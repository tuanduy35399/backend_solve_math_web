"""Geometry adapter. Upstream BGE, ChromaStore and RRF implementations stay unchanged."""
import os
import hashlib
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from learning.models import Material, Prerequisite
from .upstream import load_source
from ai_service.providers import ProviderUnavailable

def resources():
    if os.getenv('RAG_ENABLED','false').lower()!='true':
        raise ProviderUnavailable('Hybrid RAG chưa bật. Cấu hình Neo4j, cài requirements-ai.txt, bật RAG_ENABLED và đồng bộ học liệu.')
    return _resources()

@lru_cache(maxsize=1)
def _resources():
    # Some Transformers versions start a remote conversion thread for .bin models.
    # Use the original BGE weights without triggering that unrelated service.
    os.environ.setdefault('DISABLE_SAFETENSORS_CONVERSION','1')
    os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
    if os.getenv('RAG_MODEL_OFFLINE','false').lower()=='true':
        os.environ['HF_HUB_OFFLINE']='1'
    from neo4j import GraphDatabase
    bge=load_source('mindgeo_bge','hybrid_graph_rag/hybridRAG_paper/indexing/embedding/bge_m3.py')
    chroma=load_source('mindgeo_chroma','hybrid_graph_rag/hybridRAG_paper/indexing/vector/chroma.py')
    hybrid=load_source('mindgeo_rrf','hybrid_graph_rag/hybridRAG_paper/retrieval/search/hybrid_search.py')
    if not all(os.getenv(k) for k in ['NEO4J_URI','NEO4J_PASSWORD']): raise ProviderUnavailable('Chưa cấu hình Neo4j.')
    driver=GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.getenv('NEO4J_USERNAME','neo4j'),os.environ['NEO4J_PASSWORD']),connection_timeout=5)
    driver.verify_connectivity()
    db_path=PathForChroma()
    store=chroma.ChromaStore(db_path=str(db_path),collection_name=os.getenv('CHROMA_COLLECTION','mindgeo_geometry'))
    import torch
    torch.set_num_threads(int(os.getenv('RAG_CPU_THREADS','2')))
    embed=bge.BGE_M3_Embedding().get_model()
    # Keep the upstream model; bound attention memory on the student's laptop.
    embed.max_length=int(os.getenv('RAG_EMBED_MAX_LENGTH','2048'))
    embed._model.max_seq_length=embed.max_length
    embed.embed_batch_size=1
    return embed,store,driver,hybrid.HybridSearch()

def close_resources():
    if _resources.cache_info().currsize:
        _,store,driver,_=_resources()
        driver.close()
        store.client.close()
        _resources.cache_clear()

def PathForChroma():
    from pathlib import Path
    path=Path(os.getenv('CHROMA_DB_PATH','./data/chroma'))
    return path if path.is_absolute() else settings.BASE_DIR/path

def material_text(material):
    sections=material.corpus_metadata.get('sections',{})
    if sections:
        # Source links and prerequisite IDs are metadata, not mathematical evidence.
        return material.title+'\n'+material.text+'\n'+material.formula+'\n'+material.note+'\n\n'+'\n\n'.join(
            title+'\n'+text for title,text in sections.items()
            if title not in ['Phát biểu và ý nghĩa','Điều kiện áp dụng','Công thức và ký hiệu','Lỗi thường gặp','Kiến thức tiên quyết đề xuất','Nguồn đối chiếu']
        )
    return material.title+'\n'+material.text+'\n'+material.formula+'\n'+material.note

