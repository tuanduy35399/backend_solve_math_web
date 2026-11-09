"""Exercise real RAG (and optional cloud generation/report) using isolated accounts/DB.

Actual Neo4j/Chroma are queried read-only. --generate/--research make real external
calls with academic content, so they must be selected explicitly.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def worker(generate,research):
    import time
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','backend_web.settings')
    sys.path.insert(0,str(ROOT))
    import django
    django.setup()
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from fastapi.testclient import TestClient
    from learning.models import Profile
    from ai_service.main import app
    from integrations.geometry_rag import close_resources
    user=User.objects.create(username='live_ai_verification')
    Profile.objects.create(user=user,role='educator')
    headers={'Authorization':'Token '+Token.objects.create(user=user).key}
    client=TestClient(app)
    result={'fixture_database':'temporary','qwen':'not_tested_no_gpu','retrieval':[]}
    try:
        for pk in ['g6-trung-diem','g7-tam-giac-can','g8-pythagore','g9-tiep-tuyen']:
            started=time.perf_counter()
            response=client.post('/api/v1/rag/analyze-gap',json={'concept_id':pk},headers=headers)
            response.raise_for_status()
            data=response.json()
            assert data['contexts'] and all(c['source'] for c in data['contexts'])
            result['retrieval'].append({'concept':pk,'contexts':len(data['contexts']),'elapsed_ms':round((time.perf_counter()-started)*1000)})
        response=client.get('/api/v1/rag/graph?concept_id=g6-chu-vi-dien-tich-chu-nhat',headers=headers)
        response.raise_for_status()
        graph=response.json()
        assert graph['nodes'] and graph['edges'] and not graph['stale']
        result['extracted_graph']={'entities':len(graph['nodes']),'relations':len(graph['edges']),'origin':graph['origin']}
        if generate:
            response=client.post('/api/v1/recommend/quiz-summary',json={'concept_id':'g8-pythagore'},headers=headers)
            response.raise_for_status()
            generated=response.json();quiz_id=generated['quiz_id']
            from rest_framework.test import APIClient
            api=APIClient();api.force_authenticate(user)
            quiz=api.get(f'/api/v1/quizzes/{quiz_id}/').json()
            assert all('correct' not in question for question in quiz['questions'])
            scored=api.post(f'/api/v1/quizzes/{quiz_id}/submit/',{'answers':[0]*len(quiz['questions']),'seconds':30},format='json')
            assert scored.status_code==200
            result['generation']={'provider':generated['source'],'questions':len(quiz['questions']),'exercises':len(generated['exercises']),'saved':True,'server_grading_status':scored.status_code}
        if research:
            response=client.post('/api/v1/research/report',json={'concept_id':'g8-pythagore'},headers=headers)
            response.raise_for_status()
            report=response.json()
            assert report['sources'] and report['content']
            (ROOT/'data/live-research-report.md').write_text(report['content'])
            result['research']={'sources':len(report['sources']),'characters':len(report['content']),'saved':True}
        (ROOT/'data/live-ai-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False))
    finally:
        close_resources()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--generate',action='store_true')
    parser.add_argument('--research',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:
        worker(args.generate,args.research)
        return
    with tempfile.TemporaryDirectory(prefix='mindgeo-live-ai-') as temp:
        env={**os.environ,'DATABASE_PATH':str(Path(temp)/'verification.sqlite3'),'DJANGO_DEBUG':'true','DJANGO_ALLOWED_HOSTS':'testserver,localhost,127.0.0.1','RAG_ENABLED':'true','RAG_MODEL_OFFLINE':'true'}
        for command in [['manage.py','migrate','--noinput'],['manage.py','seed_learning'],['manage.py','import_geometry_corpus','--publish']]:
            subprocess.run([sys.executable,*command],cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL)
        command=[sys.executable,str(Path(__file__).resolve()),'--worker']
        if args.generate:command.append('--generate')
        if args.research:command.append('--research')
        subprocess.run(command,cwd=ROOT,env=env,check=True)


if __name__=='__main__':main()
