import importlib.util
from pathlib import Path
from django.conf import settings

ROOT = settings.BASE_DIR / 'external'

def load_source(name, relative):
    path=ROOT/relative
    if not path.is_file(): raise RuntimeError('Chưa clone repo nguồn. Chạy python scripts/clone_sources.py.')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