def sync_corpus(progress=None):
    embed,store,driver,_=resources()
    materials=list(Material.objects.filter(status='Đã xuất bản').order_by('id'))
    nodes=[{'id':m.pk,'title':m.title,'text':material_text(m),'formula':m.formula,
            'content_sha256':embedding_fingerprint(m,embed.max_length),
            'grade':m.grade,'document_type':m.corpus_metadata.get('document_type','theory'),
            'review_status':m.corpus_metadata.get('review_status','not_recorded'),'source':m.source} for m in materials]
    ids=[m.pk for m in materials]
    texts={m.pk:material_text(m) for m in materials}
    # Reject truncation before changing an index; this corpus fits the CPU limit.
    for pk,text in texts.items():
        if len(embed._model.tokenizer.encode(text))>embed.max_length:
            raise ValueError(f'Học liệu {pk} vượt RAG_EMBED_MAX_LENGTH; tăng giới hạn hoặc chia nhỏ học liệu trước khi đồng bộ.')
    old=store.collection.get(include=['metadatas'])
    fingerprints={pk:(meta or {}).get('content_sha256') for pk,meta in zip(old['ids'],old['metadatas'])}
    embedded=0
    for index,m in enumerate(materials,1):
        text=texts[m.pk]
        fingerprint=embedding_fingerprint(m,embed.max_length)
        metadata={'concept_id':m.pk,'grade_level':m.grade,
                  'document_type':m.corpus_metadata.get('document_type','theory'),
                  'review_status':m.corpus_metadata.get('review_status','not_recorded'),
                  'source_reference':m.source,'title':m.title,'content_sha256':fingerprint}
        if fingerprints.get(m.pk)!=fingerprint:
            store.collection.upsert(ids=[m.pk],documents=[text],embeddings=[embed.get_text_embedding(text)],metadatas=[metadata])
            embedded+=1
        else:
            store.collection.update(ids=[m.pk],metadatas=[metadata])
        if progress and (index%10==0 or index==len(materials)):
            progress(f'Chroma: {index}/{len(materials)} học liệu; {embedded} embedding mới.')
    # Remove stale entries only from this application's dedicated collection.
    stale=[pk for pk in old['ids'] if pk not in ids]
    if stale: store.collection.delete(ids=stale)
    edges=[{'source':a,'target':b} for a,b in Prerequisite.objects.filter(source_id__in=ids,target_id__in=ids).values_list('source_id','target_id')]
    by_id={m.pk:m for m in materials}
    for edge in edges:
        target=by_id[edge['target']].corpus_metadata
        proposed=edge['source'] in target.get('prerequisites',[])
        edge['origin']=target.get('prerequisite_origin','not_recorded') if proposed else 'application'
        edge['review_status']='cho-giao-vien-duyet' if proposed else 'not_recorded'
    def write(tx):
        tx.run('MATCH (n:MindGeoConcept) WHERE NOT n.id IN $ids DETACH DELETE n',ids=ids).consume()
        tx.run('UNWIND $nodes AS row MERGE (n:Concept:MindGeoConcept {id:row.id}) SET n.title=row.title,n.text=row.text,n.formula=row.formula,n.grade=row.grade,n.document_type=row.document_type,n.review_status=row.review_status,n.source=row.source,n.content_sha256=row.content_sha256',nodes=nodes).consume()
        tx.run('MATCH (:MindGeoConcept)-[r:PREREQUISITE_OF]->(:MindGeoConcept) DELETE r').consume()
        tx.run('UNWIND $edges AS row MATCH (a:MindGeoConcept {id:row.source}),(b:MindGeoConcept {id:row.target}) MERGE (a)-[r:PREREQUISITE_OF]->(b) SET r.origin=row.origin,r.review_status=row.review_status',edges=edges).consume()
    with driver.session(database=os.getenv('NEO4J_DATABASE','neo4j')) as session:
        session.run('CREATE CONSTRAINT mindgeo_concept_id IF NOT EXISTS FOR (n:MindGeoConcept) REQUIRE n.id IS UNIQUE').consume()
        session.execute_write(write)
    return {'materials':len(ids),'edges':len(edges),'embedding':'BAAI/bge-m3','embedded':embedded,'cached':len(ids)-embedded}

def embedding_fingerprint(material,max_length):
    return hashlib.sha256(f'BAAI/bge-m3:{max_length}\n{material_text(material)}'.encode()).hexdigest()

