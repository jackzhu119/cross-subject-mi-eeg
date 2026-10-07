"""Apply reviewed prose edits; preserve frozen numbers, references and data."""
import copy
import json
import re
from pathlib import Path

NUMERIC_LITERAL = re.compile(r'[+\-−]?\d+(?:[.,]\d+)*(?:[eE][+\-]?\d+)?')
CITATION = re.compile(r'\[\d+(?:[,–\-]\d+)*\]')

def apply_language_refinement(content, paper_dir):
    path = Path(paper_dir) / 'language_refinement.json'
    edits = json.loads(path.read_text())
    result = copy.deepcopy(content)
    assert len(result['blocks']) == edits['baseline_block_count']
    seen = set()
    for change in edits['block_edits']:
        index, field = change['index'], change['field']
        block = result['blocks'][index]
        assert (index, field) not in seen, 'Overlapping editorial edits'
        seen.add((index, field))
        assert ((field == 'text' and block['type'] == 'paragraph') or
                (field == 'caption' and block['type'] == 'figure') or
                (field == 'note' and block['type'] == 'table'))
        assert block[field] == change['before'], (index, field, 'baseline mismatch')
        assert NUMERIC_LITERAL.findall(change['before']) == NUMERIC_LITERAL.findall(change['after']), (index, 'numeric literals changed')
        assert CITATION.findall(change['before']) == CITATION.findall(change['after']), (index, 'citations changed')
        block[field] = change['after']
    # Authorship, funding, conflicts, ethics and material AI use remain intact.
    for index in edits['unchanged_declaration_indexes']:
        assert result['blocks'][index] == content['blocks'][index]
    assert result['references'] == content['references']
    assert result['reference_keys'] == content['reference_keys']
    assert result['new_fits'] == result['new_checkpoint_inference'] == 0
    return result
