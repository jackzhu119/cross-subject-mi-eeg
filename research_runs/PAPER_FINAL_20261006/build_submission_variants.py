"""Split editable manuscript and expand supplementary methods; no science run."""
import copy
import json
import re
from pathlib import Path
import hashlib
from datetime import datetime, timezone
import fitz
from docx import Document

import export_manuscript as export

OUT = Path(__file__).resolve().parent
data = json.loads((OUT / 'manuscript_content.json').read_text())
split = next(i for i, b in enumerate(data['blocks']) if b.get('text') == 'Supplementary material')
export.BLOCKS = copy.deepcopy(data['blocks'][:split])
export.word('manuscript_main_en.docx')
export.pdf('manuscript_main_en.pdf')

export.TITLE = 'Supplementary material'
export.SUBTITLE = data['title']
export.BLOCKS = copy.deepcopy(data['blocks'][split + 1:])
export.BLOCKS.append({'type': 'heading', 'level': 1, 'text': 'Detailed reproducible methods'})

# The companion method file is already reviewed. Preserve its content, including
# list items and full registry URLs, without inventing scientific statements.
method_lines = (OUT / 'supplementary_methods.md').read_text().splitlines()
paragraph = []
def flush():
    if paragraph:
        export.BLOCKS.append({'type': 'paragraph', 'text': ' '.join(paragraph)})
        paragraph.clear()
method_table_count = 0
line_index = 0
while line_index < len(method_lines):
    line = method_lines[line_index]
    if line.startswith('|'):
        flush()
        cells = []
        while line_index < len(method_lines) and method_lines[line_index].startswith('|'):
            cells.append([c.strip().replace('`', '').replace('**', '') for c in method_lines[line_index].strip().strip('|').split('|')])
            line_index += 1
        assert len(cells) >= 3 and all(set(c.replace(':', '').strip()) <= {'-'} for c in cells[1])
        method_table_count += 1
        label = 'Methods table M' + str(method_table_count) + '. '
        label += 'Equal-person hand power summaries.' if method_table_count == 1 else 'All descriptive physiology–accuracy coefficients.'
        export.BLOCKS.append({'type': 'table', 'label': label, 'headers': cells[0], 'rows': cells[2:], 'note': 'Values repeat the independently checked Q16 results; no additional analysis is performed.'})
        continue
    if not line.strip():
        flush()
    elif line.startswith('#'):
        flush()
        export.BLOCKS.append({'type': 'heading', 'level': 2, 'text': line.lstrip('# ').strip()})
    else:
        # Render Markdown emphasis as plain words in the expanded methods.
        # Word-boundary guards retain mathematical asterisk operators.
        plain = line.replace('`', '').replace('**', '')
        plain = re.sub(r'(?<![\w*])\*([^*\n]+)\*(?![\w*])', r'\1', plain)
        paragraph.append(plain.strip())
    line_index += 1
flush()
export.word('supplementary_materials.docx')
export.pdf('supplementary_materials.pdf')
receipt = {'status': 'current_split_exports_checked', 'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'detailed_methods_repeat_tables': method_table_count, 'no_new_model_execution': True}
for stem in ['manuscript_main_en', 'supplementary_materials']:
    document = Document(OUT / (stem + '.docx'))
    receipt[stem] = {'pdf_pages': len(fitz.open(OUT / (stem + '.pdf'))), 'figures': len(document.inline_shapes), 'tables': len(document.tables), 'sha256': {ext: hashlib.sha256((OUT / (stem + '.' + ext)).read_bytes()).hexdigest() for ext in ['docx', 'pdf']}}
(OUT / 'evidence/submission_exports.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'status': 'exported', 'main_body_blocks': split, 'supplementary_blocks': len(export.BLOCKS), 'new_fits': 0}))
