"""Geometry adapter. Upstream BGE, ChromaStore and RRF implementations stay unchanged."""
import os
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from learning.models import Material, Prerequisite
from .upstream import load_source
from ai_service.providers import ProviderUnavailable

@lru_cache(maxsize=1)
def resources():
    if os.getenv('RAG_ENABLED','false').lower()!='true':
        raise ProviderUnavailable('Hybrid RAG chưa bật. Cấu hình Neo4j, cài requirements-ai.txt, bật RAG_ENABLED và đồng bộ học liệu.')
    from neo4j import GraphDatabase
    bge=load_source('mindgeo_bge','hybrid_graph_rag/hybridRAG_paper/indexing/embedding/bge_m3.py')
    chroma=load_source('mindgeo_chroma','hybrid_graph_rag/hybridRAG_paper/indexing/vector/chroma.py')
    hybrid=load_source('mindgeo_rrf','hybrid_graph_rag/hybridRAG_paper/retrieval/search/hybrid_search.py')
    if not all(os.getenv(k) for k in ['NEO4J_URI','NEO4J_PASSWORD']): raise ProviderUnavailable('Chưa cấu hình Neo4j.')
    driver=GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.getenv('NEO4J_USERNAME','neo4j'),os.environ['NEO4J_PASSWORD']),connection_timeout=5)
    driver.verify_connectivity()
    db_path=PathForChroma()
    store=chroma.ChromaStore(db_path=str(db_path),collection_name=os.getenv('CHROMA_COLLECTION','mindgeo_geometry'))
    return bge.BGE_M3_Embedding().get_model(),store,driver,hybrid.HybridSearch()

def PathForChroma():
    from pathlib import Path
    path=Path(os.getenv('CHROMA_DB_PATH','./data/chroma'))
    return path if path.is_absolute() else settings.BASE_DIR/path

def sync_corpus():
    embed,store,driver,_=resources()
    materials=list(Material.objects.filter(status='Đã xuất bản'))
    nodes=[{'id':m.pk,'title':m.title,'text':m.text,'formula':m.formula} for m in materials]
    ids=[m.pk for m in materials]
    # Remove stale entries only from this application's dedicated collection.
    old=store.collection.get().get('ids',[])
    stale=[pk for pk in old if pk not in ids]
    if stale: store.collection.delete(ids=stale)
    for m in materials:
        text=m.title+'\n'+m.text+'\n'+m.formula+'\n'+m.note
        store.collection.upsert(ids=[m.pk],documents=[text],embeddings=[embed.get_text_embedding(text)],metadatas=[{'concept_id':m.pk,'grade_level':m.grade,'document_type':'theory','source_reference':m.source,'title':m.title}])
    edges=[{'source':a,'target':b} for a,b in Prerequisite.objects.filter(source_id__in=ids,target_id__in=ids).values_list('source_id','target_id')]
    def write(tx):
        tx.run('MATCH (n:MindGeoConcept) WHERE NOT n.id IN $ids DETACH DELETE n',ids=ids).consume()
        tx.run('UNWIND $nodes AS row MERGE (n:Concept:MindGeoConcept {id:row.id}) SET n.title=row.title,n.text=row.text,n.formula=row.formula',nodes=nodes).consume()
        tx.run('MATCH (:MindGeoConcept)-[r:PREREQUISITE_OF]->(:MindGeoConcept) DELETE r').consume()
        tx.run('UNWIND $edges AS row MATCH (a:MindGeoConcept {id:row.source}),(b:MindGeoConcept {id:row.target}) MERGE (a)-[:PREREQUISITE_OF]->(b)',edges=edges).consume()
    with driver.session(database=os.getenv('NEO4J_DATABASE','neo4j')) as session: session.execute_write(write)
    return {'materials':len(ids),'edges':len(edges),'embedding':'BAAI/bge-m3'}

def retrieve(concept_id):
    embed,store,driver,hybrid=resources()
    from llama_index.core.schema import TextNode,NodeWithScore
    material=Material.objects.get(pk=concept_id,status='Đã xuất bản')
    query=material.title+' '+material.text
    def vector_search():
        if store.collection.count()==0: raise RuntimeError('Chroma chưa có học liệu. Giáo viên cần đồng bộ chỉ mục.')
        result=store.collection.query(query_embeddings=[embed.get_query_embedding(query)],n_results=min(5,store.collection.count()))
        return [NodeWithScore(node=TextNode(id_=pk,text=text,metadata=metadata),score=1/(1+distance))
                for pk,text,metadata,distance in zip(result['ids'][0],result['documents'][0],result['metadatas'][0],result['distances'][0])]
    def graph_search():
        with driver.session(database=os.getenv('NEO4J_DATABASE','neo4j')) as session:
            rows=session.run('MATCH (n:MindGeoConcept {id:$id}) MATCH (p:MindGeoConcept)-[:PREREQUISITE_OF*0..6]->(n) RETURN DISTINCT p.id AS id,p.title AS title,p.text AS text,p.formula AS formula LIMIT 30',id=concept_id)
            return [dict(r) for r in rows]
    with ThreadPoolExecutor(max_workers=2) as pool:
        vector=pool.submit(vector_search);graph=pool.submit(graph_search)
        vector_results=vector.result();prerequisites=graph.result()
    if not prerequisites: raise RuntimeError('Neo4j chưa có khái niệm này. Cần đồng bộ lại học liệu.')
    graph_results=[NodeWithScore(node=TextNode(id_=r['id'],text=r['title']+'\n'+r['text']+'\n'+r['formula'],metadata={'concept_id':r['id'],'title':r['title'],'source_reference':'Neo4j / học liệu nội bộ'}),score=1) for r in prerequisites]
    fused=hybrid.merge(vector_results=vector_results,graph_results=graph_results,top_k=8)
    # Current Django publication status remains authoritative if an index is stale.
    published=set(Material.objects.filter(status='Đã xuất bản').values_list('id',flat=True))
    contexts=[{'concept_id':n.node.metadata['concept_id'],'text':n.node.get_content(),'source':n.node.metadata.get('source_reference',''),'score':n.score} for n in fused if n.node.metadata.get('concept_id') in published]
    return {'concept_id':concept_id,'prerequisites':[r for r in prerequisites if r['id']!=concept_id and r['id'] in published], 'contexts':contexts,'channels':['BGE-M3 / Chroma','Neo4j','upstream RRF']}
