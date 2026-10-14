"""Read actual readiness and optionally export licensed rehearsal photos; never simulate inference."""
import argparse
import json
import os
from pathlib import Path
import httpx

parser=argparse.ArgumentParser()
parser.add_argument('--base-url',default='http://127.0.0.1:'+os.getenv('CZ_PORT','8790'))
parser.add_argument('--export-photos',action='store_true')
args=parser.parse_args()
headers={'Authorization':'Bearer '+os.environ['CZ_ACCESS_TOKEN']} if os.getenv('CZ_ACCESS_TOKEN') else {}
folder=Path(os.getenv('CZ_DATA_DIR','runtime'))/'stage';folder.mkdir(parents=True,exist_ok=True)
with httpx.Client(base_url=args.base_url,headers=headers,timeout=30,trust_env=False) as client:
    r=client.get('/api/operator/readiness');r.raise_for_status();result=r.json()
    (folder/'readiness.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    if args.export_photos:
        r=client.get('/api/operator/photos.zip');r.raise_for_status()
        (folder/'rehearsal-photos.zip').write_bytes(r.content)
    for c in result['checks']:print(('通过' if c['ok'] else '待处理')+' · '+c['label']+' · '+c['detail'])
    # Keep a PDF fallback usable even if the browser or the model later becomes unavailable.
    if result['backups']:
        b=result['backups'][0];r=client.get(b['pdf_url']);r.raise_for_status()
        (folder/(b['job_id']+'.pdf')).write_bytes(r.content)
print('检查及备用文件：'+str(folder))
raise SystemExit(0 if result['ready'] else 1)
