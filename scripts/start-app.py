"""Start only this checkout's application, with a persistent log and instance check."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
import httpx

root=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser();parser.add_argument('--timeout',type=int,default=45);args=parser.parse_args()
port=int(os.getenv('CZ_PORT','8790'));url=f'http://127.0.0.1:{port}'
instance=hashlib.sha256(str(root).encode()).hexdigest()[:16]
def status():
    try:
        r=httpx.get(url+'/api/health',timeout=2,trust_env=False);r.raise_for_status();return r.json()
    except (httpx.HTTPError,ValueError): return None
existing=status()
if existing:
    if existing.get('installation')!=instance: raise SystemExit('该端口已有其他工作台，请配置新的 CZ_PORT。')
    from cizheng_precheck import __version__
    if existing.get('version')!=__version__: raise SystemExit('旧版工作台仍在运行，请先停止本项目应用，再执行 run-spark.sh；不会停止其他服务。')
    print('本工作台已运行：'+url);raise SystemExit(0)
data=Path(os.getenv('CZ_DATA_DIR',str(root/'runtime'))).resolve();data.mkdir(parents=True,exist_ok=True)
with (data/'app.log').open('ab') as log:
    process=subprocess.Popen([sys.executable,'-m','uvicorn','cizheng_precheck.api:create_app','--factory',
        '--host',os.getenv('CZ_HOST','127.0.0.1'),'--port',str(port),'--workers','1'],cwd=root,
        stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True)
    (data/'app.pid').write_text(str(process.pid))
deadline=time.monotonic()+args.timeout
while time.monotonic()<deadline:
    ready=status()
    if ready and ready.get('installation')==instance:
        print('工作台已启动：'+url);break
    if process.poll() is not None: raise SystemExit('应用未能启动，请查看 runtime/app.log。')
    time.sleep(1)
else: raise SystemExit('应用尚未就绪，请检查日志；本脚本未停止其他服务。')
