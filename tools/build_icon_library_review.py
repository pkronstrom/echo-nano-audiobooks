#!/usr/bin/env python3
"""Build a self-contained comparison of pinned, existing icon libraries."""
import base64
import json
import re
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from icon_proposals_v6 import draw, KEPT
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'docs/icon-library-assets'
labels=dict(files='File Browser',library='Media Library',play='Music Playback',musicsettings='Music Settings',settings='System Settings',shuffle='Shuffle',books='Audiobooks',meditation='Meditation')

def build():
    sets=json.loads((ASSETS/'manifest.json').read_text())
    for s in sets:
        s['licenseText']=(ASSETS/s['id']/'LICENSE').read_text()
        for icon in s['icons']:
            raw=(ASSETS/s['id']/(icon['id']+'.svg')).read_text()
            root=ET.fromstring(raw)
            assert all(el.tag.split('}')[-1] in {'svg','path','g','rect','circle','ellipse','line','polyline','polygon','title','desc'} for el in root.iter())
            assert not re.search(r'\bon\w+\s*=|href\s*=',raw)
            icon['sha256']=hashlib.sha256(raw.encode()).hexdigest()
            # Only colour changes for the dark review page; path geometry untouched.
            rendered=raw.replace('currentColor','#ffffff')
            if 'fill' not in root.attrib:rendered=rendered.replace('<svg','<svg fill="#ffffff"',1)
            ET.fromstring(rendered)
            icon['uri']='data:image/svg+xml;base64,'+base64.b64encode(rendered.encode()).decode()
    prior=json.loads((ROOT/'docs/reviews/icon-feedback-v6.json').read_text())
    current=[dict(id=k,label=label,pixels=draw(k,'B' if k=='settings' else KEPT[k][0])) for k,label in labels.items()]
    payload=dict(sets=sets,labels=labels,current=current,previous=prior)
    page=(ROOT/'tools/icon_library_review_template.html').read_text().replace('DATA_JSON',json.dumps(payload).replace('</','<\\/'))
    (ROOT/'docs/icon-library-review.html').write_text(page)
    (ROOT/'docs/icon-review.html').write_text(page)
    print('Built six libraries × eight icons; original SVG geometry retained')
if __name__=='__main__':build()
