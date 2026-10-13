import asyncio
import io
import json
from fastapi.testclient import TestClient
from pypdf import PdfReader
from cizheng_precheck.api import create_app
from cizheng_precheck.provider import ModelFailure
from test_core import wait,fixture_analysis


class TestProvider:
    """Explicit test-only protocol fixture, never installed as a production mode."""
    __test__ = False
    def __init__(self,settings): self.calls=[]
    async def observe(self,photos,folder):
        a=fixture_analysis()
        # Demo has three photos; provide a third grounded observation for protocol coverage.
        a['observations'].append(dict(a['observations'][1],id='O3',photo_id='P3'))
        self.calls.append({'purpose':'observe','status':'test_fixture'})
        return a
    async def compare(self,observations,references,claim,images=()):
        ref=next(r for r in references if r['id']=='MET-48450')
        return {'comparisons':[{'id':'C1','observation_ids':['O1'],'reference_id':ref['id'],'quote':'gold lacquer repairs',
                'relation':'compatible','claim_relevance':'style_only','explanation':'观察到的补片同馆方修补记录相容，仍需实物确认。','alternative':'外观相似的补片也可能是其他修复材料。'}]}
    async def review(self,*args,**kwargs): return {'items':[{'comparison_id':'C1','verdict':'supported','reason':'描述范围保持在修补比对，没有推断真伪。'}]}


def test_visual_contract_full_pipeline(settings):
    settings.model_url='http://127.0.0.1:8000/v1';settings.model='test-only'
    with TestClient(create_app(settings,TestProvider)) as c:
        c.headers['x-cz-csrf']=c.get('/api/status').json()['csrf']
        case=c.post('/api/demos',json={}).json()
        job=c.post('/api/cases/'+case['id']+'/jobs',json={'mode':'analyze'}).json()
        assert wait(c,job['id'])['status']=='complete'
        report=c.get('/api/jobs/'+job['id']+'/report').json()
        assert report['score']['value']==3
        assert report['audit']['comparisons'][0]['citation_verified']
        assert len(PdfReader(io.BytesIO(c.get('/api/jobs/'+job['id']+'/report.pdf').content)).pages)==1


def test_model_failure_does_not_fabricate_report(settings):
    class Broken(TestProvider):
        async def observe(self,*args): raise ModelFailure('视觉服务不可用')
    settings.model_url='http://127.0.0.1:8000/v1';settings.model='test-only'
    with TestClient(create_app(settings,Broken)) as c:
        c.headers['x-cz-csrf']=c.get('/api/status').json()['csrf']
        case=c.post('/api/demos',json={}).json()
        job=c.post('/api/cases/'+case['id']+'/jobs',json={'mode':'analyze'}).json()
        assert wait(c,job['id'])['status']=='failed'
        assert c.get('/api/jobs/'+job['id']+'/report').status_code==404
        assert c.get('/api/cases/'+case['id']).status_code==200


def test_auth_protects_photos_and_reports(settings):
    settings.access_token='test-access-secret'
    with TestClient(create_app(settings)) as c:
        assert c.get('/api/status').status_code==401
        assert c.get('/api/demo-photos/met-48450-01.jpg').status_code==401
        assert c.post('/api/login',json={'token':'wrong'}).status_code==401
        assert c.post('/api/login',json={'token':'test-access-secret'}).status_code==200
        assert c.get('/api/status').status_code==200


def test_cancel_keeps_case_but_never_finishes_report(settings):
    class Slow(TestProvider):
        async def observe(self,*args):
            await asyncio.sleep(10)
    settings.model_url='http://127.0.0.1:8000/v1';settings.model='test-only'
    with TestClient(create_app(settings,Slow)) as c:
        c.headers['x-cz-csrf']=c.get('/api/status').json()['csrf']
        case=c.post('/api/demos',json={}).json()
        job=c.post('/api/cases/'+case['id']+'/jobs',json={'mode':'analyze'}).json()
        c.post('/api/jobs/'+job['id']+'/cancel',json={})
        assert wait(c,job['id'])['status']=='cancelled'
        assert c.get('/api/cases/'+case['id']).status_code==200
        assert c.get('/api/jobs/'+job['id']+'/report').status_code==404


def test_total_job_timeout(settings):
    class Slow(TestProvider):
        async def observe(self,*args): await asyncio.sleep(10)
    settings.model_url='http://127.0.0.1:8000/v1';settings.model='test-only';settings.job_timeout=.1
    with TestClient(create_app(settings,Slow)) as c:
        c.headers['x-cz-csrf']=c.get('/api/status').json()['csrf']
        case=c.post('/api/demos',json={}).json()
        job=c.post('/api/cases/'+case['id']+'/jobs',json={'mode':'analyze'}).json()
        finished=wait(c,job['id'])
        assert finished['status']=='failed' and '超时' in finished['stage']
        assert c.get('/api/jobs/'+job['id']+'/report').status_code==404


def test_modified_original_stops_evidence_export(settings):
    with TestClient(create_app(settings)) as c:
        c.headers['x-cz-csrf']=c.get('/api/status').json()['csrf']
        case=c.post('/api/demos',json={}).json()
        job=c.post('/api/cases/'+case['id']+'/jobs',json={'mode':'catalog'}).json()
        assert wait(c,job['id'])['status']=='complete'
        path=settings.data_dir/'cases'/case['id']/'P1.original'
        path.write_bytes(path.read_bytes()+b'changed')
        assert c.get('/api/jobs/'+job['id']+'/evidence.zip').status_code==409


def test_visual_mode_does_not_take_scenario_grade_or_catalog_cache(settings):
    settings.model_url='http://127.0.0.1:8000/v1';settings.model='test-only'
    with TestClient(create_app(settings,TestProvider)) as c:
        c.headers['x-cz-csrf']=c.get('/api/status').json()['csrf']
        case=c.post('/api/demos',json={'object_id':51185}).json()
        catalog=c.post('/api/cases/'+case['id']+'/jobs',json={'mode':'catalog'}).json()
        assert wait(c,catalog['id'])['status']=='complete'
        assert c.get('/api/jobs/'+catalog['id']+'/report').json()['score']['value']==4
        visual=c.post('/api/cases/'+case['id']+'/jobs',json={'mode':'analyze'}).json()
        assert visual['id']!=catalog['id'] and wait(c,visual['id'])['status']=='complete'
        report=c.get('/api/jobs/'+visual['id']+'/report').json()
        # Protocol fixture reports a repair, so the rule yields 3, not scenario's 4.
        assert report['mode']=='visual_precheck' and report['score']['value']==3
        assert report['runtime']['model_calls'][0]['purpose']=='observe'
