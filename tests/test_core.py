import io
import json
import time
import hashlib
import zipfile
from pathlib import Path
import pytest
from PIL import Image
from pypdf import PdfReader
from cizheng_precheck.config import local_endpoint
from cizheng_precheck.imaging import inspect_photo
from cizheng_precheck.knowledge import Knowledge, validate_comparisons
from cizheng_precheck.schemas import Observation
from cizheng_precheck.policy import decide
from cizheng_precheck.store import Store
from conftest import photo_bytes


def wait(client, job_id):
    for _ in range(150):
        job = client.get('/api/jobs/'+job_id).json()
        if job['status'] not in ('running','queued'):
            return job
        time.sleep(.03)
    raise AssertionError('job did not finish')


def test_catalog_full_journey_and_export(client):
    case = client.post('/api/demos',json={'object_id':48450}).json()
    assert len(case['photos'])==3
    response = client.post('/api/cases/'+case['id']+'/jobs',json={'mode':'catalog'})
    assert response.status_code==202
    job = wait(client,response.json()['id'])
    assert job['status']=='complete',job
    report = client.get('/api/jobs/'+job['id']+'/report').json()
    assert report['score']['value']==3
    assert report['authenticity_probability'] is None
    assert report['model_executed'] is False
    assert report['identity_verified'] is False
    assert report['audit']['online']['status']=='disabled'
    pdf=client.get('/api/jobs/'+job['id']+'/report.pdf').content
    assert hashlib.sha256(pdf).hexdigest()==report['pdf_sha256']
    reader=PdfReader(io.BytesIO(pdf))
    assert len(reader.pages)==1
    text=reader.pages[0].extract_text()
    assert '送检关注评分' in text and '金漆修补' in text
    archive=client.get('/api/jobs/'+job['id']+'/evidence.zip').content
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for p in case['photos']:
            assert hashlib.sha256(z.read('originals/'+p['original_file'])).hexdigest()==p['sha256']


@pytest.mark.parametrize('identifier,grade,opinion',[(48607,2,'常规核验'),(51185,4,'年代说法冲突')])
def test_catalog_grade_follows_explicit_evidence(client,identifier,grade,opinion):
    case=client.post('/api/demos',json={'object_id':identifier}).json()
    job=client.post('/api/cases/'+case['id']+'/jobs',json={'mode':'catalog'}).json()
    assert wait(client,job['id'])['status']=='complete'
    r=client.get('/api/jobs/'+job['id']+'/report').json()
    assert r['score']['value']==grade and opinion in r['opinion']
    assert r['authenticity_probability'] is None and not r['model_executed']
    if identifier==51185:
        assert '体验设定' in r['claim'] and '19th century' in r['reasons'][1]['body']


def test_no_model_refuses_new_visual_analysis(client):
    case=client.post('/api/demos',json={'object_id':48450}).json()
    r=client.post('/api/cases/'+case['id']+'/jobs',json={'mode':'analyze'})
    assert r.status_code==409


def test_upload_and_duplicate_rejection(client):
    data=photo_bytes()
    r=client.post('/api/cases',data={'metadata':json.dumps({'name':'我的青釉碗'})},files=[('photos',('x.jpg',data,'image/jpeg'))])
    assert r.status_code==200,r.text
    assert r.json()['photos'][0]['sha256']==hashlib.sha256(data).hexdigest()
    r=client.post('/api/cases',files=[('photos',('x.jpg',data,'image/jpeg')),('photos',('y.jpg',data,'image/jpeg'))])
    assert r.status_code==422 and '重复' in r.text


def test_invalid_image_not_stored(client):
    before=len(client.get('/api/cases').json())
    r=client.post('/api/cases',files=[('photos',('wrong.jpg',b'not-image','image/jpeg'))])
    assert r.status_code==422
    assert len(client.get('/api/cases').json())==before


def test_csrf_and_cross_origin(client):
    assert client.post('/api/demos',json={},headers={'x-cz-csrf':'bad'}).status_code==403
    assert client.post('/api/demos',json={},headers={'origin':'https://attacker.example'}).status_code==403
    assert client.get('/api/status',headers={'host':'attacker.example'}).status_code==400


@pytest.mark.parametrize('url',['https://api.example.com/v1','http://169.254.169.254/v1','http://0.0.0.0/v1','http://localhost:8000/v1?key=secret','http://name:pass@127.0.0.1:8000/v1'])
def test_visual_endpoint_rejects_remote_or_unsafe(url):
    with pytest.raises(ValueError): local_endpoint(url)


def test_local_endpoint():
    assert local_endpoint('http://127.0.0.1:8000/v1/')=='http://127.0.0.1:8000/v1'


