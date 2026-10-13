#!/usr/bin/env python3
"""Generate the offline icon review from audited Nano firmware resources.

No firmware is modified. Python standard library only.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from rknano_fw import load, stock_name
from icon_proposals import variants as variants_v2
from icon_proposals_v3 import variants

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
    references={}
    for key,letter in [('shuffle','D'),('books','B'),('meditation','D')]:
        old=next(s for s in variants_v2() if s['id']==letter)
        icon=next(i for i in old['icons'] if i['kind']==key)
        references[key]=dict(id='v2-'+letter,label='Preferred v2 '+letter+' · '+icon['symbol'],pixels=icon['pixels'])
    references['musicsettings']=dict(id='v1-crisp',label='Round 1 Crisp · preferred direction',pixels=proposal('musicsettings'))
    data=dict(stock=icons,groups=[dict(g,label=labels[kinds.index(g['id'])],reference=references.get(g['id'])) for g in variants()],
              previous=json.loads((ROOT/'docs/reviews/icon-feedback-v2.json').read_text()))
    page=TEMPLATE.replace('DATA_JSON',json.dumps(data)).replace('HASH_VALUE',hashlib.sha256(Path(stock).read_bytes()).hexdigest())
    output.write_text(page)
    print(f'Wrote {output}; 5 decoded stock + 1 existing patch + 32 revised icons + preferred references')


TEMPLATE=(ROOT/'tools/icon_review_template.html').read_text(encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock',type=Path,default=ROOT/'NANOV170.IMG')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/icon-review.html')
    args=parser.parse_args()
    generate(args.stock,args.output)


if __name__=='__main__':main()
