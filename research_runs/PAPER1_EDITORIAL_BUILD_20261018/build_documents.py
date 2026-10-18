#!/usr/bin/env python3
"""Export editable PLOS author documents and check their text/OOXML/PDF."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,shutil,sys,zipfile

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    old=(a.source/'scripts/export_manuscript.py').read_text()
    old=old.replace('import tempfile\n','import tempfile\nimport shutil\n')
    old=re.sub(r"SOFFICE = Path\([^\n]+",'SOFFICE = Path(shutil.which("libreoffice") or shutil.which("soffice") or "/missing")',old)
    old=old.replace("if heading:\n            level = len(heading[1])", "if heading:\n            if heading[2] == 'Abstract':\n                doc.add_page_break()\n            level = len(heading[1])")
    old=old.replace("if height > 6.5:\n                width *= 6.5 / height", "if height > 5.7:\n                width *= 5.7 / height")
    old=old.replace("inline(p, captions[number], size=11)","inline(p, captions[number], size=10)")
    script=a.out/'scripts/export_manuscript.py';script.write_text(old)
    spec=importlib.util.spec_from_file_location('export_final',script);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    jobs=[('main','manuscript_en.md','main_manuscript.docx',False,False),('review','manuscript_en.md','review_manuscript.docx',True,False),('supplement','supplementary_en.md','S1_Appendix.docx',False,False),('cover','submission/Cover_Letter.md','submission/Cover_Letter.docx',False,True),('fields','submission/Submission_Fields.md','submission/Submission_Fields.docx',False,True),('ethics','submission/Ethics_Author_Statement.md','submission/Ethics_Author_Statement.docx',False,True)]
    checks={}
    for name,source,dest,review,cover in jobs:
        print('Export',name,flush=True)
        m.render(a.out/source,a.out/dest,append_figures=review,cover=cover)
        pdf=m.pdf_export(a.out/dest)
        checks[name]=m.document_checks(a.out/source,a.out/dest,pdf,review=review,cover=cover)
        if name=='cover':assert checks[name]['pages']==1,checks[name]['pages']
        print(name,checks[name]['pages'],'pages',flush=True)
    (a.out/'evidence/document_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
if __name__=='__main__':main()
