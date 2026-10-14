"""Legacy retry regression names, now using the portable command-line fixture."""
from test_portable_launcher import fixture, run, calls, REV
from pathlib import Path


def test_failed_install_retries_without_recreating_runtime(fixture):
 base,env,_=fixture;env['TEST_FAIL_NUMERIC_ONCE']='1'
 first=run(fixture);assert first.returncode==1 and 'Dependency installation failed' in first.stdout
 origin=(base/'budget_origin.json').read_bytes()
 second=run(fixture);assert second.returncode==0,second.stdout+second.stderr
 assert (base/'budget_origin.json').read_bytes()==origin
 assert len(calls(Path(env['TEST_ROOT'])/'venv_calls.jsonl'))==1
 assert len(calls(Path(env['TEST_ROOT'])/'pip_calls.jsonl'))==2
 third=run(fixture);assert third.returncode==0 and len(calls(Path(env['TEST_ROOT'])/'pip_calls.jsonl'))==2


def test_wrong_immutable_checkout_blocks_before_install(fixture):
 _,env,_=fixture;env['TEST_HEAD']='c'*40;r=run(fixture)
 assert r.returncode==2 and 'Code revision mismatch' in r.stdout
 assert not (Path(env['TEST_ROOT'])/'pip_calls.jsonl').exists()


def test_malformed_revision_never_accesses_commands(fixture):
 base,_,_=fixture;r=run(fixture,'--revision','not-a-commit')
 assert r.returncode==2 and not base.exists()
