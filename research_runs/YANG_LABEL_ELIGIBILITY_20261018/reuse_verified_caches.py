#!/usr/bin/env python3
"""Copy proven-compatible arrays without changing embedded old execution identity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid


def main():
    p=argparse.ArgumentParser();p.add_argument('--code',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,str(a.code.resolve(strict=True)))
    import p1_data as data
    from eligibility_policy import legacy_compatible,annotate_legacy_reuse
    root=a.root.resolve(strict=True);old=root/'data/processed18_clockfix_v2_20261018';new=root/'data/processed18_eligible_v3_20261018'
    entries=[]
    for dataset,people in [('bnci',range(1,10)),('yang',range(1,23))]:
        verified=data.VerifiedFiles(root/'data/raw'/dataset)
        for person in people:
            src=old/dataset/f'sub-{person:03d}.npz'
            if not src.is_file() or src.is_symlink():raise ValueError('expected prior cache missing or symlink')
            receipt=json.loads(src.with_suffix('.audit.json').read_text())
            digest=data.file_hash(src)
            if digest!=receipt['npz_sha256'] or src.stat().st_size!=receipt['npz_bytes']:
                raise ValueError('prior cache differs from independent written receipt')
            audit=data.verify_subject_npz(src,filter_bank_json=a.code/'config/filter_bank18.json')
            if not legacy_compatible(audit) or audit['provider_subject']!=person or audit['dataset']!=data.DATASET_NAMES[dataset]:
                raise ValueError('cache not approved for compatibility reuse')
            if audit['downloader_manifest_sha256']!=verified.manifest_sha256:
                raise ValueError('raw manifest changed')
            for row in audit['raw_files']:
                if verified.records.get(row['path'])!=row:raise ValueError('raw provenance differs')
                verified.find(relative=row['path'])
            linked=annotate_legacy_reuse(src,verified.root,audit)
            target=new/dataset/src.name;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                if target.is_symlink() or data.file_hash(target)!=digest:raise ValueError('different existing target preserved')
            else:
                temporary=target.with_name(target.name+'.part-'+uuid.uuid4().hex)
                try:
                    shutil.copyfile(src,temporary)
                    if data.file_hash(temporary)!=digest:raise ValueError('cache copy changed bytes')
                    os.link(temporary,target)  # Exclusive publication of a NEW copied inode, not a link to old data.
                finally:temporary.unlink(missing_ok=True)
            if data.file_hash(src)!=digest:raise ValueError('original cache changed during reuse')
            entries.append({'source':str(src),'destination':str(target),'npz_sha256':digest,
                            'old_embedded_audit_preserved':True,'compatibility':linked['cache_reuse_compatibility']})
            print(f'Verified copied cache {dataset}:{person:03d}',flush=True)
    report={'status':'PASS_31_COMPATIBLE_CACHES','files':entries,'arrays_regenerated':False,
            'source_files_modified':False,'scope':'full NPZ hashes, array/metadata hashes, raw-file rehash and native event linkage'}
    new.mkdir(parents=True,exist_ok=True)
    path=new/'cache_reuse_receipt.json'
    raw=(json.dumps(report,indent=2)+'\n').encode()
    if path.exists() and path.read_bytes()!=raw:raise ValueError('prior reuse receipt differs; preserved')
    if not path.exists():path.write_bytes(raw)
    print('PASS_31_COMPATIBLE_CACHES',flush=True)

if __name__=='__main__':main()
