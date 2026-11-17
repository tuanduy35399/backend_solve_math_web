"""Real HTTP/browser verification on an isolated temporary database; no paid model calls."""
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
frontend=Path(os.getenv('MINDGEO_FRONTEND',str(root.parent/'solve_math_vlm/frontend')))
processes=[]
with_corpus='--corpus' in sys.argv

def wait(url,process):
    for _ in range(100):
        if process.poll() is not None: raise RuntimeError('Test service stopped early; inspect its log.')
        try:
            with urllib.request.urlopen(url,timeout=1) as response:
                if response.status==200:return
        except Exception:time.sleep(.2)
    raise RuntimeError('Timed out waiting for '+url)

with tempfile.TemporaryDirectory(prefix='mindgeo-qa-') as temp:
    # Browser cases share one loopback IP; keep production's login limit intact.
    Path(temp,'qa_settings.py').write_text(
        "from backend_web.settings import *\n"
        "CACHES = {'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}\n"
    )
    env={**os.environ,'DATABASE_PATH':str(Path(temp)/'qa.sqlite3'),'DJANGO_SECRET_KEY':secrets.token_urlsafe(40),'DJANGO_DEBUG':'true',
         'DJANGO_SETTINGS_MODULE':'qa_settings','PYTHONPATH':os.pathsep.join([temp,str(root),os.environ.get('PYTHONPATH','')]),
         'DJANGO_ALLOWED_HOSTS':'127.0.0.1,localhost,testserver','OPENAI_BASE_URL':'','OPENAI_MODEL':'','GEMINI_API_KEY':'','GEMINI_MODEL':'','OPENAI_API_KEY':'','TAVILY_API_KEY':'','RAG_ENABLED':'false',
         'TEST_USER_PASSWORD':secrets.token_urlsafe(18),'TEST_FRONTEND_URL':'http://127.0.0.1:5180',
         'DJANGO_TARGET':'http://127.0.0.1:18000','FASTAPI_TARGET':'http://127.0.0.1:18001','VITE_DEMO_MODE':'false'}
    env['TEST_GEOMETRY_CORPUS']='true' if with_corpus else 'false'
    commands=[['manage.py','migrate','--noinput'],['manage.py','seed_learning']]
    if with_corpus:commands.append(['manage.py','import_geometry_corpus','--publish'])
    for command in commands:subprocess.run([sys.executable,*command],cwd=root,env=env,check=True,stdout=subprocess.DEVNULL)
    seed="""import os
from django.contrib.auth.models import User
from learning.models import Profile,Quiz
for name,role in [('qa_student','student'),('qa_educator','educator'),('qa_admin','admin')]:
 u=User.objects.create_user(name,password=os.environ['TEST_USER_PASSWORD'],first_name=name)
 Profile.objects.create(user=u,role=role)
if os.environ['TEST_GEOMETRY_CORPUS']=='true':
 Quiz.objects.create(user=User.objects.get(username='qa_student'),kind='general',source='qa-fixture',summary='Quiz kiểm thử kiến thức hình học',questions=[{'concept':'g8-pythagore','question':'Tam giác vuông có hai cạnh góc vuông 5 và 12 cm. Cạnh huyền dài bao nhiêu?','options':['13 cm','17 cm','7 cm','60 cm'],'correct':0,'explanation':'Theo Pythagore: căn của 25+144 bằng 13.'}])
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
            process=subprocess.Popen(args,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);processes.append(process);wait(url,process)
        result=subprocess.run(['npm','run','test:e2e','--','--project=live',*[arg for arg in sys.argv[1:] if arg!='--corpus']],cwd=frontend,env=env)
        if result.returncode:
            for log in logs:
                log.flush();log.seek(0);print(log.read()[-10000:])
        sys.exit(result.returncode)
    finally:
        # npm starts Vite as a child; stop our full session to avoid orphan QA servers.
        for process in processes:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        for process in processes:
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        for log in logs:log.close()
