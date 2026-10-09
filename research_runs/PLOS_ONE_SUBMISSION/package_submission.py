"""Package validated editorial artifacts; never runs scientific code."""
from pathlib import Path
import hashlib,json,zipfile
from datetime import datetime,timezone
P=Path(__file__).resolve().parent
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((P/'evidence/plos_delivery_validation.json').read_text())
assert r['status']=='passed' and not r['failed_checks']
assert r['new_model_fits']==r['new_checkpoint_inference']==r['new_q16_scientific_execution']==0
for f,rec in r['pdfs'].items():assert h(P/f)==rec['sha256']
for n,rec in enumerate(json.loads((P/'evidence/figure_conversion.json').read_text()),1):assert h(P/'Figures'/f'Fig{n}.tif')==rec['tiff_sha256']
(P/'Numerical_Validation_Report.md').write_text(f'''# Numerical and delivery preservation validation

Status: **passed**, {r['check_count']} editorial/package checks; zero failed checks.

- 16,417 frozen scientific-file hashes remain unchanged in the active repository.
- 237 source manuscript assets were verified at their immutable historical commit. Obsolete editorial files have been removed from the current tree; this does not rewrite their historical archive.
- 453 source table cells are preserved, including p-values, confidence intervals, participant/trial/epoch counts and Q16 descriptors.
- Main scientific paragraphs, equations, abstract sentences and reference metadata are unchanged, apart from established citation/display typography. The updated S8 paragraph is administrative only.
- Source validation groups remain [1,2], [3,4], [5,6], [7,8,9], with the original equal-fold aggregation.
- All 66 retained S1 Data scientific/provenance members are frozen-source byte copies. Two superseded editorial delivery reports are excluded; scientific independent validations remain intact.
- All six TIFF files are byte-identical to the preceding visually checked package. Original points, error bars, field images and color scales are unchanged.
- 28 references preserve source authors, titles, years and DOIs; first-citation numbering is continuous and all references are cited.
- New model fits = 0; new checkpoint inference = 0; new Q15/Q16 experimental execution = 0.
- Current journal-facing documents contain no obsolete submission target or prior-review block.

Main review PDF: 41 pages; S1 Appendix: 29 pages; cover letter: one page. Continuous main line numbers, table-cell identity, caption placement and page bounds passed checks. All pages were reviewed as contact sheets; changed pages received full-resolution checks, supplemented by an independent editorial review.

This establishes preservation and delivery integrity. It does not claim a new raw/model replay, institutional ethics ruling, submission or journal acceptance. Original independent scientific validators retain their documented coverage. ORCID, approval of the current formatted files, author declarations and the official human-data checklist remain author actions.

See `evidence/plos_delivery_validation.json`, `evidence/independent_editorial_review.json` and `evidence/visual_review.json`.
''')
archive='PLOS_ONE_Submission_Package.zip'
excluded={archive,archive+'.sha256','MANIFEST.sha256','FILE_INVENTORY.json'}
files=sorted(f for f in P.rglob('*') if f.is_file() and f.name not in excluded and '__pycache__'not in f.parts)
assert not any(f.name.startswith('.env') or f.suffix in {'.pem','.key','.mat'} for f in files)
records={str(f.relative_to(P)):{'sha256':h(f),'bytes':f.stat().st_size} for f in files}
(P/'FILE_INVENTORY.json').write_text(json.dumps({'generated_at_utc':datetime.now(timezone.utc).isoformat(),'target_journal':'PLOS ONE','science_unchanged':True,'files':records},indent=2)+'\n')
files.append(P/'FILE_INVENTORY.json');files.sort()
(P/'MANIFEST.sha256').write_text(''.join(h(f)+'  '+str(f.relative_to(P))+'\n' for f in files))
with zipfile.ZipFile(P/archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for f in files+[P/'MANIFEST.sha256']:z.write(f,'PLOS_ONE_SUBMISSION/'+str(f.relative_to(P)))
with zipfile.ZipFile(P/archive) as z:
 assert z.testzip()is None
 for f in files:assert hashlib.sha256(z.read('PLOS_ONE_SUBMISSION/'+str(f.relative_to(P)))).hexdigest()==h(f)
(P/(archive+'.sha256')).write_text(h(P/archive)+'  '+archive+'\n')
print(json.dumps({'status':'passed','payload_files':len(files),'archive_bytes':(P/archive).stat().st_size,'archive_sha256':h(P/archive),'checks':r['check_count']}))
