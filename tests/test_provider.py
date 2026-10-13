import asyncio
import json
import httpx
import pytest
from cizheng_precheck.provider import Provider,ModelFailure
from cizheng_precheck.schemas import ObservationSet,ReviewSet
from test_core import fixture_analysis


def test_http_visual_adapter_transmits_images_and_rejects_orphan_observations(settings,tmp_path,monkeypatch):
    from conftest import photo_bytes
    from cizheng_precheck.imaging import inspect_photo
    settings.model_url='http://127.0.0.1:8000/v1';settings.model='test-contract'
    photos=[]
    for i in (1,2):
        p,preview=inspect_photo(photo_bytes(view=i),f'P{i}')
        (tmp_path/p['preview_file']).write_bytes(preview);photos.append(p)
    seen=[]
    def respond(request):
        body=json.loads(request.content);seen.append(body)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(fixture_analysis(),ensure_ascii=False)}}],'usage':{'total_tokens':100}})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    result=asyncio.run(Provider(settings).observe(photos,tmp_path))
    assert result['object_name']=='青釉碗'
    images=[c for c in seen[0]['messages'][1]['content'] if c['type']=='image_url']
    assert len(images)==2 and all(c['image_url']['url'].startswith('data:image/jpeg;base64,') for c in images)
    assert '馆藏号' not in seen[0]['messages'][1]['content'][0]['text']


def test_cloud_text_packet_excludes_private_observations_and_sources(settings,monkeypatch):
    settings.text_url='https://text.example/v1';settings.text_model='test';settings.cloud_text=True
    seen=[]
    def respond(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"items":[]}'}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    references=[{'id':'R1','excerpt':'PUBLIC','public_record':True},{'id':'R2','excerpt':'PRIVATE_SOURCE','public_record':False}]
    comparisons=[{'id':'C1','quote':'PUBLIC','reference_id':'R1','relation':'compatible','explanation':'PRIVATE_OBSERVATION'},
                 {'id':'C2','quote':'PRIVATE_SOURCE','reference_id':'R2','relation':'conflict','explanation':'PRIVATE_OBSERVATION'}]
    asyncio.run(Provider(settings).review([{'description':'PRIVATE_OBSERVATION'}],comparisons,references,cloud=True))
    serialized=json.dumps(seen)
    assert 'PUBLIC' in serialized and 'PRIVATE_SOURCE' not in serialized and 'PRIVATE_OBSERVATION' not in serialized
    assert 'image_url' not in serialized


def test_bad_json_only_retries_once(settings,monkeypatch):
    settings.model_url='http://127.0.0.1:8000/v1';settings.model='test'
    count=[]
    def respond(request):
        count.append(1)
        return httpx.Response(200,json={'choices':[{'message':{'content':'not json'}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    provider=Provider(settings)
    with pytest.raises(ModelFailure):asyncio.run(provider.complete('observe','system',{},ObservationSet))
    assert len(count)==2 and provider.calls[0]['status']=='failed'


def test_definitive_authenticity_language_rejected():
    a=fixture_analysis();a['observations'][0]['description']='真品率100%，确认为真品'
    with pytest.raises(ValueError): ObservationSet.model_validate(a)