def test_reencoded_match_is_only_a_candidate(settings):
    k=Knowledge(settings.knowledge_dir,settings.data_dir/'cache')
    data=photo_bytes()
    p,_=inspect_photo(data,'P1')
    match=k.origins([p])[0]
    assert match['match']=='exact_file' and not match['identity_verified']
    im=Image.open(io.BytesIO(data));b=io.BytesIO();im.resize((500,400)).save(b,'JPEG',quality=70)
    p,_=inspect_photo(b.getvalue(),'P1')
    assert all(m['match']=='visual_candidate' for m in k.origins([p]))


def test_bad_bounding_box():
    with pytest.raises(ValueError):
        Observation(id='O1',photo_id='P1',dimension='修补',description='表面有一处补片',location='口沿',bbox=[.7,.2,.3,.4],kind='repair_candidate',alternative='也可能为反光')


def test_citation_rejection():
    observations=[{'id':'O1'}]
    refs=[{'id':'R1','excerpt':'The ceramic bowl has gold lacquer repairs.'}]
    base={'id':'C1','observation_ids':['O1'],'reference_id':'R1','quote':'gold lacquer repairs','claim_relevance':'style_only'}
    ok,bad=validate_comparisons([base],observations,refs)
    assert len(ok)==1 and not bad
    for edited in [dict(base,quote='this is fake'),dict(base,reference_id='invented'),dict(base,observation_ids=['O9'])]:
        ok,bad=validate_comparisons([edited],observations,refs)
        assert not ok and len(bad)==1


def fixture_analysis():
    return {'object_name':'青釉碗','object_consistency':'consistent','ceramic':'yes','visible_roles':['overall','base'],
            'observations':[{'id':'O1','photo_id':'P1','dimension':'修补','description':'口沿见黄色补片','location':'口沿','bbox':[0,0,1,1],'kind':'repair_candidate','alternative':'可能为修复材料'},
                            {'id':'O2','photo_id':'P2','dimension':'胎釉','description':'底足可见露胎','location':'底足','bbox':[0,0,1,1],'kind':'feature','alternative':'颜色受光线影响'}],
            'search_terms':['celadon','bowl'],'missing_views':[]}


def case_for_rules():
    return {'id':'case_a','name':'碗','source':'持有人提供','photos':[{'id':'P1','issues':[]},{'id':'P2','issues':[]}],'claim':'被称为某一年代的原作'}


def test_repair_is_not_fake_or_probability():
    r=decide(case_for_rules(),{'id':'job_a'},fixture_analysis(),[],{'items':[]},[],[])
    assert r['score']['value']==3 and r['authenticity_probability'] is None
    assert '仿品' not in r['opinion']


def test_style_difference_does_not_raise_to_four():
    comparison={'id':'C1','observation_ids':['O1'],'reference_id':'R1','quote':'q','relation':'conflict','claim_relevance':'style_only','explanation':'器型风格有差异','alternative':'器物的用途可能不同'}
    r=decide(case_for_rules(),{'id':'job_a'},fixture_analysis(),[comparison],{'items':[{'comparison_id':'C1','verdict':'supported'}]},[{'id':'R1','source_group':'one'}],[])
    assert r['score']['value']==3


def test_low_quality_and_mixed_object_abstain():
    case=case_for_rules();case['photos'][0]['issues']=['画面信息偏少']
    assert decide(case,{'id':'job_a'},fixture_analysis(),[],{'items':[]},[],[])['score']['value'] is None
    analysis=fixture_analysis();analysis['object_consistency']='mixed'
    assert decide(case_for_rules(),{'id':'job_a'},analysis,[],{'items':[]},[],[])['score']['value'] is None


def test_same_institution_does_not_create_independent_sources():
    base={'relation':'conflict','claim_relevance':'direct','explanation':'主张存在矛盾','alternative':'仍需实物复核','quote':'actual'}
    comparisons=[dict(base,id='C1',observation_ids=['O1'],reference_id='R1'),dict(base,id='C2',observation_ids=['O2'],reference_id='R2')]
    review={'items':[{'comparison_id':c['id'],'verdict':'supported'} for c in comparisons]}
    refs=[{'id':'R1','source_group':'metmuseum'},{'id':'R2','source_group':'metmuseum'}]
    r=decide(case_for_rules(),{'id':'job_a'},fixture_analysis(),comparisons,review,refs,[])
    assert r['score']['value']==4


def test_restart_marks_interrupted(settings):
    store=Store(settings.data_dir)
    store.put('job',{'id':'job_abc','status':'running'})
    store.recover()
    assert store.get('job_abc')['status']=='interrupted'


def test_background_reference_cannot_support_direct_conflict():
    item={'id':'C1','observation_ids':['O1'],'reference_id':'R1','quote':'Longquan ware','claim_relevance':'direct'}
    good,bad=validate_comparisons([item],[{'id':'O1'}],[{'id':'R1','excerpt':'Longquan ware','applicability':'context_only'}])
    assert not good and bad[0]['reason']=='reference_not_comparable'


def test_no_path_traversal(client):
    assert client.get('/api/demo-photos/secrets.json').status_code==404
    assert client.get('/api/jobs/does-not-exist/report.pdf').status_code==404
