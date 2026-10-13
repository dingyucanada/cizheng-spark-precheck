import asyncio
import subprocess
from pathlib import Path
import httpx
import pytest
from cizheng_precheck.provider import Provider


def test_install_entry_really_includes_local_model_and_real_acceptance():
    root=Path(__file__).resolve().parents[1]
    body=(root/'scripts/install-spark.sh').read_text()
    ordered=['scripts/bootstrap-spark.sh','scripts/download-model.py','scripts/start-model.sh',
             'scripts/wait-model.py','scripts/probe-model.py','scripts/start-app.py','scripts/acceptance.py --visual']
    positions=[body.index(s) for s in ordered]
    assert positions==sorted(positions)
    plan=subprocess.check_output(['bash',str(root/'scripts/install-spark.sh'),'--print-plan'],text=True)
    assert 'Qwen/Qwen3-VL-8B-Instruct' in plan and '真实双图' in plan


@pytest.mark.parametrize('payload,expected',[({'data':[{'id':'Qwen/Qwen3-VL-8B-Instruct'}]},'ready'),({'data':[{'id':'wrong'}]},'model_mismatch')])
def test_health_checks_actual_model_id(settings,monkeypatch,payload,expected):
    settings.model_url='http://127.0.0.1:8000/v1';settings.model='Qwen/Qwen3-VL-8B-Instruct';settings.model_key='never-display-this'
    def respond(request):
        assert request.url.path=='/v1/models'
        assert request.headers['authorization']=='Bearer never-display-this'
        return httpx.Response(200,json=payload)
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    result=asyncio.run(Provider(settings).health())
    assert result['state']==expected and 'never-display-this' not in str(result)


def test_health_configuration_not_readiness(settings,monkeypatch):
    settings.model_url='http://127.0.0.1:8000/v1';settings.model='vision'
    def fail(request): raise httpx.ConnectError('private secret should not surface')
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(fail),**kw))
    result=asyncio.run(Provider(settings).health())
    assert result['ready'] is False and result['state']=='unavailable' and 'secret' not in str(result)
