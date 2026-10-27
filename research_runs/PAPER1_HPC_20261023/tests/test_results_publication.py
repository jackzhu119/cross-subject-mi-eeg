import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

spec=importlib.util.spec_from_file_location('paper1_bundle_core',str(Path(__file__).resolve().parents[1]/'PUBLISH_RESULTS_ON_SCHOOL.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.project=self.root/'paper1-risk-v1'
        self.project.mkdir();self.out=self.root/'export'
        self.study={'methods':list(b._METHODS),'epochs':40,'updates_per_epoch':128,'source_folds':5,
                    'validation_seeds':[1,2,3],'final_seeds':[4,5,6]}
        self.tasks=[]
        for fold in range(5):
            for seed in self.study['validation_seeds']:
                for method in b._METHODS:
                    self.tasks.append({'id':f'dev-f{fold:02d}-{method}-s{seed}','phase':'development',
                        'fold':fold,'seed':seed,'method':method,'train_ids':['a'],'validation_ids':['v'],
                        'test_ids':['p']})
        for seed in self.study['final_seeds']:
            for method in b._METHODS:
                self.tasks.append({'id':f'final-{method}-s{seed}','phase':'final','fold':None,
                    'seed':seed,'method':method,'train_ids':['a'],'validation_ids':[],
                    'test_ids':['p'],'selected_epoch':17})
        self.plan={'fingerprint':'a'*64,'identity':{'data_fingerprint':'b'*64},
            'development_task_count':75,'final_task_count':15,
            'development_tasks_sha256':b._canonical(self.tasks[:75])}
        self.write('config/study.json',self.study);self.write('tasks.json',self.tasks)
        self.write('state/plan.json',self.plan)
        selection={'plan_fingerprint':self.plan['fingerprint'],'source_records':[]}
        for i,task in enumerate(self.tasks):
            variants=['outer_best'] if task['phase']=='development' else ['fixed40','source_selected']
            complete={'status':'complete','task_id':task['id'],'epochs_completed':40,'global_step':5120,
                'optimizer_updates':5120,'best_epoch':17,
                'fingerprint':b._worker_fingerprint(self.study,task,self.plan['identity']['data_fingerprint']),
                'evaluations':{},**{k:task.get(k) for k in ('phase','method','seed','fold','selected_epoch')}}
            for variant in variants:
                digest=hashlib.sha256((task['id']+variant).encode()).hexdigest()
                folder='evaluations/'+variant+'/'+digest[:20]
                complete['evaluations'][variant]=folder+'/summary.json'
                relative='outputs/runs/'+task['id']+'/'+folder
                self.write(relative+'/summary.json',{'variant':variant,'model_sha256':digest,
                    'people':[{'person_id':'p'}]})
                shard=self.project/relative/('c'*24+'.npz')
                with zipfile.ZipFile(shard,'w') as z:
                    for name in ('logits.npy','y.npy','trial_ids.npy','identity.npy'):
                        z.writestr(name,b'synthetic bytes; exporter does not decode arrays')
            self.write('outputs/runs/'+task['id']+'/complete.json',complete)
            if task['phase']=='development':
                selection['source_records'].append({'task_id':task['id'],'best_epoch':17,
                    'complete_sha256':b._canonical(complete)})
        self.write('state/selection.json',selection)
        domains={d:{'status':'complete','domain':d} for d in b._DOMAINS}
        self.write('outputs/analysis/summary.json',{'status':'complete',
            'plan_fingerprint':self.plan['fingerprint'],'domains':domains})
        for domain in b._DOMAINS:
            self.write('outputs/analysis/'+domain+'.json',domains[domain])
            self.write('outputs/analysis/'+domain+'_participants.json',[{'person_id':'p'}])
        for relative in ('raw/private.mat','data/prepared/X.npy','outputs/runs/unrelated/checkpoints/latest.pt',
                         'outputs/runs/unused/evaluations/inner_epoch_001/a.npz','config/sync.json'):
            path=self.project/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'not selected')

    def write(self,relative,value):
        path=self.project/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value,sort_keys=True))

    def read(self,relative):return json.loads((self.project/relative).read_text())

    def test_complete_scope_hashes_archive_and_deterministic_resume(self):
        first=b.build_bundle(self.project,self.out)
        second=b.build_bundle(self.project,self.out)
        self.assertEqual(first['sha256'],second['sha256'])
        self.assertEqual(first['archive'],second['archive'])
        self.assertEqual(first['manifest']['development_completed'],75)
        self.assertEqual(first['manifest']['final_completed'],15)
        self.assertEqual(first['manifest']['selected_evaluation_summaries'],105)
        self.assertEqual(first['manifest']['prediction_shards'],105)
        self.assertEqual(first['manifest']['selected_file_count'],311)
        self.assertFalse(first['manifest']['model_checkpoint_backup'])
        with tarfile.open(first['archive'],'r:gz') as t:
            names=t.getnames();self.assertEqual(len(names),312)
            self.assertFalse(any('/inner_epoch_' in x or '/checkpoints/' in x or x.startswith(('raw/','data/')) for x in names))
            for row in first['manifest']['selected_files']:
                data=t.extractfile(row['path']).read()
                self.assertEqual(len(data),row['bytes'])
                self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'])
            self.assertEqual(json.load(t.extractfile('EXPORT_MANIFEST.json')),first['manifest'])
        self.assertFalse(list(self.out.glob('*.partial')))
        self.assertEqual(hashlib.sha256(first['archive'].read_bytes()).hexdigest(),first['sha256'])

    def test_missing_completion_or_incomplete_analysis_rejected_without_sources_changed(self):
        relative='outputs/runs/'+self.tasks[0]['id']+'/complete.json'
        original=(self.project/relative).read_bytes()
        (self.project/relative).unlink()
        with self.assertRaisesRegex(ValueError,'missing'):b.build_bundle(self.project,self.out)
        (self.project/relative).write_bytes(original)
        summary=self.read('outputs/analysis/summary.json');summary['status']='partially_complete'
        self.write('outputs/analysis/summary.json',summary)
        with self.assertRaisesRegex(ValueError,'complete analysis'):b.build_bundle(self.project,self.out)
        self.assertFalse(self.out.exists())

    def test_old_fit_count_identity_and_frozen_task_change_rejected(self):
        relative='outputs/runs/'+self.tasks[0]['id']+'/complete.json'
        original=self.read(relative);changed={**original,'global_step':1}
        self.write(relative,changed)
        with self.assertRaisesRegex(ValueError,'40-epoch'):b.build_bundle(self.project,self.out)
        self.write(relative,original)
        tasks=copy.deepcopy(self.tasks);tasks[0]['train_ids']=['other']
        self.write('tasks.json',tasks)
        with self.assertRaisesRegex(ValueError,'plan, selection'):b.build_bundle(self.project,self.out)

    def test_escape_and_raw_array_in_prediction_rejected(self):
        relative='outputs/runs/'+self.tasks[0]['id']+'/complete.json'
        complete=self.read(relative);original=copy.deepcopy(complete)
        complete['evaluations']['outer_best']='../../raw/private.mat'
        self.write(relative,complete)
        with self.assertRaisesRegex(ValueError,'exact selected variant'):b.build_bundle(self.project,self.out)
        self.write(relative,original)
        evalpath=self.project/'outputs/runs'/self.tasks[0]['id']/original['evaluations']['outer_best']
        shard=evalpath.parent/('c'*24+'.npz')
        with zipfile.ZipFile(shard,'a') as z:z.writestr('X.npy',b'not allowed')
        with self.assertRaisesRegex(ValueError,'unexpected arrays'):b.build_bundle(self.project,self.out)

    def test_change_after_json_validation_is_rejected_before_pack(self):
        original=b._canonical
        changed=False
        def canonical(value):
            nonlocal changed
            if isinstance(value,list) and len(value)==75 and not changed:
                changed=True
                p=self.project/'config/study.json'
                p.write_text(p.read_text()+'\n')
            return original(value)
        with mock.patch.object(b,'_canonical',side_effect=canonical):
            with self.assertRaisesRegex(ValueError,'Validated result JSON changed'):
                b.build_bundle(self.project,self.out)
        self.assertFalse(self.out.exists())

    def test_compressed_limit_keeps_partial_without_publication(self):
        with mock.patch.object(b,'_MAX_BUNDLE',1000):
            with self.assertRaisesRegex(ValueError,'exceeds 64 MiB'):
                b.build_bundle(self.project,self.out)
        self.assertTrue(list(self.out.glob('*.partial')))
        self.assertFalse(list(self.out.glob('*.tar.gz')))

    def test_symlink_escape_is_rejected_before_archive(self):
        path=self.project/'config/study.json';outside=self.root/'outside.json'
        outside.write_bytes(path.read_bytes());path.unlink();path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'symlink escapes'):b.build_bundle(self.project,self.out)





