"""Clone exact upstream revisions without modifying their code or importing their .env/DB files."""
import json
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
for source in json.loads((root/'integrations/sources.json').read_text()):
    destination=root/'external'/source['name']
    if destination.exists():
        revision=subprocess.check_output(['git','-C',str(destination),'rev-parse','HEAD'],text=True).strip()
        if revision!=source['revision']: raise SystemExit(f"Revision differs for {source['name']}; keeping checkout untouched.")
        print(f"Already cloned: {source['name']}")
        continue
    destination.parent.mkdir(exist_ok=True)
    subprocess.run(['git','clone','--no-checkout',source['url'],str(destination)],check=True)
    subprocess.run(['git','-C',str(destination),'checkout','--detach',source['revision']],check=True)
    print(f"Cloned: {source['name']}")
