import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import types
import zipfile
from collections import Counter

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from eligibility_policy import qualified_events,population,sessions,legacy_compatible,LEGACY_DATA_SHA256
from build_eligibility_copy import build
SOURCE=HERE.parent/'SOURCE_EXPANSION_20261017'

class EligibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads((HERE.parent/'YANG_MARKER_AUDIT_20261018/five_original_event_members_audit.json').read_text())['files']
    def record(self,person,session):
        r=sessions()[(person,session)]
        return {'path':r['path'],'size':r['bytes'],'sha256':r['sha256']}
    def test_five_real_anomalies_keep_only_native_labels_without_retiming(self):
        for row in self.rows:
            cues,a=qualified_events(row['subject'],row['session'],row['events'],self.record(row['subject'],row['session']))
            self.assertEqual([{k:c[k] for k in ('onset','duration','description')} for c in cues],
                             [e for e in row['events'] if e['description'] in ('1','2')])
            self.assertEqual(len(cues),195 if (row['subject'],row['session'])==(24,3) else 199)
            self.assertEqual(len(a['unknown_events']),0 if (row['subject'],row['session'])==(24,3) else 1)
            for cue in cues:
                i=cue['native_event_index']
                self.assertEqual(cue['native_segment'],1+sum(e['description']=='9' for e in row['events'][:i]))
    def test_missing_events_do_not_move_next_segment(self):
        row=next(r for r in self.rows if (r['subject'],r['session'])==(24,3))
        cues,a=qualified_events(24,3,row['events'],self.record(24,3))
        self.assertEqual(a['native_segment_counts'][3],{'2':16,'1':19})
        self.assertEqual(a['native_segment_counts'][4],{'2':20,'1':20})
        self.assertEqual(cues[155]['native_segment'],5)  # No artificial group-of-40 boundary at 160.
        self.assertEqual(cues[155]['onset'],row['events'][cues[155]['native_event_index']]['onset'])
    def test_extra_255_does_not_remove_or_relabel_200_valid_events(self):
        events=json.loads((HERE/'validation/sub017_ses02_events.json').read_text())
        cues,a=qualified_events(17,2,events,self.record(17,2))
        self.assertEqual(Counter(c['description'] for c in cues),{'1':100,'2':100})
        self.assertEqual(len(a['unknown_events']),1)
        self.assertEqual(a['unknown_events'][0]['onset'],105.625)
    def test_changed_identity_count_or_anomaly_onset_rejected(self):
        row=self.rows[0];events=copy.deepcopy(row['events']);events[2]['description']='255'
        with self.assertRaises(ValueError):qualified_events(23,1,events,self.record(23,1))
        events=copy.deepcopy(row['events']);events[2]['onset']+=0.001
        with self.assertRaises(ValueError):qualified_events(23,1,events,self.record(23,1))
        bad=self.record(23,1);bad['sha256']='0'*64
        with self.assertRaises(ValueError):qualified_events(23,1,row['events'],bad)
    def test_all_51_people_counts_and_all_five_unknowns(self):
        self.assertEqual(sum(population('yang',s)[0] for s in range(1,52)),30591)
        self.assertEqual([population('yang',s)[0] for s in (23,24,26,32)],[599,594,599,599])
        self.assertEqual(sum(r['all_marker_counts'].get('255',0) for r in sessions().values()),5)
    def test_legacy_cache_scope_is_exact_and_preserves_identity(self):
        for dataset,person,expected in [('BNCI2014_001',9,True),('Yang2025_2C',17,True),('Yang2025_2C',22,True),('Yang2025_2C',23,False),('Dreyer2023',1,False)]:
            a={'dataset':dataset,'provider_subject':person,'data_module_sha256':LEGACY_DATA_SHA256}
            before=copy.deepcopy(a);self.assertEqual(legacy_compatible(a),expected);self.assertEqual(a,before)
            a['data_module_sha256']='0'*64;self.assertFalse(legacy_compatible(a))
    def test_cache_population_roundtrip_and_corruption_guards(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            code=Path(folder)/'code';build(SOURCE,code)
            spec=importlib.util.spec_from_file_location('eligible_data_fixture',code/'p1_data.py')
            data=importlib.util.module_from_spec(spec);sys.modules[spec.name]=data;spec.loader.exec_module(data)
            for dataset,person,module_sha in [('bnci',1,LEGACY_DATA_SHA256),('yang',24,data.file_hash(code/'p1_data.py'))]:
                n,counts=population(dataset,person)
                y=np.array([0]*counts[0]+[1]*counts[1],dtype=np.int64)
                rows=[{'dataset':data.DATASET_NAMES[dataset],'subject':str(person),'session':'fixture',
                       'run':'fixture','trial_id':str(i),'y':int(label)} for i,label in enumerate(y)]
                X=np.zeros((n,3,18,320),dtype=np.float32)
                audit={'dataset':data.DATASET_NAMES[dataset],'provider_subject':person,
                       'filter_bank_sha256':data.file_hash(code/'config/filter_bank18.json'),
                       'data_module_sha256':module_sha,'units':'dimensionless','normalization':data.NORMALIZATION,
                       'X_sha256':data.array_hash(X),'y_sha256':data.array_hash(y),'metadata_sha256':data.object_hash(rows)}
                arrays={'X':X,'y':y,'metadata_json':np.array([json.dumps(r) for r in rows]),'audit_json':np.array(json.dumps(audit))}
                arrays.update({k:np.array([r[k] for r in rows]) for k in ('dataset','subject','session','run','trial_id')})
                path=Path(folder)/(dataset+'.npz');np.savez_compressed(path,**arrays)
                result=data.verify_subject_npz(path,filter_bank_json=code/'config/filter_bank18.json')
                self.assertEqual(result['data_module_sha256'],module_sha)
                arrays['y']=y.copy();arrays['y'][0]=1
                np.savez_compressed(path,**arrays)
                with self.assertRaises(ValueError):data.verify_subject_npz(path,filter_bank_json=code/'config/filter_bank18.json')
                arrays['y']=y;audit['data_module_sha256']='0'*64;arrays['audit_json']=np.array(json.dumps(audit))
                np.savez_compressed(path,**arrays)
                with self.assertRaises(ValueError):data.verify_subject_npz(path,filter_bank_json=code/'config/filter_bank18.json')

    def test_generated_copy_changes_only_approved_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            dest=Path(directory)/'code';manifest=build(SOURCE,dest)
            before=json.loads((SOURCE/'config/study.json').read_text());after=json.loads((dest/'config/study.json').read_text())
            self.assertEqual({k for k in set(before)|set(after) if before.get(k)!=after.get(k)},
                             {'protocol_id','source_trial_counts_expected','eligibility_amendment'})
            self.assertEqual(after['source_trial_counts_expected'],{'S9':2592,'S29':14590,'S60':33183})
            for name in ('p1_train.py','p1_select.py','p1_csp.py','config/filter_bank18.json'):
                self.assertEqual((SOURCE/name).read_bytes(),(dest/name).read_bytes())
            for r in manifest['files']:
                self.assertEqual(hashlib.sha256((dest/r['path']).read_bytes()).hexdigest(),r['sha256'])
            s=(dest/'p1_data.py').read_text();self.assertIn('block=cue["native_segment"]',s)
            self.assertIn('event_sample = _grid(cue["onset"] * 1000',s)
            self.assertIn('analysis_anchor = event_sample + 1500',s)
            with self.assertRaises(ValueError):build(SOURCE,dest)

    def test_invalid_existing_cache_stops_without_rebuild_or_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);code=root/'code';build(SOURCE,code)
            cache=root/'cache/yang/sub-023.npz';cache.parent.mkdir(parents=True)
            cache.write_bytes(b'preserved-invalid-cache')
            tree=ast.parse((code/'p1_runner.py').read_text())
            prepare=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='prepare')
            fake=types.ModuleType('p1_data')
            fake.verify_subject_npz=Mock(side_effect=ValueError('hash mismatch'))
            fake.build_subject_npz=Mock();fake.VerifiedFiles=Mock();fake.DATASET_NAMES={'yang':'Yang2025_2C'}
            scope={'Path':Path,'BUNDLE':code,'log':lambda *a:None,'zipfile':zipfile}
            exec(compile(ast.Module(body=[prepare],type_ignores=[]),'prepare','exec'),scope)
            with patch.dict(sys.modules,{'p1_data':fake}):
                with self.assertRaisesRegex(ValueError,'preserved'):
                    scope['prepare'](root/'raw',root/'cache','yang',[23])
            fake.build_subject_npz.assert_not_called()
            self.assertEqual(cache.read_bytes(),b'preserved-invalid-cache')

if __name__=='__main__':unittest.main()