class FakeGitHub:
    archive_data = None
    corrupt_readback = False
    calls = []

    def __init__(self, token, repository):
        self.prefix='/repos/'+repository

    def optional(self, endpoint):
        self.calls.append(('GET',endpoint,None))
        return {'object':{'sha':'a'*40}}

    def request(self, method, endpoint, payload=None, *, raw_path=None, expected_bytes=None):
        self.calls.append((method,endpoint,payload))
        if method=='GET' and '/git/commits/' in endpoint:
            return {'tree':{'sha': 'c'*40 if endpoint.endswith('d'*40) else 'b'*40}}
        if method=='POST' and endpoint.endswith('/git/blobs'):
            import base64
            self.archive_data=base64.b64decode(payload['content'])
            FakeGitHub.archive_data=self.archive_data
            return {'sha':b._git_blob_sha(self.archive_data)}
        if method=='POST' and endpoint.endswith('/git/trees'):
            assert payload['base_tree']=='b'*40
            assert all(row['path'].startswith(b.RESULT_DIRECTORY+'/') for row in payload['tree'])
            return {'sha':'c'*40}
        if method=='POST' and endpoint.endswith('/git/commits'):
            assert payload['parents']==['a'*40] and payload['tree']=='c'*40
            return {'sha':'d'*40}
        if method=='PATCH':
            assert endpoint.endswith('/git/refs/heads/'+b.RESULT_BRANCH)
            assert payload['force'] is False
            return {'object':{'sha':'d'*40}}
        if method=='GET' and '/contents/' in endpoint:
            assert 'ref='+('d'*40) in endpoint
            return {'sha':b._git_blob_sha(self.archive_data),'size':len(self.archive_data)}
        if method=='GET' and '/git/blobs/' in endpoint:
            raw_path.write_bytes(b'corrupt' if self.corrupt_readback else self.archive_data)
            return None
        raise AssertionError((method,endpoint))


