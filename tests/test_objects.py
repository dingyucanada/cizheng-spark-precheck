import copy
import io
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
import pytest
from pypdf import PdfReader
from conftest import photo_bytes
from test_core import wait
from cizheng_precheck.store import Store,uid,now
from cizheng_precheck.imaging import inspect_photo
from cizheng_precheck.schemas import CaseInput


def test_demo_open_reuses_object_and_report(client):
    first=client.post('/api/demos',json={'object_id':48450}).json()
    job=client.post('/api/cases/'+first['id']+'/jobs',json={'mode':'catalog'}).json()
    assert wait(client,job['id'])['status']=='complete'
    for _ in range(4):
        again=client.post('/api/demos',json={'object_id':48450}).json()
        same=client.post('/api/cases/'+again['id']+'/jobs',json={'mode':'catalog'}).json()
        assert again['id']==first['id'] and same['id']==job['id']
    assert len(client.get('/api/cases').json())==1
    assert client.get('/api/cases').json()[0]['report_count']==1
    newer=client.post('/api/cases/'+first['id']+'/jobs',json={'mode':'catalog','force_new':True}).json()
    assert newer['id']!=job['id'] and wait(client,newer['id'])['status']=='complete'
    records=client.get('/api/cases').json()
    assert len(records)==1 and records[0]['report_count']==2


def test_reordered_upload_same_object_changed_claim_new_report(client):
    def upload(order,claim):
        return client.post('/api/cases',data={'metadata':json.dumps({'name':'我的碗','claim':claim})},
            files=[('photos',(f'{n}.jpg',photo_bytes(view=n),'image/jpeg')) for n in order]).json()
    a=upload([1,3],'核对修补');b=upload([3,1],'核对底足')
    assert a['id']==b['id'] and b['claim']=='核对底足'
    assert len(client.get('/api/cases').json())==1
    assert a['photos'][0]['sha256']==b['photos'][0]['sha256']


def test_concurrent_intake_deduplicates_atomically(settings):
    store=Store(settings.data_dir);store.reconcile_cases()
    raw=photo_bytes();p,preview=inspect_photo(raw,'P1')
    def submit(_):return store.save_case(CaseInput(),[(p,raw,preview)])['id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids=list(pool.map(submit,range(10)))
    assert len(set(ids))==1 and len(store.cases())==1


def test_old_duplicate_migration_keeps_reports_and_files(settings,client):
    first=client.post('/api/demos',json={'object_id':48450}).json()
    store=Store(settings.data_dir)
    second=copy.deepcopy(first);second['id']=uid('case_');second['created_at']=now()
    shutil.copytree(store.case_dir(first['id']),store.root/'cases'/second['id'])
    store.put('case',second)
    legacy_job={'id':uid('job_'),'case_id':second['id'],'status':'complete','created_at':now()}
    store.put('job',legacy_job)
    store.reconcile_cases();store.reconcile_cases()
    assert len(store.cases())==1
    assert store.canonical(second['id'])['id']==first['id']
    assert store.get(second['id'])['merged_into']==first['id']
    assert store.jobs_for_case(first['id'])[0]['id']==legacy_job['id']
    assert (store.case_dir(second['id'])/second['photos'][0]['original_file']).read_bytes()==photo_bytes()
    assert client.get('/api/cases/'+second['id']+'/photos/P1').status_code==200


def test_changed_input_claim_does_not_reuse_old_report(client):
    case=client.post('/api/demos',json={'object_id':51185}).json()
    job=client.post('/api/cases/'+case['id']+'/jobs',json={'mode':'catalog'}).json()
    assert wait(client,job['id'])['status']=='complete'
    report=client.get('/api/jobs/'+job['id']+'/report').json();assert report['score']['value']==4
    changed=client.post('/api/cases',data={'metadata':json.dumps({'name':'茶壶','claim':'核对清代资料','source':'公开馆藏'})},
        files=[('photos',(f'{n}.jpg',photo_bytes(51185,n),'image/jpeg')) for n in [1,2,3]]).json()
    assert changed['id']==case['id'] and 'example' not in changed
    fresh=client.post('/api/cases/'+case['id']+'/jobs',json={'mode':'catalog'}).json()
    assert fresh['id']!=job['id'] and wait(client,fresh['id'])['status']=='complete'
    current=client.get('/api/jobs/'+fresh['id']+'/report').json()
    assert current['score']['value']==2
    assert client.get('/api/jobs/'+job['id']+'/report').json()==report
    reopened=client.post('/api/demos',json={'object_id':51185}).json()
    assert reopened['claim']=='核对清代资料'  # never reset personal edits when opening a card


def test_mixed_catalog_images_still_abstain(client):
    case=client.post('/api/cases',files=[('photos',('a.jpg',photo_bytes(48450),'image/jpeg')),('photos',('b.jpg',photo_bytes(51185),'image/jpeg'))]).json()
    job=client.post('/api/cases/'+case['id']+'/jobs',json={'mode':'catalog'}).json();wait(client,job['id'])
    assert client.get('/api/jobs/'+job['id']+'/report').json()['score']['value'] is None


def test_all_scenarios_pdf_is_one_page(client):
    results=[]
    for identifier in [48450,48607,51185]:
        case=client.post('/api/demos',json={'object_id':identifier}).json()
        job=client.post('/api/cases/'+case['id']+'/jobs',json={'mode':'catalog'}).json()
        assert wait(client,job['id'])['status']=='complete'
        results.append(client.get('/api/jobs/'+job['id']+'/report').json()['opinion'])
        pdf=client.get('/api/jobs/'+job['id']+'/report.pdf').content
        assert len(PdfReader(io.BytesIO(pdf)).pages)==1
    assert len(set(results))==3
