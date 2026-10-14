import hashlib
import importlib.util
import io
import json
from pathlib import Path
import ssl
import subprocess
import sys
import time
import urllib.request

import pytest

PATH = Path(__file__).with_name('restore_source_official_lampx_v2.py')
spec = importlib.util.spec_from_file_location('official_source_restore_v2',PATH)
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def row(name='A01T.mat',data=b'frozen-source-bytes'):
    return {'filename':name,'url':'https://bnci-horizon-2020.eu/database/data-sets/001-2014/'+name,
            'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


class Response(io.BytesIO):
    status=200
    def __init__(self,data,url,headers=None):
        super().__init__(data);self.url=url;self.headers=headers or {}
    def geturl(self):return self.url


def factory(data=b'frozen-source-bytes',error=None,header=None,url=None,on_open=None):
    class Opener:
        def __init__(self,r):self.r=r
        def open(self,req,timeout):
            assert 0 < timeout <= 30
            if on_open:on_open()
            if error:raise error
            return Response(data,url or self.r['url'],header)
    return Opener


def test_fixed_manifest_matches_frozen_q8_and_historical_urls():
    rows=m.load_manifest(PATH.with_name('source_official_manifest.json'))
    repo=PATH.parents[3]
    frozen=json.loads((repo/'research_runs/Q8-E001/results/source_files.json').read_text())
    byname={Path(r['path']).name:r for r in frozen}
    historical=json.loads((repo/'research_runs/Q15-PREPARATION/BNCI_R2_SOURCE_RECEIPT_20261003.json').read_text())['files']
    urls={r['file_id']:r['official_url'] for r in historical}
    assert len(rows)==18 and sum(r['bytes'] for r in rows)==779873919
    for r in rows:
        assert (r['sha256'],r['bytes'],r['url'])==(byname[r['filename']]['sha256'],byname[r['filename']]['bytes'],urls[r['filename']])


def test_dry_run_has_no_network_or_writes(tmp_path):
    result=subprocess.run([sys.executable,str(PATH),'--data-dir',str(tmp_path/'data'),'--evidence-dir',str(tmp_path/'evidence')],capture_output=True,text=True)
    assert result.returncode==0 and 'MANIFEST_ONLY_NO_NETWORK' in result.stdout
    assert not list(tmp_path.iterdir())


def test_restore_exact_bytes_and_reuse(tmp_path):
    r=row();data=tmp_path/'data';evidence=tmp_path/'evidence'
    m.restore([r],data,evidence,'first',opener_factory=factory(),reserve=0)
    assert (data/'bnci'/r['filename']).read_bytes()==b'frozen-source-bytes'
    assert not list((data/'bnci').glob('*.partial'))
    def forbidden(unused):pytest.fail('Correct cache must not be requested again')
    m.restore([r],data,evidence,'second',opener_factory=forbidden,reserve=0)
    report=json.loads((evidence/'second-transfer.json').read_text())
    assert report['files'][0]['status']=='REUSED_VERIFIED_CACHE'


@pytest.mark.parametrize('payload',[b'wrong--sourcebytes!',b'short',b'frozen-source-bytes-extra'])
def test_wrong_hash_short_oversize_retains_partial_and_receipt(tmp_path,payload):
    data=tmp_path/'data';evidence=tmp_path/'evidence'
    with pytest.raises(ValueError):m.restore([row()],data,evidence,'failed',opener_factory=factory(payload),reserve=0)
    assert not (data/'bnci/A01T.mat').exists()
    partials=list((data/'bnci').glob('.A*.partial'));assert len(partials)==1
    assert partials[0].read_bytes()==payload
    report=json.loads((evidence/'failed-transfer.json').read_text())
    assert report['status']=='FAILED_OR_BLOCKED_SOURCE_RESTORATION' and report['retained_partials']


def test_wrong_existing_later_file_blocks_all_requests_and_preserves_it(tmp_path):
    data=tmp_path/'data';(data/'bnci').mkdir(parents=True)
    bad=data/'bnci/A02T.mat';bad.write_bytes(b'bad cached bytes')
    def forbidden(unused):pytest.fail('All cache checks must precede network')
    with pytest.raises(ValueError):m.restore([row(),row('A02T.mat')],data,tmp_path/'evidence','bad',opener_factory=forbidden,reserve=0)
    assert bad.read_bytes()==b'bad cached bytes'


def test_destination_appearing_during_transfer_is_not_overwritten(tmp_path):
    p=tmp_path/'A01T.mat'
    f=factory(on_open=lambda:p.write_bytes(b'appeared concurrently'))
    with pytest.raises(FileExistsError):m.download_one(row(),tmp_path,'race',time.monotonic()+10,opener_factory=f)
    assert p.read_bytes()==b'appeared concurrently'
    assert len(list(tmp_path.glob('.A*.partial')))==1


@pytest.mark.parametrize('url',[
 'http://bnci-horizon-2020.eu/database/data-sets/001-2014/A01T.mat',
 'https://example.com/database/data-sets/001-2014/A01T.mat',
 'https://bnci-horizon-2020.eu.evil.test/database/data-sets/001-2014/A01T.mat',
 'https://user:password@bnci-horizon-2020.eu/database/data-sets/001-2014/A01T.mat',
 'https://bnci-horizon-2020.eu/database/data-sets/001-2014/A02T.mat',
 'https://bnci-horizon-2020.eu/database/data-sets/001-2014/A01T.mat?redirect=elsewhere',
 'https://bnci-horizon-2020.eu:444/database/data-sets/001-2014/A01T.mat'])
def test_redirect_outside_exact_frozen_https_file_rejected(url):
    redirect=m.OfficialRedirect('A01T.mat')
    with pytest.raises(ValueError):redirect.redirect_request(urllib.request.Request(row()['url']),None,302,'',{},url)


def test_only_exact_original_response_one_hop_allowed():
    r=row();handler=m.OfficialRedirect(r['filename']);req=urllib.request.Request(r['url'])
    dest=m.lampx_url(r['filename'])
    assert handler.redirect_request(req,None,302,'',{'Location':dest},dest).full_url==dest
    with pytest.raises(ValueError,match='one_original'):
        handler.redirect_request(urllib.request.Request(dest),None,302,'',{'Location':dest},dest)


def test_tls_verification_and_no_proxy_credentials():
    opener=m.official_opener(row())
    https=next(h for h in opener.handlers if isinstance(h,urllib.request.HTTPSHandler))
    assert https._context.check_hostname and https._context.verify_mode==ssl.CERT_REQUIRED
    assert not any(isinstance(h,urllib.request.ProxyHandler) and h.proxies for h in opener.handlers)


def test_tls_error_no_retry_and_retained_failure(tmp_path):
    attempts=[]
    f=factory(error=ssl.SSLCertVerificationError('test cert failure'),on_open=lambda:attempts.append(1))
    with pytest.raises(ssl.SSLCertVerificationError):m.restore([row()],tmp_path/'data',tmp_path/'evidence','tls',opener_factory=f,reserve=0)
    assert len(attempts)==1
    report=json.loads((tmp_path/'evidence/tls-transfer.json').read_text())
    assert report['automatic_retries']==0 and report['error_type']=='SSLCertVerificationError'


def test_bad_content_length_never_installs(tmp_path):
    with pytest.raises(ValueError,match='length'):m.download_one(row(),tmp_path,'headers',time.monotonic()+10,opener_factory=factory(header={'Content-Length':'1'}))
    assert not (tmp_path/'A01T.mat').exists()


def test_whole_worker_timeout_terminates_child_and_keeps_log(tmp_path):
    code,timed_out=m.supervise([sys.executable,'-c','import time; print("START",flush=True); time.sleep(30)'],tmp_path/'worker.log',timeout=.3)
    assert code==124 and timed_out
    assert b'START' in (tmp_path/'worker.log').read_bytes()


def test_deadline_prevents_request(tmp_path):
    def forbidden(unused):pytest.fail('Expired deadline must prevent request')
    with pytest.raises(TimeoutError):m.download_one(row(),tmp_path,'late',time.monotonic()-1,opener_factory=forbidden)


def test_low_disk_and_symlink_prevent_network(tmp_path,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=0))
    def forbidden(unused):pytest.fail('No network on unsafe storage')
    with pytest.raises(ValueError,match='disk'):m.restore([row()],tmp_path/'data',tmp_path/'evidence','disk',opener_factory=forbidden,reserve=0)
    (tmp_path/'alias').symlink_to(tmp_path/'data',target_is_directory=True)
    with pytest.raises(ValueError,match='symlink'):m.restore([row()],tmp_path/'alias',tmp_path/'other','link',opener_factory=forbidden,reserve=0)


