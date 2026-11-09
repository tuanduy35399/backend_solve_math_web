import json
import os
from datetime import datetime, timezone
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from learning.models import Material
from integrations.geometry_rag import material_text
from integrations.geometry_extraction import cache_key, extract_document, make_extractor, write_document
from integrations.upstream import load_source


class Command(BaseCommand):
    help='Dùng model bên ngoài trích xuất thực thể/quan hệ; cache và tiếp tục khi chạy lại.'

    def add_arguments(self, parser):
        parser.add_argument('--limit',type=int,default=0)
        parser.add_argument('--rpm',type=int,default=10)
        parser.add_argument('--dry-run',action='store_true')
        parser.add_argument('--force',action='store_true')
        parser.add_argument('--max-calls',type=int,default=100,help='Giới hạn lượt gọi offline trong lần chạy này, không trừ quota bài/quiz.')

    def handle(self,*args,**options):
        materials=list(Material.objects.filter(status='Đã xuất bản',id__startswith='g').order_by('id'))
        if options['limit']<0 or not 1<=options['rpm']<=60 or options['max_calls']<1:
            raise CommandError('--limit phải >=0; --rpm từ 1 đến 60; --max-calls phải >=1.')
        if options['limit']:materials=materials[:options['limit']]
        root=settings.BASE_DIR/'data/geometry-extraction'
        plan=[(m,material_text(m)) for m in materials]
        needed=sum(options['force'] or not (root/(cache_key(text)+'.json')).exists() for _,text in plan)
        self.stdout.write(f'{len(plan)} bài; {needed} lượt gọi model dự kiến; {len(plan)-needed} cache. Không gửi chat/ảnh/thông tin người học.')
        if options['dry_run']:return
        extractor=make_extractor()
        limiter=load_source('mindgeo_rate_limit','hybrid_graph_rag/hybridRAG_paper/indexing/rate_limit.py').RateLimiter(max_per_minute=options['rpm'])
        from neo4j import GraphDatabase
        driver=GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.getenv('NEO4J_USERNAME','neo4j'),os.environ['NEO4J_PASSWORD']),connection_timeout=5)
        root.mkdir(parents=True,exist_ok=True)
        completed=[]
        calls=0
        try:
            driver.verify_connectivity()
            for index,(material,text) in enumerate(plan,1):
                path=root/(cache_key(text)+'.json')
                cached=path.exists() and not options['force']
                if cached:result=json.loads(path.read_text())
                else:
                    from openai import APIConnectionError, APITimeoutError, RateLimitError, InternalServerError
                    for attempt in range(2):
                        if calls>=options['max_calls']:
                            raise CommandError('Đã đạt --max-calls của lượt dựng đồ thị; chạy lại để tiếp tục từ cache.')
                        limiter.wait()
                        calls+=1
                        try:
                            result=extract_document(extractor,material,text)
                            break
                        except (APIConnectionError,APITimeoutError,RateLimitError,InternalServerError) as exc:
                            if attempt:raise
                            self.stdout.write(f'{material.pk}: {type(exc).__name__}; thử lại một lần, có tính --max-calls.')
                write_document(driver,material,result)
                if not cached:
                    temporary=path.with_suffix('.tmp')
                    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2))
                    temporary.replace(path)
                completed.append({'id':material.pk,'entities':len(result['nodes']),'relations':len(result['edges']),'rejected':result.get('rejected_relations',0),'cached':cached})
                self.stdout.write(f'{index}/{len(plan)} {material.pk}: {len(result["nodes"])} thực thể, {len(result["edges"])} quan hệ, {result.get("rejected_relations",0)} bị loại thiếu bằng chứng; '+('cache' if cached else 'LLM thật'))
        except Exception as exc:
            detail=str(exc).replace(os.getenv('OPENAI_API_KEY') or '\0','[REDACTED]')[:240] if isinstance(exc,ValueError) else type(exc).__name__
            raise CommandError(f'Dừng tại bài {plan[len(completed)][0].pk if len(completed)<len(plan) else "cuối"}: {detail}. Những bài đã xong được giữ trong cache; chạy lại để tiếp tục. Kiểm tra cấu hình/đầu ra trước khi thử lại.') from exc
        finally:
            driver.close()
            (root/'last-run.json').write_text(json.dumps({'completed_at':datetime.now(timezone.utc).isoformat(),'requested':len(plan),'model_calls':calls,'completed':completed},ensure_ascii=False,indent=2))