class PublicationTests(unittest.TestCase):
    setUp = BundleTests.setUp
    write = BundleTests.write
    read = BundleTests.read

    def test_publish_separate_branch_full_readback_and_original_results_retained(self):
        bundle=b.build_bundle(self.project,self.out)
        FakeGitHub.calls=[];FakeGitHub.corrupt_readback=False
        before=(self.project/'outputs/analysis/summary.json').read_bytes()
        import contextlib,io
        with mock.patch.object(b,'GitHubPublisher',FakeGitHub),contextlib.redirect_stdout(io.StringIO()):
            result=b.publish_bundle(self.project,bundle,'FAKE_PRIVATE_TOKEN')
        self.assertEqual(result['status'],'RESULT_BUNDLE_PUBLISHED_AND_READBACK_VERIFIED')
        self.assertTrue(result['full_archive_readback_verified'])
        self.assertEqual(result['branch'],b.RESULT_BRANCH)
        self.assertEqual((self.project/'outputs/analysis/summary.json').read_bytes(),before)
        self.assertFalse(result['model_checkpoint_backup'])
        self.assertFalse(any('/refs/heads/main' in endpoint and method!='GET'
                             for method,endpoint,payload in FakeGitHub.calls))

    def test_corrupt_readback_does_not_claim_verified_or_remove_original_bundle(self):
        bundle=b.build_bundle(self.project,self.out)
        FakeGitHub.corrupt_readback=True
        import contextlib,io
        with mock.patch.object(b,'GitHubPublisher',FakeGitHub),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(b.UploadError,'readback SHA256 differs'):
                b.publish_bundle(self.project,bundle,'FAKE_PRIVATE_TOKEN')
        self.assertTrue(bundle['archive'].is_file())
        self.assertFalse((self.out/'github-publication.json').exists())
        self.assertTrue(list(self.out.glob('*.github-readback.part')))
        FakeGitHub.corrupt_readback=False

    def test_existing_private_token_reused_without_prompt(self):
        path=self.root/'private-token';path.write_text('FAKE_PRIVATE_TOKEN');path.chmod(0o600)
        self.write('config/sync.json',{'token_file':str(path)})
        with mock.patch.object(b.getpass,'getpass',side_effect=AssertionError('no new token needed')):
            self.assertEqual(b._token(self.project),'FAKE_PRIVATE_TOKEN')

    def test_readable_json_change_after_export_stops_before_network(self):
        bundle=b.build_bundle(self.project,self.out)
        path=self.project/'outputs/analysis/summary.json'
        path.write_bytes(path.read_bytes()+b'\n')
        with mock.patch.object(b,'GitHubPublisher',side_effect=AssertionError('no network on changed results')):
            with self.assertRaisesRegex(b.UploadError,'Readable result changed after export'):
                b.publish_bundle(self.project,bundle,'FAKE_PRIVATE_TOKEN')
        self.assertTrue(bundle['archive'].exists())


class CurlBoundaryTests(unittest.TestCase):
    def test_token_only_on_stdin_and_api_denial_redacted(self):
        token='FAKE_PRIVATE_TOKEN_NEVER_IN_ARGV'
        from types import SimpleNamespace
        def execute(command,**kwargs):
            self.assertNotIn(token,' '.join(command))
            self.assertIn(token,kwargs['input'].decode())
            self.assertNotIn('--insecure',command)
            self.assertNotIn('--location',command)
            return SimpleNamespace(returncode=0,stdout=(token+'\n403').encode(),stderr=token.encode())
        with mock.patch.object(b.subprocess,'run',side_effect=execute):
            with self.assertRaises(b.UploadError) as caught:
                b.GitHubPublisher(token,b.REPOSITORY).request('GET','/repos/'+b.REPOSITORY+'/git/ref/heads/main')
        self.assertNotIn(token,str(caught.exception))
        self.assertEqual(caught.exception.status,403)


if __name__=='__main__':unittest.main()