def test_active_lock_blocks_second_writer(tmp_path):
    with m.data_lock(tmp_path):
        with pytest.raises(RuntimeError,match='active'):
            with m.data_lock(tmp_path):pytest.fail('Second writer acquired same root')


def test_modified_manifest_blocked(tmp_path):
    p=tmp_path/'manifest.json';p.write_text('{}')
    with pytest.raises(ValueError,match='manifest_hash'):m.load_manifest(p)


@pytest.mark.parametrize('suffix',['?token=x','#part','/extra','%00','/../A02T.mat'])
def test_lampx_query_fragment_extra_path_rejected(suffix):
    r=row();dest=m.lampx_url(r['filename'])+suffix
    with pytest.raises(ValueError):m.OfficialRedirect(r['filename']).redirect_request(urllib.request.Request(r['url']),None,302,'',{'Location':dest},dest)


@pytest.mark.parametrize('dest',[
 'http://lampx.tugraz.at/~bci/database/001-2014/A01T.mat',
 'https://lampx.tugraz.at:443/~bci/database/001-2014/A01T.mat',
 'https://lampx.tugraz.at.evil.test/~bci/database/001-2014/A01T.mat',
 'https://user@lampx.tugraz.at/~bci/database/001-2014/A01T.mat',
 'https://lampx.tugraz.at/~bci/database/001-2014/A02T.mat',
 'https://lampx.tugraz.at/~bci/database/001-2014/A01T.gdf',
 'https://lampx.tugraz.at/~bci/database/other/A01T.mat',
 'https://bnci-horizon-2020.eu/database/data-sets/001-2014/A01T.mat'])
