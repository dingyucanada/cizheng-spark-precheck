"""Curated local source import, explicitly run by an operator; no arbitrary web crawling."""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from cizheng_precheck.config import ROOT

parser=argparse.ArgumentParser()
parser.add_argument('file', help='A JSON file following docs/reference-template.json')
args=parser.parse_args()
data=json.loads(Path(args.file).read_text())
required=('title','provider','url','excerpt','location','rights','reviewer','reviewed_at')
for key in required:
    if not isinstance(data.get(key),str) or not data[key].strip():
        raise SystemExit('Missing required string: '+key)
url=urlparse(data['url'])
approved={'www.metmuseum.org':'metmuseum','www.dpm.org.cn':'palace-museum','www.britishmuseum.org':'british-museum','collections.vam.ac.uk':'vam','www.vam.ac.uk':'vam','asia.si.edu':'smithsonian','www.artic.edu':'artic'}
if url.scheme!='https' or url.hostname not in approved or url.username or url.password:
    raise SystemExit('Source host is not an approved institution; extend the reviewed allowlist first.')
if len(data['excerpt'])>6000:
    raise SystemExit('Keep only the relevant cited passage, at most 6000 characters.')
digest=hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
record={'id':'CURATED-'+digest[:12],'title':data['title'],'provider':data['provider'],'url':data['url'],
        'source_group':approved[url.hostname],'excerpt':data['excerpt'],'location':data['location'],
        'rights':data['rights'],'reviewer':data['reviewer'],'reviewed_at':data['reviewed_at'],
        'public_domain':False,'image_url':'','public_record':bool(data.get('public_record',False)),
        'record_sha256':digest,'retrieved_at':datetime.now(timezone.utc).isoformat(),'accession':data.get('accession',''),
        'medium':data.get('medium',''),'date':data.get('date','')}
folder=ROOT/'knowledge/curated';folder.mkdir(exist_ok=True)
(folder/(record['id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(record['id']+' 已入库。重启应用后生效；人工核对标记不等于真伪结论。')
