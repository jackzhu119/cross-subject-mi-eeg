"""Split editable manuscript and expand supplementary methods; no science run."""
import copy
import json
from pathlib import Path

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
for line in method_lines:
    if not line.strip():
        flush()
    elif line.startswith('#'):
        flush()
        export.BLOCKS.append({'type': 'heading', 'level': 2, 'text': line.lstrip('# ').strip()})
    else:
        # Inline code and bold syntax are typographical Markdown conventions.
        paragraph.append(line.replace('`', '').replace('**', '').strip())
flush()
export.word('supplementary_materials.docx')
export.pdf('supplementary_materials.pdf')
print(json.dumps({'status': 'exported', 'main_body_blocks': split, 'supplementary_blocks': len(export.BLOCKS), 'new_fits': 0}))
