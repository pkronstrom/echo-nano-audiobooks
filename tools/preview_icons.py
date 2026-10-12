#!/usr/bin/env python3
"""Generate the offline icon review from audited Nano firmware resources.

No firmware is modified. Python standard library only.
"""
import argparse
import hashlib
import html
import json
import re
import struct
from pathlib import Path

from rknano_fw import load, stock_name

ROOT = Path(__file__).resolve().parents[1]
ADDRESSES = [0x03072DFF, 0x03072DAF, 0x03072D5F, 0x03072D87, 0x03072DD7]


def decode(data):
    assert len(data) == 40
    return [''.join('1' if data[(y // 8) * 20 + x] & (1 << (y % 8)) else '0'
                    for x in range(20)) for y in range(16)]


def proposal(kind, bold=False):
    grid = [[0] * 20 for _ in range(16)]
    def dot(x, y):
        if 0 <= x < 20 and 0 <= y < 16:
            grid[y][x] = 1
    def line(x, y, xx, yy):
        n = max(abs(xx-x), abs(yy-y))
        for i in range(n+1):
            dot(round(x+(xx-x)*i/max(n,1)), round(y+(yy-y)*i/max(n,1)))
    def rect(x,y,w,h,fill=False):
        for yy in range(y,y+h):
            for xx in range(x,x+w):
                if fill or yy in (y,y+h-1) or xx in (x,x+w-1): dot(xx,yy)
    if kind == 'files':
        rect(2,5,16,9); line(2,4,2,2); line(2,2,7,2); line(7,2,10,5)
    elif kind == 'library':
        for y in [3,7,11]: rect(2,y,2,2,True); line(7,y,17,y); line(7,y+1,17,y+1)
    elif kind == 'play':
        for x in range(5,15):
            for y in range(2+abs(x-5)//2,14-abs(x-5)//2): dot(x,y)
    elif kind == 'musicsettings':
        for x,y in [(4,5),(10,10),(16,4)]: line(x,2,x,13);rect(x-2,y-1,5,3,True)
    elif kind == 'settings':
        rect(5,3,10,10);rect(8,6,4,4)
        for x,y,w,h in [(8,1,4,3),(8,12,4,3),(3,6,3,4),(14,6,3,4)]:rect(x,y,w,h,True)
    elif kind == 'shuffle':
        for a in [(2,3,6,3),(6,3,13,12),(13,12,17,12),(2,12,6,12),(6,12,13,3),(13,3,17,3),(14,0,17,3),(14,6,17,3),(14,9,17,12),(14,15,17,12)]:line(*a)
    elif kind == 'books':
        rect(2,3,7,10);rect(10,3,7,10);line(9,4,9,14)
        for y in [6,9]:line(4,y,6,y);line(12,y,14,y)
    elif kind == 'meditation':
        rect(8,1,4,4,True)
        for a in [(9,6,5,10),(10,6,14,10),(5,10,2,12),(2,12,9,14),(14,10,17,12),(17,12,10,14),(8,7,8,10),(11,7,11,10)]:line(*a)
    if bold:
        original = [row[:] for row in grid]
        for y in range(16):
            for x in range(19):
                if original[y][x]:grid[y][x+1]=1
    return [''.join(map(str,row)) for row in grid]


def generate(stock, output):
    if not stock_name(stock): raise ValueError('Expected audited stock V1.7.0 image')
    im = load(stock)
    pointer_offset,_ = im.region(0,0x03004124)
    if list(struct.unpack_from('<5I',im.d,pointer_offset)) != ADDRESSES:
        raise ValueError('Stock icon table differs from audited addresses')
    offset,_ = im.region(21,0x0300E6D8)
    icons=[]
    for i,address in enumerate(ADDRESSES):
        sid = struct.unpack_from('<H',im.d,offset+i*8+6)[0]
        p=im.lang_text(2,sid)
        label=bytes(im.d[p:p+200]).decode('utf-16le').split('\0')[0]
        off,_=im.region(0,address)
        icons.append(dict(label=label,address=f'0x{address:08x}',sid=f'0x{sid:02x}',pixels=decode(im.d[off:off+40])))
    asm=(ROOT/'patches/shuffle_10_mod21_cave.S').read_text()
    raw=bytes(int(x,16) for row in asm.splitlines() if row.strip().startswith('.byte')
              for x in re.findall(r'0x([0-9a-f]+)',row))
    icons.append(dict(label='Shuffle',address='mod21 0x0307951c (patch)',sid='0x82',pixels=decode(raw)))
    kinds=['files','library','play','musicsettings','settings','shuffle','books','meditation']
    labels=[i['label'] for i in icons]+['Audiobooks · proposed entry','Meditation · proposed entry']
    data=dict(stock=icons,outline=[dict(label=l,pixels=proposal(k)) for l,k in zip(labels,kinds)],
              bold=[dict(label=l,pixels=proposal(k,True)) for l,k in zip(labels,kinds)])
    page=TEMPLATE.replace('DATA_JSON',json.dumps(data)).replace('HASH_VALUE',hashlib.sha256(Path(stock).read_bytes()).hexdigest())
    output.write_text(page)
    print(f'Wrote {output}; 5 decoded stock + 1 existing patch + 16 proposed icons')


TEMPLATE='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Echo Nano · icon review</title>
<style>body{margin:0;background:#13171b;color:#e8edf1;font:16px/1.5 system-ui}main{max-width:1100px;margin:auto;padding:32px}h1{font-size:32px}h2{margin-top:44px}p{max-width:850px;color:#bbc8d2}.tag{color:#ffe08c}a{color:#7cc9ff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}.card{padding:16px;background:#20272e;border:1px solid #394652;border-radius:8px}.card h3{font-size:16px;margin-top:0}.samples{display:flex;align-items:center;gap:24px;min-height:90px}.icon{background:#000;color:#fff;image-rendering:pixelated;flex-shrink:0}small{color:#a8b8c6;display:block}.controls{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}button,select{font:inherit;padding:8px;background:#283746;color:white;border:1px solid #668096;border-radius:5px}.screens{display:flex;gap:24px;align-items:center;flex-wrap:wrap}.screen{background:black;color:white;image-rendering:pixelated}.note{padding:14px;border-left:3px solid #ddba66;background:#282820}code{overflow-wrap:anywhere}label{display:flex;gap:8px;align-items:center}textarea{box-sizing:border-box;width:100%;background:#10171d;color:#eef4f7;border:1px solid #668096;border-radius:5px;padding:10px;font:14px/1.4 system-ui}.card select{width:100%;margin-bottom:10px}footer{margin-top:50px;border-top:1px solid #394652;padding-top:20px}</style>
<main><h1>Echo Nano / activity icons</h1><p class="tag">Design review only · no icon changes installed in firmware</p>
<p>The inventory below is decoded directly from the audited V1.7.0 firmware and the existing Shuffle patch. The display drawing code clips to <b>128 × 32 pixels</b>. Each current activity icon is <b>20 × 16 pixels</b>, packed into 40 bytes. Native means one image pixel per CSS pixel; browser zoom and your display scaling determine physical size.</p>
<h2>Current inventory — actual bitmap bytes</h2><p>Exact main-menu order and English labels. “Music Playback” is the current Now Playing activity. Music Settings and System Settings are separate entries. Shuffle is the sixth entry added by the existing custom firmware.</p><div id="stock" class="grid"></div>
<h2>Two proposed pixel directions</h2><p><b>A · Crisp</b> uses simple outlined silhouettes, a play triangle, list bars, sliders and crossed Shuffle arrows. <b>B · Heavy</b> thickens the same shapes by one horizontal pixel for stronger visibility, at some cost to internal detail. These are alternatives to review, not final approved assets. Books and Meditation show prospective activity symbols; their presence here does not mean a menu shortcut exists.</p>
<div class="controls"><label>Direction <select id="direction"><option value="outline">A · Crisp</option><option value="bold">B · Heavy</option></select></label><label><input type="checkbox" id="inverse"> Selected / inverse</label></div><div id="proposed" class="grid"></div>
<h2>Your icon feedback</h2><p>Choose an icon direction, approve individual symbols or request changes, then copy the feedback back to the assistant. This review concerns icon artwork only; it does not approve new menus, shortcuts or navigation. Nothing is applied to firmware automatically.</p>
<div class="controls"><label>Overall decision <select id="decision"><option value="pending">Pending review</option><option value="crisp">Prefer A · Crisp</option><option value="heavy">Prefer B · Heavy</option><option value="current">Keep current icons</option><option value="mixed">Mixed / see individual feedback</option></select></label></div>
<div id="feedback" class="grid"></div><p><label for="general">General feedback</label><textarea id="general" rows="5" placeholder="Recognizability, stroke weight, contrast, any symbols to change…"></textarea></p>
<div class="controls"><button id="copy">Copy feedback</button><button id="download">Download feedback.txt</button></div><p id="status" role="status">Feedback is saved in this browser when local storage is available.</p><textarea id="export" rows="8" readonly aria-label="Feedback to copy"></textarea>
<div class="note">Recommended starting direction: A · Crisp, retaining the current 20 × 16 resource size. Selected previews use simple inversion; the native selection function also adds edge treatment. A later size increase needs layout work and separate approval. The display is only 32 pixels high.</div>
<footer><p>Regenerate: <code>python3 tools/preview_icons.py</code>. Full evidence: <a href="icons.md">icons.md</a>. Offline HTML; no fonts, scripts or images fetched from the network.</p><small>Audited stock SHA-256: HASH_VALUE</small></footer></main>
<script>const data=DATA_JSON;
function svg(rows,scale=1,inverse=false){let s=`<svg class="icon" width="${rows[0].length*scale}" height="${rows.length*scale}" viewBox="0 0 ${rows[0].length} ${rows.length}" shape-rendering="crispEdges" role="img" aria-label="Pixel icon"><rect width="100%" height="100%" fill="${inverse?'white':'black'}"/>`;rows.forEach((r,y)=>[...r].forEach((b,x)=>{if(b==='1')s+=`<rect x="${x}" y="${y}" width="1" height="1" fill="${inverse?'black':'white'}"/>`}));return s+'</svg>'}
function cards(id,items,inverse=false){document.getElementById(id).innerHTML=items.map((i,n)=>`<article class="card"><h3>${n+1}. ${i.label}</h3><div class="samples">${svg(i.pixels,1,inverse)}${svg(i.pixels,4,inverse)}</div><small>Native · 4× integer enlargement</small>${i.address?`<small>${i.address}<br>String ${i.sid}</small>`:''}</article>`).join('')}
const direction=document.getElementById('direction'), inverse=document.getElementById('inverse');
function update(){cards('stock',data.stock,inverse.checked);cards('proposed',data[direction.value],inverse.checked)}
cards('stock',data.stock);[direction,inverse].forEach(e=>e.addEventListener('change',update));update();
let saved={};try{saved=JSON.parse(localStorage.getItem('echo-nano-icon-review-v1')||'{}')}catch(e){}
const feedback=document.getElementById('feedback'),decision=document.getElementById('decision'),general=document.getElementById('general'),output=document.getElementById('export'),status=document.getElementById('status');
feedback.innerHTML=data.outline.map((i,n)=>`<article class="card"><h3>${i.label}</h3><label for="choice${n}">Decision</label><select id="choice${n}"><option value="pending">Pending review</option><option value="approve-crisp">Approve A · Crisp</option><option value="approve-heavy">Approve B · Heavy</option>${n<6?'<option value="keep-current">Keep current</option>':''}<option value="revise">Needs revision</option><option value="defer">Defer this icon</option></select><label for="comment${n}">Feedback</label><textarea id="comment${n}" rows="3" placeholder="What would you change?"></textarea></article>`).join('');
decision.value=saved.decision||'pending';general.value=saved.general||'';
data.outline.forEach((i,n)=>{document.getElementById('choice'+n).value=saved.icons?.[n]?.choice||'pending';document.getElementById('comment'+n).value=saved.icons?.[n]?.comment||''});
function collect(){return {review:'Echo Nano icon artwork v1',scope:'Icons only. No navigation or firmware changes approved.',decision:decision.value,icons:data.outline.map((i,n)=>({label:i.label,choice:document.getElementById('choice'+n).value,comment:document.getElementById('comment'+n).value})),general:general.value}}
function save(){const f=collect();output.value=JSON.stringify(f,null,2);try{localStorage.setItem('echo-nano-icon-review-v1',JSON.stringify(f))}catch(e){status.textContent='Browser storage unavailable. Copy or download your feedback to keep it.'}}
[decision,general,...feedback.querySelectorAll('select,textarea')].forEach(e=>e.addEventListener('input',save));save();
document.getElementById('copy').addEventListener('click',async()=>{save();try{await navigator.clipboard.writeText(output.value);status.textContent='Copied. Paste this feedback into the conversation.'}catch(e){output.focus();output.select();status.textContent='Clipboard unavailable here. Feedback selected: press Command+C / Ctrl+C, or Download.'}});
document.getElementById('download').addEventListener('click',()=>{save();const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([output.value],{type:'text/plain'}));a.download='echo-nano-icon-feedback.txt';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});
</script></html>'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock',type=Path,default=ROOT/'NANOV170.IMG')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/icon-review.html')
    args=parser.parse_args()
    generate(args.stock,args.output)


if __name__=='__main__':main()
