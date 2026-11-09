"""Run Django and FastAPI together. Stop both cleanly with Ctrl+C."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
processes=[]
try:
    for args in [[sys.executable,'manage.py','runserver','127.0.0.1:8000','--noreload'],[sys.executable,'-m','uvicorn','ai_service.main:app','--host','127.0.0.1','--port','8001']]:
        processes.append(subprocess.Popen(args,cwd=root))
    while all(p.poll() is None for p in processes): time.sleep(.5)
except KeyboardInterrupt: pass
finally:
    for p in processes:
        if p.poll() is None: p.terminate()
    for p in processes:
        try:p.wait(timeout=8)
        except subprocess.TimeoutExpired:p.kill();p.wait()
