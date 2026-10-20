#!/usr/bin/env python3
"""Build actual Word OOXML tracked changes for PLOS ONE Paper 1.
Start from the new DOCX, preserve its scientific contents and formatting, and
mark text changed from the preserved original as additions/deletions.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys
import zipfile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

OLD = Path(sys.argv[1])
NEW = Path(sys.argv[2])
OUTPUT = Path(sys.argv[3])
REPORT = OUTPUT.with_suffix(".validation.json")
AUTHOR = "Version comparison"
NOW = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
XML_NS = "http://www.w3.org/XML/1998/namespace"

old = Document(OLD)
new = Document(NEW)
old_body = old.element.body
new_body = new.element.body
block_tags = {qn("w:p"), qn("w:tbl")}
old_blocks = [e for e in old_body if e.tag in block_tags]
new_blocks = [e for e in new_body if e.tag in block_tags]

def get_text(elem):
    if elem.tag == qn("w:tbl"):
        rows = []
        for tr in elem.iter(qn("w:tr")):
            cells = []
            for tc in tr:
                if tc.tag == qn("w:tc"):
                    cells.append("".join((t.text or "") for t in tc.iter(qn("w:t"))))
            if cells:
                rows.append(" | ".join(cells))
        return "\n".join(rows)
    return "".join((t.text or "") for t in elem.iter(qn("w:t")))

def normalized(elem):
    return re.sub(r"\s+", " ", get_text(elem)).strip()

def change(tag, number):
    e = OxmlElement("w:" + tag)
    e.set(qn("w:id"), str(number))
    e.set(qn("w:author"), AUTHOR)
    e.set(qn("w:date"), NOW)
    return e

next_id = 1000

def mark_insertions(elem):
    global next_id
    added = 0
    for run in list(elem.iter(qn("w:r"))):
        parent = run.getparent()
        if parent is None or parent.tag in {qn("w:del"), qn("w:ins")}:
            continue
        if not any(ch.tag in {qn("w:t"), qn("w:drawing"), qn("w:tab"), qn("w:br"), qn("w:instrText")} for ch in run):
            continue
        ins = change("ins", next_id)
        next_id += 1
        parent.replace(run, ins)
        ins.append(run)
        added += 1
    return added

def make_deleted_paragraph(txt):
    global next_id
    p = OxmlElement("w:p")
    ppr = OxmlElement("w:pPr")
    rpr = OxmlElement("w:rPr")
    rpr.append(change("del", next_id))
    next_id += 1
    ppr.append(rpr)
    p.append(ppr)
    deletion = change("del", next_id)
    next_id += 1
    run = OxmlElement("w:r")
    t = OxmlElement("w:delText")
    t.set("{" + XML_NS + "}space", "preserve")
    t.text = txt
    run.append(t)
    deletion.append(run)
    p.append(deletion)
    return p

original_clean_body = deepcopy(new_body)
if list(new_body.iter(qn("w:del"))) or list(new_body.iter(qn("w:ins"))):
    raise SystemExit("Refusing to merge pre-existing tracked changes in newer DOCX")

old_vals = [normalized(x) for x in old_blocks]
new_vals = [normalized(x) for x in new_blocks]
if not any("Source-cohort expansion improves weaker-class coverage" in x for x in new_vals):
    raise SystemExit("Wrong CURRENT manuscript: expected PLOS ONE Paper 1 title")
if not any("Source-only model selection" in x for x in old_vals):
    raise SystemExit("Wrong PRIOR manuscript: expected 9 October Paper 1 title")
matcher = SequenceMatcher(a=old_vals, b=new_vals, autojunk=False)
removals = defaultdict(list)
insert_at = set()
stat = {"equal": 0, "replace_old": 0, "replace_new": 0, "delete_old": 0, "insert_new": 0}
for tag, i0, i1, j0, j1 in matcher.get_opcodes():
    if tag == "equal":
        stat["equal"] += j1 - j0
        continue
    if tag in ("delete", "replace"):
        for x in old_blocks[i0:i1]:
            if normalized(x):
                removals[j0].append(get_text(x))
                stat["delete_old" if tag == "delete" else "replace_old"] += 1
    if tag in ("insert", "replace"):
        insert_at.update(range(j0, j1))
        stat["insert_new" if tag == "insert" else "replace_new"] += j1 - j0

inserted_runs = sum(mark_insertions(new_blocks[j]) for j in sorted(insert_at))
for j in sorted(removals.keys(), reverse=True):
    if j < len(new_blocks):
        idx = new_body.index(new_blocks[j])
    else:
        sect = next((x for x in new_body if x.tag == qn("w:sectPr")), None)
        idx = new_body.index(sect) if sect is not None else len(new_body)
    for txt in reversed(removals[j]):
        new_body.insert(idx, make_deleted_paragraph(txt))

settings = new.settings.element
if settings.find(qn("w:trackRevisions")) is None:
    settings.insert(0, OxmlElement("w:trackRevisions"))

# Independent round-trip validation: accept revisions => identical current DOCX body.
check = deepcopy(new_body)
for p in list(check):
    if p.tag != qn("w:p"):
        continue
    ppr = p.find(qn("w:pPr"))
    rpr = ppr.find(qn("w:rPr")) if ppr is not None else None
    if rpr is not None and rpr.find(qn("w:del")) is not None:
        check.remove(p)
for ins in list(check.iter(qn("w:ins"))):
    parent = ins.getparent()
    if parent is None:
        continue
    index = parent.index(ins)
    for child in list(ins):
        ins.remove(child)
        parent.insert(index, child)
        index += 1
    parent.remove(ins)
for deletion in list(check.iter(qn("w:del"))):
    parent = deletion.getparent()
    if parent is not None:
        parent.remove(deletion)
exact = (etree.tostring(original_clean_body, method="c14n") ==
         etree.tostring(check, method="c14n"))
if not exact:
    raise SystemExit("FAIL: accepting changes did not reconstruct current DOCX body")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
new.save(OUTPUT)
with zipfile.ZipFile(OUTPUT) as z:
    doc = etree.fromstring(z.read("word/document.xml"))
    st = etree.fromstring(z.read("word/settings.xml"))
    cins = len(list(doc.iter(qn("w:ins"))))
    cdel = len(list(doc.iter(qn("w:del"))))
    cdeltext = len(list(doc.iter(qn("w:delText"))))
    assert cins > 0 and cdel > 0 and cdeltext > 0
    assert st.find(qn("w:trackRevisions")) is not None
report = {
    "prior_docx": str(OLD), "current_docx": str(NEW), "output": str(OUTPUT),
    "prior_blocks": len(old_blocks), "current_blocks": len(new_blocks),
    "diff_blocks": stat, "inserted_run_nodes": inserted_runs,
    "xml_insertions": cins, "xml_deletions": cdel, "xml_deleted_text_nodes": cdeltext,
    "accept_changes_reconstructs_current_body_exactly": exact,
    "comparison_date_utc": NOW,
    "important": "Source files are GitHub snapshots. Confirm actual Editorial Manager uploads match the corresponding files."
}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
