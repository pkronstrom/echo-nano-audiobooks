#!/usr/bin/env python3
"""Assemble the checked audiobook test image and later-dated stock recovery."""
import argparse
from datetime import datetime,timedelta
from pathlib import Path
from playback_layout import integrate
from rknano_fw import Image

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stock',type=Path,default=Path('NANOV170.IMG'))
    p.add_argument('--base',type=Path,default=Path('out/NANOV170.IMG'))
    p.add_argument('--payload',type=Path,default=Path('out/playback'))
    p.add_argument('--output',type=Path,default=Path('out/audiobook/NANOV170.IMG'))
    p.add_argument('--date',default='20261013',help='YYYYMMDD, newer than the image installed on the device')
    a=p.parse_args()
    stock=a.stock.read_bytes()
    result=integrate(stock,a.base.read_bytes(),a.payload,a.date)
    recovery=Image(stock);recovery.set_date((datetime.strptime(a.date,'%Y%m%d')+timedelta(days=1)).strftime('%Y%m%d'));recovery.finalize()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(result)
    dest=a.output.parent/'recovery'/a.output.name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(recovery.d)
    print(f'Custom: {a.output} (P4a, {a.date})\nRecovery: {dest} ({recovery.date})')
if __name__=='__main__':main()
