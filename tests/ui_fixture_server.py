"""Browser-test server only. Explicit fixtures, not a user-selectable inference mode.
Run with CZ_UI_TEST_DATA set to a disposable directory. Never use for a live demo.
"""
import asyncio
import os
from pathlib import Path
import uvicorn
from cizheng_precheck.api import create_app
from cizheng_precheck.config import Settings
from cizheng_precheck.provider import Provider
from test_pipeline import TestProvider

class BrowserFixture(TestProvider):
    async def observe(self, *args):
        await asyncio.sleep(.6)
        return await super().observe(*args)
    async def compare(self, *args, **kwargs):
        await asyncio.sleep(.6)
        return await super().compare(*args, **kwargs)
    async def review(self, *args, **kwargs):
        await asyncio.sleep(.6)
        return await super().review(*args, **kwargs)

if __name__ == '__main__':
    target=os.environ.get('CZ_UI_TEST_DATA')
    if not target: raise SystemExit('This test server requires an explicit disposable CZ_UI_TEST_DATA directory.')
    async def fixture_health(self):
        return dict(ready=True, state='test_fixture', model='TEST-ONLY', message='TEST FIXTURE — no GPU execution')
    Provider.health=fixture_health
    app=create_app(Settings(data_dir=Path(target),model_url='http://127.0.0.1:18999/v1',model='TEST-ONLY'),BrowserFixture)
    uvicorn.run(app,host='127.0.0.1',port=8792)
