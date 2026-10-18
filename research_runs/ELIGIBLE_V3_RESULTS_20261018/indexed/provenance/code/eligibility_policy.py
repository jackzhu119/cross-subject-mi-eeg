"""Authorized fixed-input eligibility amendment; never infer labels or time points."""
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = '5291d362185a8db9bf45ddc95d9cb49d40de57893d2fd4da8681a802b5ab36f9'
LEGACY_DATA_SHA256 = 'a930de67cbc15d1db4c5d7d2b8ee05a436ebc20e564e72800c1913aaeee86b44'

@lru_cache(maxsize=1)
def sessions():
    root=Path(__file__).resolve().parent
    path=root/'config/eligibility_manifest.json'
    if not path.exists():path=root/'eligibility_manifest.json'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA256:
        raise ValueError('eligibility manifest changed')
    obj=json.loads(raw)
    rows={(r['subject'],r['session']):r for r in obj['sessions']}
    if len(obj['sessions'])!=153 or set(rows)!={(s,d) for s in range(1,52) for d in range(1,4)}:
        raise ValueError('eligibility registry is incomplete')
    return rows


def population(dataset, person):
    if dataset!='yang':
        n={'bnci':288,'dreyer':80}[dataset]
        return n,{0:n//2,1:n//2}
    counts={y:sum(sessions()[(int(person),s)]['all_marker_counts'].get(str(y+1),0) for s in range(1,4)) for y in (0,1)}
    return sum(counts.values()),counts


def qualified_events(person, session, events, record):
    fixed=sessions()[(int(person),int(session))]
    if any(record[k]!=fixed[j] for k,j in [('path','path'),('size','bytes'),('sha256','sha256')]):
        raise ValueError('event file differs from fixed eligibility identity')
    counts=dict(Counter(e['description'] for e in events))
    if counts!=fixed['all_marker_counts'] or ('all_events' in fixed and events!=fixed['all_events']):
        raise ValueError('event sequence/count differs from reviewed evidence')
    if not all(events[i]['onset']<=events[i+1]['onset'] for i in range(len(events)-1)):
        raise ValueError('nonordered native events')
    if counts.get('9')!=4 or any(k not in ('1','2','7','8','9','255') for k in counts):
        raise ValueError('unreviewed separator/marker inventory')
    block=1; observed_task=0; cues=[]; unknown=[]; boundaries=[]
    segment_counts=[Counter() for _ in range(5)]
    for index,event in enumerate(events):
        code=event['description']
        if code=='9':
            boundaries.append({'native_event_index':index,**event});block+=1
        elif code in ('1','2','255'):
            observed_task+=1
            segment_counts[block-1][code]+=1
            item={**event,'native_event_index':index,'native_observed_task_ordinal':observed_task,'native_segment':block}
            if code=='255':unknown.append(item)
            else:cues.append(item)
    if not all(cues[i]['onset']<cues[i+1]['onset'] for i in range(len(cues)-1)):
        raise ValueError('nonordered or duplicate task cue onsets')
    if any(not (c.get('1',0)+c.get('2',0)) for c in segment_counts):
        raise ValueError('empty native marker-delimited segment')
    if 'all_events' not in fixed and any(c.get('1',0)!=20 or c.get('2',0)!=20 for c in segment_counts):
        raise ValueError('unreviewed native segment counts')
    audit={'eligibility_manifest_sha256':MANIFEST_SHA256,'known_labels_only':True,
           'all_marker_counts':counts,'included_count':len(cues),'unknown_events':unknown,
           'shortfall_vs_planned_counts':{str(y):100-counts.get(str(y),0) for y in (1,2)},
           'unknown_labels_inferred':False,'missing_onsets_inferred':False,
           'native_boundaries':boundaries,'native_segment_counts':[dict(c) for c in segment_counts],
           'boundary_semantics':'operational native marker-9 delimiters; official code-9 semantics unconfirmed',
           'trial_ordinal_semantics':'retained order only, not reconstructed planned trial number',
           'native_event_mapping':[{'native_event_index':c['native_event_index'],'onset':c['onset'],
                                    'code':c['description'],'native_segment':c['native_segment'],
                                    'native_observed_task_ordinal':c['native_observed_task_ordinal']} for c in cues]}
    return cues,audit


def legacy_compatible(audit):
    # Only the 31 completed, unaffected source persons from the recorded failed run.
    return (audit.get('data_module_sha256')==LEGACY_DATA_SHA256 and
            ((audit.get('dataset')=='BNCI2014_001' and 1<=audit.get('provider_subject',0)<=9) or
             (audit.get('dataset')=='Yang2025_2C' and 1<=audit.get('provider_subject',0)<=22)))


def annotate_legacy_reuse(path, raw_root, audit):
    """Retain old NPZ/audit identities; add independent eligibility linkage separately."""
    if not legacy_compatible(audit):return audit
    import numpy as np
    import p1_data as data
    result=dict(audit)
    compatibility={'source_data_module_sha256':audit['data_module_sha256'],
                   'current_data_module_sha256':data.file_hash(data.__file__),
                   'arrays_regenerated':False,'npz_sha256':data.file_hash(path),
                   'eligibility_manifest_sha256':MANIFEST_SHA256,'sessions':[]}
    if audit['dataset']=='Yang2025_2C':
        with np.load(path,allow_pickle=False) as npz:
            rows=[json.loads(x) for x in npz['metadata_json'].tolist()]
        verified=data.VerifiedFiles(raw_root)
        for session in range(1,4):
            relative=f"sourcedata/2C dataset/sub-{audit['provider_subject']:03d}/ses-{session:02d}/eeg/evt.bdf"
            event_path=verified.find(relative=relative)
            events,_=data.read_annotations(event_path)
            record=verified.used[event_path.relative_to(verified.root).as_posix()]
            cues,evidence=qualified_events(audit['provider_subject'],session,events,record)
            cached=[r for r in rows if r['session']==f'ses-{session:02d}']
            if len(cached)!=len(cues):raise ValueError('legacy cache differs from approved source population')
            for row,cue in zip(cached,cues):
                sample=data._grid(cue['onset']*1000,'cached cue',tolerance=0.5+1e-9)
                if (row['y']!=int(cue['description'])-1 or row['event_sample']!=sample or
                    row['analysis_anchor_sample']!=sample+1500 or row['block']!=cue['native_segment']):
                    raise ValueError('legacy cache labels/time/block differ from native events')
            compatibility['sessions'].append({'session':session,**evidence})
    result['cache_reuse_compatibility']=compatibility
    return result
