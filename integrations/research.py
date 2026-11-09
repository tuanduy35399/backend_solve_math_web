import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from django.conf import settings
from .upstream import ROOT

def create_report(material):
    from ai_service.providers import ProviderUnavailable
    if not all(os.getenv(k) for k in ['OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_MODEL','TAVILY_API_KEY']):
        raise ProviderUnavailable('Cần OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL và TAVILY_API_KEY cho agent nghiên cứu.')
    source=ROOT/'ai_agent_game_maker_plan'
    if not (source/'tools.py').exists(): raise ProviderUnavailable('Chưa clone repo agent. Chạy scripts/clone_sources.py.')
    with tempfile.TemporaryDirectory(prefix='mindgeo-report-') as temp:
        subprocess.run([sys.executable,str(settings.BASE_DIR/'integrations/research_worker.py'),str(source)],input=json.dumps({'topic':material.title+' / '+material.topic},ensure_ascii=False),text=True,cwd=temp,capture_output=True,timeout=180,check=True)
        result=json.loads((Path(temp)/'result.json').read_text())
        if len(result['content'])>100000: raise ValueError('Báo cáo quá dài.')
        return result