def test_nonexact_lampx_destinations_rejected(dest):
    r=row()
    with pytest.raises(ValueError):m.OfficialRedirect(r['filename']).redirect_request(urllib.request.Request(r['url']),None,302,'',{'Location':dest},dest)


def test_direct_lampx_request_or_missing_actual_location_rejected():
    r=row();dest=m.lampx_url(r['filename'])
    with pytest.raises(ValueError):m.OfficialRedirect(r['filename']).redirect_request(urllib.request.Request(dest),None,302,'',{'Location':dest},dest)
    with pytest.raises(ValueError):m.OfficialRedirect(r['filename']).redirect_request(urllib.request.Request(r['url']),None,302,'',{},dest)


def test_mirror_final_response_without_actual_origin_route_blocked(tmp_path):
    with pytest.raises(ValueError,match='verified_origin'):
        m.download_one(row(),tmp_path,'fake',time.monotonic()+10,opener_factory=factory(url=m.lampx_url('A01T.mat')))
    assert not (tmp_path/'A01T.mat').exists()


def test_actual_route_is_recorded_per_requested_file_only(tmp_path):
    requested=[]
    class Opener:
        def __init__(self,r):
            self.r=r;self.source_redirect=m.OfficialRedirect(r['filename'])
        def open(self,req,timeout):
            requested.append(req.full_url)
            dest=m.lampx_url(self.r['filename'])
            self.source_redirect.redirect_request(req,None,302,'',{'Location':dest},dest)
            return Response(b'frozen-source-bytes',dest)
    m.restore([row()],tmp_path/'data',tmp_path/'evidence','v2',opener_factory=Opener,reserve=0)
    report=json.loads((tmp_path/'evidence/v2-transfer.json').read_text())
    assert requested==[row()['url']]
    assert set(report['actual_response_routes'])=={'A01T.mat'}
    assert report['files'][0]['response_route']['hops'][0]['http_status']==302
    assert report['files'][0]['sha256']==row()['sha256']
    assert report['old_failure_root_cause_resolved'] is False


def prior_fixture(tmp_path):
    data=tmp_path/'data';(data/'bnci').mkdir(parents=True)
    evidence=tmp_path/'evidence';evidence.mkdir()
    fixtures=PATH.parent/'prior_failure_20261014T105918Z'
    for suffix in ('transfer','supervision'):
        name=m.PRIOR_ATTEMPT+'-'+suffix+'.json'
        (evidence/name).write_bytes((fixtures/name).read_bytes())
    (data/'bnci'/('.A01E.mat.'+m.PRIOR_ATTEMPT+'.partial')).write_bytes(b'')
    return data,evidence


def test_single_new_attempt_cannot_be_reclaimed_and_old_evidence_unchanged(tmp_path):
    data,evidence=prior_fixture(tmp_path)
    before={p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    m.claim_single_revision_attempt(data,evidence,'new-attempt')
    with pytest.raises(FileExistsError):m.claim_single_revision_attempt(data,evidence,'second-attempt')
    assert all(p.read_bytes()==b for p,b in before.items())
    claim=json.loads((data/'.official-lampx-v2-one-attempt.json').read_text())
    assert claim['attempt']=='new-attempt' and claim['authorized_new_attempts']==1


def test_changed_prior_evidence_blocks_single_attempt_claim(tmp_path):
    data,evidence=prior_fixture(tmp_path)
    (evidence/(m.PRIOR_ATTEMPT+'-transfer.json')).write_text('{}')
    with pytest.raises(ValueError,match='prior_failure'):m.claim_single_revision_attempt(data,evidence,'new')
    assert not (data/'.official-lampx-v2-one-attempt.json').exists()


def test_non_frozen_mat_not_mapped():
    for name in ('A10T.mat','A01T.gdf','../A01T.mat'):
        with pytest.raises(ValueError):m.lampx_url(name)
