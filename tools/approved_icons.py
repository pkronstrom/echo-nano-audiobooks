"""Frozen user-selected 20×16 icons; no renderer is needed at firmware build time.

apply_icons mutates only six checked existing bitmap locations, after validating
all of them. Caller owns final CRC/header recomputation. Optional book/candle
bytes are exposed for menu integration, not installed by this helper.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs/approved-icons.json'
STOCK_SHA256 = '54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116'


def encode(rows):
    if len(rows) != 16 or any(len(r) != 20 or set(r) - {'0', '1'} for r in rows):
        raise ValueError('expected sixteen rows of twenty binary pixels')
    return bytes(sum((rows[page * 8 + bit][x] == '1') << bit for bit in range(8))
                 for page in range(2) for x in range(20))


def decode(data):
    if len(data) != 40:
        raise ValueError('expected forty icon bytes')
    return [''.join('1' if data[(y // 8) * 20 + x] & (1 << (y % 8)) else '0'
                    for x in range(20)) for y in range(16)]


def load_manifest():
    manifest = json.loads(MANIFEST.read_text())
    if manifest['format'] != 'echo-nano-approved-icons-v1':
        raise ValueError('unknown approved icon format')
    for icon in manifest['icons']:
        blob = encode(icon['pixels'])
        if blob.hex() != icon['bitmap_hex'] or hashlib.sha256(blob).hexdigest() != icon['bitmap_sha256']:
            raise ValueError('approved icon bitmap checksum mismatch: ' + icon['id'])
    return manifest


def icon_bytes(kind):
    for icon in load_manifest()['icons']:
        if icon['id'] == kind:
            return bytes.fromhex(icon['bitmap_hex'])
    raise ValueError('unknown approved icon: ' + kind)


def apply_icons(image, stock):
    """Apply to rknano_fw.Image objects; return the six changed locations."""
    if hashlib.sha256(stock.d).hexdigest() != STOCK_SHA256:
        raise ValueError('approved icons require pinned stock V1.7.0')
    if len(image.d) != len(stock.d) or image.modules != stock.modules or image.sections != stock.sections:
        raise ValueError('approved icon firmware layout changed')
    staged = []
    for icon in load_manifest()['icons']:
        target = icon['target']
        if target is None:
            continue
        offset, _ = image.region(target['module'], target['address'])
        expected = bytes.fromhex(target['expected_hex'])
        if len(expected) != 40 or image.d[offset:offset + 40] != expected:
            raise ValueError('unexpected existing bitmap: ' + icon['id'])
        if target['module'] == 0:
            stock_offset, _ = stock.region(target['module'], target['address'])
            if stock.d[stock_offset:stock_offset + 40] != expected:
                raise ValueError('icon manifest does not match stock')
        staged.append((icon, offset))
    for icon, offset in staged:
        image.d[offset:offset + 40] = bytes.fromhex(icon['bitmap_hex'])
    return [dict(id=icon['id'], module=icon['target']['module'], address=icon['target']['address'])
            for icon, _ in staged]
