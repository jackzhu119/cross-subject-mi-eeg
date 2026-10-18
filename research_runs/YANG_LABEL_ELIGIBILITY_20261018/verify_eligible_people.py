#!/usr/bin/env python3
"""Prepare anomalous source people in NEW approved cache; no model fitting."""
import argparse
import json
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--code',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,str(a.code.resolve(strict=True)))
    import p1_data as data
    from eligibility_policy import population
    cache=a.root/'data/processed18_eligible_v3_20261018/yang';raw=a.root/'data/raw/yang'
    summaries=[]
    for person in (23,24,26,32):
        path=cache/f'sub-{person:03d}.npz'
        if path.exists():
            audit=data.verify_subject_npz(path,filter_bank_json=a.code/'config/filter_bank18.json')
            if audit['provider_subject']!=person:raise ValueError('existing cache subject differs')
            verified=data.VerifiedFiles(raw)
            if audit['downloader_manifest_sha256']!=verified.manifest_sha256:raise ValueError('native manifest differs')
            for row in audit['raw_files']:
                if row!=verified.records.get(row['path']):raise ValueError('native receipt differs')
                verified.find(relative=row['path'])
        else:
            audit=data.build_subject_npz('yang',person,raw,path,filter_bank_json=a.code/'config/filter_bank18.json',
                                        yang_unit_policy='yang_v5_questionmark_V_scale_invariant')
            data.verify_subject_npz(path,filter_bank_json=a.code/'config/filter_bank18.json')
        count,counts=population('yang',person)
        if audit['n_trials']!=count or audit['class_counts']!={'left_hand':counts[0],'right_hand':counts[1]}:
            raise ValueError('real eligible population differs')
        summaries.append({'subject':person,'n_trials':count,'class_counts':audit['class_counts'],
                          'npz_sha256':data.file_hash(path),'sessions':[r['events']['eligibility'] for r in audit['run_audit']]})
        print(f'PASS_REAL_ELIGIBLE_PERSON {person} trials={count}',flush=True)
    report={'status':'PASS_REAL_FOUR_AFFECTED_PEOPLE','model_fits':0,'subjects':summaries}
    out=a.root/'data/processed18_eligible_v3_20261018/affected_people_acceptance.json'
    text=json.dumps(report,indent=2)+'\n'
    if out.exists() and out.read_text()!=text:raise ValueError('different acceptance receipt preserved')
    if not out.exists():out.write_text(text)
    print('PASS_REAL_FOUR_AFFECTED_PEOPLE; no training started',flush=True)

if __name__=='__main__':main()