def retrieve(concept_id,query=None):
    embed,store,driver,hybrid=resources()
    from llama_index.core.schema import TextNode,NodeWithScore
    material=Material.objects.get(pk=concept_id,status='Đã xuất bản')
    query=query or material.title+' '+material.text
    def vector_search():
        if store.collection.count()==0: raise RuntimeError('Chroma chưa có học liệu. Giáo viên cần đồng bộ chỉ mục.')
        result=store.collection.query(query_embeddings=[embed.get_query_embedding(query)],n_results=min(5,store.collection.count()))
        return [NodeWithScore(node=TextNode(id_=pk,text=text,metadata=metadata),score=1/(1+distance))
                for pk,text,metadata,distance in zip(result['ids'][0],result['documents'][0],result['metadatas'][0],result['distances'][0])]
    def graph_search():
        with driver.session(database=os.getenv('NEO4J_DATABASE','neo4j')) as session:
            rows=session.run('MATCH (n:MindGeoConcept {id:$id}) MATCH path=(p:MindGeoConcept)-[:PREREQUISITE_OF*0..6]->(n) WITH p,min(length(path)) AS depth RETURN p.id AS id,p.title AS title,p.text AS text,p.formula AS formula,p.source AS source,p.review_status AS review_status,p.content_sha256 AS content_sha256 ORDER BY depth,id LIMIT 30',id=concept_id)
            prerequisites=[dict(r) for r in rows]
            related=session.run('MATCH (:MindGeoConcept {id:$id})-[:MENTIONS]->(:MindGeoEntity)<-[:MENTIONS]-(m:MindGeoConcept) WHERE m.id<>$id RETURN DISTINCT m.id AS id,m.title AS title,m.text AS text,m.formula AS formula,m.source AS source,m.review_status AS review_status,m.content_sha256 AS content_sha256 ORDER BY id LIMIT 8',id=concept_id)
            return prerequisites,[dict(r) for r in related]
    with ThreadPoolExecutor(max_workers=2) as pool:
        vector=pool.submit(vector_search);graph=pool.submit(graph_search)
        vector_results=vector.result();prerequisites,related=graph.result()
    if not prerequisites: raise RuntimeError('Neo4j chưa có khái niệm này. Cần đồng bộ lại học liệu.')
    graph_documents={r['id']:r for r in prerequisites+related}
    graph_results=[NodeWithScore(node=TextNode(id_=r['id'],text=r['text'],metadata={'concept_id':r['id'],'title':r['title'],'source_reference':r['source'],'review_status':r['review_status'],'content_sha256':r['content_sha256']}),score=1) for r in graph_documents.values()]
    fused=hybrid.merge(vector_results=vector_results,graph_results=graph_results,top_k=8)
    # Current Django publication status remains authoritative if an index is stale.
    published=Material.objects.filter(status='Đã xuất bản').in_bulk()
    contexts=[]
    for node in fused:
        pk=node.node.metadata.get('concept_id')
        if pk not in published:continue
        current=published[pk]
        if node.node.metadata.get('content_sha256')!=embedding_fingerprint(current,embed.max_length):
            raise ProviderUnavailable('Học liệu đã thay đổi sau lần đồng bộ. Giáo viên cần đồng bộ lại chỉ mục trước khi dùng RAG.')
        contexts.append({'concept_id':pk,'text':material_text(current),'source':current.source,
                         'review_status':current.corpus_metadata.get('review_status','not_recorded'),'score':node.score})
    current_prerequisites=[]
    for row in prerequisites:
        if row['id']==concept_id or row['id'] not in published:continue
        current=published[row['id']]
        current_prerequisites.append({'id':current.pk,'title':current.title,'text':material_text(current),'formula':current.formula,
                                      'source':current.source,'review_status':current.corpus_metadata.get('review_status','not_recorded')})
    return {'concept_id':concept_id,'prerequisites':current_prerequisites, 'contexts':contexts,'channels':['BGE-M3 / Chroma','Neo4j','upstream RRF']}
