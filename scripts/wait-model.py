"""Wait for the actual configured local model; never treat a bare TCP port as ready."""
import asyncio
import argparse
import time
from cizheng_precheck.config import Settings
from cizheng_precheck.provider import Provider

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--timeout',type=int,default=900);args=parser.parse_args()
    s=Settings(); provider=Provider(s);deadline=time.monotonic()+args.timeout
    if not s.model_configured: raise SystemExit('未配置本地模型，请检查 .env。')
    last=''
    while time.monotonic()<deadline:
        status=await provider.health()
        if status['ready']:
            print('本地模型服务就绪：'+s.model);return
        if status['message']!=last:
            print(status['message'],flush=True);last=status['message']
        await asyncio.sleep(5)
    raise SystemExit('等待模型超时，请查看 docker logs cizheng-vision；安装进度保留，可再次运行。')

asyncio.run(main())
