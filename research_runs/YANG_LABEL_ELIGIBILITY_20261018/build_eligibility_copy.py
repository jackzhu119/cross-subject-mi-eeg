#!/usr/bin/env python3
"""Create a new authorized scientific revision from the pinned public code; no dispatch."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'YANG_CLOCK_RECOVERY_20261018'))
from build_reviewed_copy import build as build_clock


def replace_once(text, old, new):
    if text.count(old)!=1:raise ValueError('reviewed scientific patch context differs: '+old[:70])
    return text.replace(old,new)


def build(source,destination):
    if destination.exists() or destination.is_symlink():raise ValueError('new destination required; originals preserved')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='paper1-eligibility-',dir=destination.parent) as folder:
        code=Path(folder)/'code'
        build_clock(source,code)
        parent_manifest=(code/'BUNDLE_MANIFEST.json').read_bytes()
        p=code/'p1_data.py';s=p.read_text(); parent_data=s
        s=replace_once(s,'import uuid\n','import uuid\nfrom eligibility_policy import population, qualified_events, legacy_compatible\n')
        s=replace_once(s,'    require(len(rows) == EXPECTED_TRIALS[dataset] and len({r["trial_id"] for r in rows}) == len(rows),',
                       '    expected_n, expected_counts = population(dataset, person)\n    require(len(rows) == expected_n and len({r["trial_id"] for r in rows}) == len(rows),')
        s=replace_once(s,'Counter(r["y"] for r in rows) == {0: len(rows) // 2, 1: len(rows) // 2}', 'Counter(r["y"] for r in rows) == expected_counts')
        s=replace_once(s,'X.shape == (EXPECTED_TRIALS[dataset], 3, 18, N_TIMES)','X.shape == (expected_n, 3, 18, N_TIMES)')
        s=replace_once(s,'"class_counts": {"left_hand": len(rows) // 2, "right_hand": len(rows) // 2}',
                       '"class_counts": {"left_hand": expected_counts[0], "right_hand": expected_counts[1]}')
        s=replace_once(s,'"excluded_trials": [], "old_19_or_21_channel_results_reused": False,',
                       '"excluded_trials": ([{"session": r["session"], **e} for r in run_audits for e in r["events"]["eligibility"]["unknown_events"]] if dataset == "yang" else []), "old_19_or_21_channel_results_reused": False,')
        s=replace_once(s,'        cues = _validated_cues(events, {"1": 0, "2": 1}, 100)',
                       '        cues, event_audit["eligibility"] = qualified_events(person, si, events,\n            verified.used[events_path.relative_to(verified.root).as_posix()])')
        s=replace_once(s,'raw_event_to_analysis_anchor_seconds=1.5, block=(ordinal - 1) // 40 + 1,',
                       'raw_event_to_analysis_anchor_seconds=1.5, block=cue["native_segment"],\n                                 native_event_index=cue["native_event_index"],\n                                 native_observed_task_ordinal=cue["native_observed_task_ordinal"],\n                                 trial_ordinal_semantics="retained_order_not_reconstructed_planned_trial",')
        old='''            for block in range(5):
                require(Counter(row["description"] for row in cues[block * 40:(block + 1) * 40]) == {"1": 20, "2": 20},
                        "Yang five-block class balance changed")'''
        s=replace_once(s,old,'            # Native marker-delimited segments were checked and audited by qualified_events.')
        s=replace_once(s,'"n_binary_trials": 200, "timing": TIMING["yang"]','"n_binary_trials": len(cues), "timing": TIMING["yang"]')
        s=replace_once(s,'audit["data_module_sha256"] == file_hash(__file__),','(audit["data_module_sha256"] == file_hash(__file__) or legacy_compatible(audit)),')
        s=replace_once(s,'        dataset = _dataset_key(audit["dataset"])','        dataset = _dataset_key(audit["dataset"])\n        expected_n, expected_counts = population(dataset, audit["provider_subject"])')
        s=replace_once(s,'len(rows) == EXPECTED_TRIALS[dataset] and','len(rows) == expected_n and')
        s=replace_once(s,'Counter(row["y"] for row in rows) == {0: len(rows) // 2, 1: len(rows) // 2}',
                       'Counter(row["y"] for row in rows) == expected_counts')
        before={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(parent_data).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        after={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(s).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for name in ('transform_native_context','explicit_sosfiltfilt','NativeReader','load_bnci_subject','load_dreyer_subject','_row','_grid','array_hash','read_annotations','VerifiedFiles'):
            if before[name]!=after[name]:raise ValueError('cache-compatible numerical/data transformation changed: '+name)
        p.write_text(s)
        p=code/'p1_runner.py';s=p.read_text()
        s=replace_once(s,'                log(f"Reuse verified prepared input {dataset}:{subject:03d}")',
                       '                from eligibility_policy import annotate_legacy_reuse\n                audit = annotate_legacy_reuse(path, native_root, audit)\n                log(f"Reuse verified prepared input {dataset}:{subject:03d}")')
        s=replace_once(s,'                log(f"Rebuild prepared input {dataset}:{subject:03d}: {error}")',
                       '                raise ValueError(f"Existing cache failed verification; preserved {dataset}:{subject:03d}") from error')
        s=s.replace('expansion18_clockfix_v2_20261018','expansion18_eligible_v3_20261018').replace('processed18_clockfix_v2_20261018','processed18_eligible_v3_20261018')
        p.write_text(s)
        p=code/'config/study.json';config=json.loads(p.read_text())
        config['protocol_id']='paper1_source_expansion_18ch_dimensionless_eligible_v3_20261018'
        config['source_trial_counts_expected']={'S9':2592,'S29':14590,'S60':33183}
        config['eligibility_amendment']={'approved_utc':'2026-10-18T01:53:31Z','manifest_sha256':'5291d362185a8db9bf45ddc95d9cb49d40de57893d2fd4da8681a802b5ab36f9',
            'rule':'explicit native labels 1/2 only; all 51 persons retained; no label/onset inference',
            'unknown_and_missing_evidence':'per-session raw event audit; native marker-9 segments, not groups of 40 retained events'}
        p.write_text(json.dumps(config,indent=2)+'\n')
        (code/'README_zh.md').write_bytes((HERE/'README_zh.md').read_bytes())
        (code/'eligibility_policy.py').write_bytes((HERE/'eligibility_policy.py').read_bytes())
        (code/'config/eligibility_manifest.json').write_bytes((HERE/'eligibility_manifest.json').read_bytes())
        (code/'RECOVERY_CLOCK_V2_MANIFEST.json').write_bytes(parent_manifest)
        # Existing originals remain untouched; this manifest describes only the new copy.
        old=json.loads(parent_manifest)
        names={r['path'] for r in old['files']}|{'eligibility_policy.py','config/eligibility_manifest.json'}
        manifest={**old,'eligibility_parent_manifest_sha256':hashlib.sha256(parent_manifest).hexdigest(),
                  'files':[{'path':name,'bytes':(code/name).stat().st_size,'sha256':hashlib.sha256((code/name).read_bytes()).hexdigest()} for name in sorted(names)]}
        (code/'BUNDLE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
        for name in ('p1_data.py','p1_runner.py','eligibility_policy.py'):
            compile((code/name).read_text(),str(code/name),'exec')
        code.rename(destination)
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('clean_public_bundle',type=Path);p.add_argument('new_code_directory',type=Path);a=p.parse_args()
    build(a.clean_public_bundle,a.new_code_directory)
    print('Built isolated eligibility revision; no cache mutations or training dispatch.')
