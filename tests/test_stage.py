import hashlib
import io
import zipfile
from fastapi.testclient import TestClient
from cizheng_precheck.api import create_app
from cizheng_precheck.provider import Provider
from cizheng_precheck.stage import readiness_snapshot
from cizheng_precheck.store import Store
from cizheng_precheck.knowledge import Knowledge
from test_core import wait


def test_collector_page_has_journey_without_setup_or_presets(client):
    html=client.get('/').text
    for banned in ['安装本地模型','demo-list','demo-mode','setup-button','三种预检情形','/operator','met-48450']:
        assert banned not in html
    assert all(x in html for x in ['添加照片','确认预检','分析核查','一页报告'])
    script=client.get('/assets/app.js').text
    assert "api('/api/demos'" not in script and "mode:'analyze',force_new:true" in script
    assert '已保存报告' in script


def test_operator_is_local_and_auth_protected(settings):
    settings.access_token='operator-test'
    with TestClient(create_app(settings),client=('192.168.1.9',12345)) as c:
        assert c.get('/operator').status_code==403
        assert c.get('/api/operator/photos.zip',headers={'Authorization':'Bearer operator-test'}).status_code==403
    with TestClient(create_app(settings)) as c:
        assert c.get('/api/operator/readiness').status_code==401
        assert c.get('/api/operator/photos.zip').status_code==401
        assert '设备准备台' in c.get('/operator').text


def test_photo_package_keeps_real_original_bytes(client,settings):
    response=client.get('/api/operator/photos.zip');assert response.status_code==200
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        names=[n for n in z.namelist() if n.endswith('.jpg')]
        assert len(names)==9
        for n in names:
            assert z.read(n)==(settings.knowledge_dir/'photos'/n.split('/')[-1]).read_bytes()
        assert 'Public Domain / CC0' in z.read('使用说明.txt').decode()


def test_service_health_or_catalog_report_cannot_pass_rehearsal(client,monkeypatch):
    async def healthy(self):return dict(ready=True,message='fixture transport healthy',model='fixture')
    monkeypatch.setattr(Provider,'health',healthy)
    case=client.post('/api/demos',json={}).json()
    j=client.post('/api/cases/'+case['id']+'/jobs',json={'mode':'catalog'}).json()
    wait(client,j['id'])
    r=client.get('/api/operator/readiness').json()
    assert not r['ready'] and not r['backups']
    assert next(c for c in r['checks'] if c['key']=='model')['ok']
    assert not next(c for c in r['checks'] if c['key']=='rehearsal')['ok']


def test_rehearsal_requires_current_session_matching_model_and_intact_files(client,settings):
    # A constructed audit record tests the gate only; it is never shipped as a real model result.
    case=client.post('/api/demos',json={}).json()
    j=client.post('/api/cases/'+case['id']+'/jobs',json={'mode':'catalog'}).json();wait(client,j['id'])
    store=Store(settings.data_dir);j=store.get(j['id']);report=store.get(j['id']+'_report')
    settings.model='test-audit-model'
    j.update(mode='analyze',model_calls=[dict(purpose='observe',status='ok',location='local',model=settings.model,image_count=3)])
    report['model_executed']=True;store.put('job',j);store.put('report',report)
    knowledge=Knowledge(settings.knowledge_dir,settings.data_dir/'cache')
    def snap(boot='2000-01-01'):
        return readiness_snapshot(store,knowledge,settings,{'ready':True,'message':'test audit'},boot)
    assert snap()['ready']
    assert not snap('2100-01-01')['ready']  # old reports remain backups, not fresh rehearsal
    settings.model='different';assert not snap()['backups'];settings.model='test-audit-model'
    pdf=store.case_dir(case['id'])/(j['id']+'.pdf');pdf.write_bytes(pdf.read_bytes()+b'changed')
    assert not snap()['ready'] and not snap()['backups']
