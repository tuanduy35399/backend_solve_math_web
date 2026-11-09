"""Explicit readiness checks: no generation requests and no secrets in responses."""
import os
from time import perf_counter
import httpx
from .geometry_rag import PathForChroma


def model_check(base,model,key):
    if not base or not model:
        return {'status':'not_configured','detail':'Thiếu base URL hoặc tên model.'}
    started=perf_counter()
    try:
        with httpx.Client(timeout=8,trust_env=False) as client:
            response=client.get(base.rstrip('/')+'/models',headers={'Authorization':'Bearer '+(key or 'local')})
        if response.status_code==200:
            available={m.get('id') for m in response.json().get('data',[])}
            return {'status':'connected' if model in available else 'error',
                    'detail':'Endpoint liệt kê được model đã cấu hình.' if model in available else 'Endpoint hoạt động nhưng chưa liệt kê model đã cấu hình.',
                    'latency_ms':round((perf_counter()-started)*1000)}
        return {'status':'unchecked' if response.status_code in [404,405] else 'error','detail':f'Kiểm tra /models trả HTTP {response.status_code}; chưa kiểm chứng suy luận.'}
    except Exception as exc:
        return {'status':'error','detail':f'Không kiểm tra được kết nối ({type(exc).__name__}).'}


def check_services():
    from django.db import connection
    connection.ensure_connection()
    result={'database':{'status':'connected'},'fastapi':{'status':'running'}}
    result['qwen']=model_check(os.getenv('QWEN_BASE_URL'),os.getenv('QWEN_MODEL'),os.getenv('QWEN_API_KEY'))
    result['content']=model_check(os.getenv('OPENAI_BASE_URL'),os.getenv('OPENAI_MODEL'),os.getenv('OPENAI_API_KEY')) if os.getenv('CONTENT_PROVIDER')=='openai' else {'status':'unchecked','detail':'Kiểm tra này dành cho endpoint tương thích OpenAI.'}
    try:
        from neo4j import GraphDatabase
        if not os.getenv('NEO4J_URI') or not os.getenv('NEO4J_PASSWORD'):
            result['neo4j']={'status':'not_configured'}
        else:
            with GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.getenv('NEO4J_USERNAME','neo4j'),os.environ['NEO4J_PASSWORD']),connection_timeout=5) as driver:
                with driver.session(database=os.getenv('NEO4J_DATABASE','neo4j')) as session:
                    nodes=session.run('MATCH (n:MindGeoConcept) RETURN count(n) AS count').single()['count']
                    entities=session.run('MATCH (n:MindGeoEntity) RETURN count(n) AS count').single()['count']
                    relations=session.run('MATCH (:MindGeoEntity)-[r]->(:MindGeoEntity) RETURN count(r) AS count').single()['count']
            result['neo4j']={'status':'connected','concepts':nodes,'entities':entities,'extracted_relations':relations}
    except Exception as exc:
        result['neo4j']={'status':'error','detail':f'Neo4j: {type(exc).__name__}.'}
    if os.getenv('RAG_ENABLED','false').lower()!='true':
        result['rag']={'status':'not_configured'}
    elif not PathForChroma().exists():
        result['rag']={'status':'error','detail':'Chưa có thư mục Chroma; cần chạy đồng bộ chỉ mục.'}
    else:
        try:
            import chromadb
            with chromadb.PersistentClient(path=str(PathForChroma())) as client:
                count=client.get_collection(os.getenv('CHROMA_COLLECTION','mindgeo_geometry')).count()
            result['rag']={'status':'connected' if count and result['neo4j']['status']=='connected' else 'error','documents':count,'detail':'Đã kiểm tra Chroma và Neo4j; chưa đo một truy vấn embedding.'}
        except Exception as exc:
            result['rag']={'status':'error','detail':f'Chroma: {type(exc).__name__}.'}
    result['research']={'status':'configured' if all(os.getenv(k) for k in ['OPENAI_BASE_URL','OPENAI_API_KEY','OPENAI_MODEL','TAVILY_API_KEY']) else 'not_configured','detail':'Chưa gọi tìm kiếm hoặc tạo báo cáo trong bước kiểm tra kết nối.'}
    result['note']='Kết quả kiểm tra trực tiếp; /models không chứng minh chất lượng suy luận. Không gọi model sinh nội dung trong bước này.'
    return result
