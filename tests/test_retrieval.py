import asyncio
import json
import httpx
from cizheng_precheck.knowledge import Knowledge


def test_one_provider_failure_does_not_remove_second_source(settings,monkeypatch):
    seen=[]
    def respond(request):
        seen.append(str(request.url))
        if request.url.host=='collectionapi.metmuseum.org':
            return httpx.Response(403)
        return httpx.Response(200,json={'data':[{'id':123,'title':'Bowl','medium_display':'Porcelain with celadon glaze','date_display':'13th century','main_reference_number':'A1','is_public_domain':True,'image_id':'abc-123'}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    knowledge=Knowledge(settings.knowledge_dir,settings.data_dir/'cache')
    refs,status=asyncio.run(knowledge.online_search(['celadon','bowl','collector-name-private']))
    assert any(r['id']=='AIC-123' for r in refs)
    assert status['status']=='ok'
    assert any(p.get('http_status')==403 for p in status['providers'])
    assert all('collector-name-private' not in url for url in seen)


def test_unapproved_reference_url_never_requested(settings,monkeypatch):
    seen=[]
    def respond(request):seen.append(str(request.url));return httpx.Response(200)
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    knowledge=Knowledge(settings.knowledge_dir,settings.data_dir/'cache')
    results=asyncio.run(knowledge.reference_images([{'id':'EVIL','image_url':'http://169.254.169.254/secret','public_domain':True}],online=True))
    assert not results and not seen
