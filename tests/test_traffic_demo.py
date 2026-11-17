import json
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from preauth.api.schemas import PreauthRequest

scripts = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(scripts))
spec = importlib.util.spec_from_file_location('demo_under_test',scripts/'traffic_demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


@pytest.mark.parametrize('scenario',['approval','rejection','exception','clarification','injection','unsupported','changed_cost'])
def test_every_demo_scenario_is_valid_synthetic_input(scenario):
    request = PreauthRequest.model_validate(demo.claim_payload('a'*32,scenario))
    assert request.policy_number.startswith('SYN-DEMO-')
    assert request.procedure_code == 'DEMO-AAAAAAAA'


def test_unrelated_cases_cannot_be_reviewed(tmp_path,monkeypatch):
    monkeypatch.setattr(demo,'CONTROL',tmp_path)
    run=demo.Demo(1,5,1)
    try:
        with pytest.raises(AssertionError,match='unrelated'):
            run.decide({'id':'not-created-by-this-run'},'approved')
    finally:
        run.cleanup()


def test_low_memory_pauses_admission_then_stops(tmp_path,monkeypatch):
    monkeypatch.setattr(demo,'CONTROL',tmp_path)
    clock=[0]
    monkeypatch.setattr(demo.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(demo.psutil,'virtual_memory',lambda:SimpleNamespace(total=16*2**30,available=1*2**30))
    run=demo.Demo(5,5,1)
    try:
        clock[0]=1
        assert not run.guard()
        clock[0]=32
        with pytest.raises(demo.DemoStopped,match='RAM'):
            run.guard()
    finally:
        run.cleanup()


def test_clarification_resubmits_owned_revision_without_exception_note(tmp_path,monkeypatch):
    monkeypatch.setattr(demo,'CONTROL',tmp_path)
    run=demo.Demo(5,5,10)
    run.created.append('owned')
    calls=[]
    monkeypatch.setattr(run,'guard',lambda *a,**k:True)
    monkeypatch.setattr(run,'pause',lambda *a:None)
    monkeypatch.setattr(run,'submit',lambda *a:{'id':'owned','revision':1,'status':'awaiting_review'})
    def request(role,method,path,body=None):
        calls.append((role,path,body))
        return {'id':'owned','revision':2,'status':'processing'}
    monkeypatch.setattr(run,'request',request)
    monkeypatch.setattr(run,'wait_assessment',lambda case:{**case,'status':'approved'})
    run.process('clarification')
    assert calls[0][0]=='reviewer' and calls[0][2]['outcome']=='information_requested'
    assert calls[1][0]=='hospital' and calls[1][1]=='/cases/owned/resubmit?revision=1'
    assert calls[1][2]['request']['notes']==''
    run.cleanup()


def test_cleanup_disables_only_recorded_run_precedents(tmp_path,monkeypatch):
    monkeypatch.setattr(demo,'CONTROL',tmp_path)
    run=demo.Demo(5,5,10)
    run.precedents={'own-approval','own-rejection'}
    seen=[]
    monkeypatch.setattr(run,'request',lambda role,method,path:seen.append(path))
    run.cleanup()
    assert set(seen)=={'/precedents/own-approval/disable','/precedents/own-rejection/disable'}
    assert not json.loads((run.output/'summary.json').read_text())['cleanup_failed_precedents']
