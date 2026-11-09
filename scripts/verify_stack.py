"""Real HTTP/browser verification on an isolated temporary database; no paid model calls."""
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
frontend=Path(os.getenv('MINDGEO_FRONTEND',str(root.parent/'solve_math_vlm/frontend')))
processes=[]

def wait(url,process):
    for _ in range(100):
        if process.poll() is not None: raise RuntimeError('Test service stopped early; inspect its log.')
        try:
            with urllib.request.urlopen(url,timeout=1) as response:
                if response.status==200:return
        except Exception:time.sleep(.2)
    raise RuntimeError('Timed out waiting for '+url)

with tempfile.TemporaryDirectory(prefix='mindgeo-qa-') as temp:
    env={**os.environ,'DATABASE_PATH':str(Path(temp)/'qa.sqlite3'),'DJANGO_SECRET_KEY':secrets.token_urlsafe(40),'DJANGO_DEBUG':'true',
         'DJANGO_ALLOWED_HOSTS':'127.0.0.1,localhost,testserver','QWEN_BASE_URL':'','QWEN_MODEL':'','QWEN_API_KEY':'','GEMINI_API_KEY':'','GEMINI_MODEL':'','OPENAI_API_KEY':'','TAVILY_API_KEY':'','RAG_ENABLED':'false',
         'TEST_USER_PASSWORD':secrets.token_urlsafe(18),'TEST_FRONTEND_URL':'http://127.0.0.1:5180',
         'DJANGO_TARGET':'http://127.0.0.1:18000','FASTAPI_TARGET':'http://127.0.0.1:18001','VITE_DEMO_MODE':'false'}
    for command in [['manage.py','migrate','--noinput'],['manage.py','seed_learning']]:subprocess.run([sys.executable,*command],cwd=root,env=env,check=True,stdout=subprocess.DEVNULL)
    seed="""import os
from django.contrib.auth.models import User
from learning.models import Profile
for name,role in [('qa_student','student'),('qa_educator','educator'),('qa_admin','admin')]:
 u=User.objects.create_user(name,password=os.environ['TEST_USER_PASSWORD'],first_name=name)
 Profile.objects.create(user=u,role=role)
"""
    subprocess.run([sys.executable,'manage.py','shell','-c',seed],cwd=root,env=env,check=True,stdout=subprocess.DEVNULL)
    logs=[]
    try:
        for args,cwd,url in [
            ([sys.executable,'manage.py','runserver','127.0.0.1:18000','--noreload'],root,'http://127.0.0.1:18000/api/v1/health/'),
            ([sys.executable,'-m','uvicorn','ai_service.main:app','--host','127.0.0.1','--port','18001'],root,'http://127.0.0.1:18001/api/v1/ai/health'),
            (['npm','run','dev','--','--port','5180','--strictPort'],frontend,'http://127.0.0.1:5180'),
        ]:
            log=open(Path(temp)/f'service-{len(processes)}.log','w+');logs.append(log)
            process=subprocess.Popen(args,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(process);wait(url,process)
        result=subprocess.run(['npm','run','test:e2e','--','--project=live'],cwd=frontend,env=env)
        if result.returncode:
            for log in logs:
                log.flush();log.seek(0);print(log.read()[-10000:])
        sys.exit(result.returncode)
    finally:
        for process in processes:
            if process.poll() is None:process.terminate()
        for process in processes:
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        for log in logs:log.close()
