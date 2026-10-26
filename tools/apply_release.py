#!/usr/bin/env python3
"""Apply a checked Echo Nano patch bundle using Python 3.10+ only."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import tempfile

from rknano_fw import Image, STOCK


def sha(data):
    return hashlib.sha256(data).hexdigest()


def date_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}", value):
        raise ValueError("date must be YYYYMMDD")
    try:
        result = dt.date(int(value[:4]), int(value[4:6]), int(value[6:]))
        result + dt.timedelta(days=1)
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid date or no later recovery date") from exc
    return result


def validate_manifest(man):
    fields = {"schema", "base_sha256", "target_sha256", "size", "default_date", "source_commit", "source_dirty", "ranges"}
    if not isinstance(man, dict) or set(man) != fields or type(man["schema"]) is not int or man["schema"] != 1:
        raise ValueError("unsupported patch manifest schema")
    for key in ("base_sha256", "target_sha256"):
        if not isinstance(man[key], str) or not re.fullmatch(r"[0-9a-f]{64}", man[key]):
            raise ValueError("invalid SHA-256")
    if man["base_sha256"] not in STOCK:
        raise ValueError("patch does not target supported official stock")
    if type(man["size"]) is not int or not 1024 <= man["size"] <= 32 * 1024 * 1024:
        raise ValueError("invalid image size")
    if not isinstance(man["source_commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", man["source_commit"]):
        raise ValueError("invalid source commit")
    if type(man["source_dirty"]) is not bool:
        raise ValueError("invalid source state")
    date_value(man["default_date"])
    if not isinstance(man["ranges"], list) or not man["ranges"]:
        raise ValueError("missing patch ranges")
    end = 0
    changes = []
    for entry in man["ranges"]:
        if not isinstance(entry, dict) or set(entry) != {"offset", "hex"}:
            raise ValueError("invalid patch range schema")
        off, raw = entry["offset"], entry["hex"]
        if type(off) is not int or not isinstance(raw, str) or not re.fullmatch(r"(?:[0-9a-f]{2})+", raw):
            raise ValueError("invalid patch range encoding")
        data = bytes.fromhex(raw)
        if off < end or off + len(data) > man["size"]:
            raise ValueError("patch ranges overlap, are unordered, or exceed image bounds")
        changes.append((off, data))
        end = off + len(data)
    return changes


def checked_image(data):
    try:
        if len(data) < 0x208 or len(data) > 32 * 1024 * 1024:
            raise ValueError("malformed firmware image size")
        count = struct.unpack_from("<I", data, 0x204)[0]
        fw_len = struct.unpack_from("<I", data, 0x1f4)[0]
        if count > 1024 or 0x208 + count * 32 > len(data) or not 0x208 <= fw_len <= len(data) - 0x204:
            raise ValueError("malformed firmware table or header offset")
        image = Image(data)
        if not image.header_copy_ok() or image.crc_stored() != image.crc_calc():
            raise ValueError("firmware CRC or header copy mismatch")
    except (IndexError, OverflowError, struct.error) as exc:
        raise ValueError("malformed firmware image") from exc
    return image


def compatible_modules(base, target):
    if base.modules == target.modules:
        return True
    # Standalone copy of the audited module31 exception; no build-tool imports.
    # Native code stays at its original execution address. Only its backing and
    # appended helper length may change (docs/folder-sort-memory-audit.md).
    if (len(base.modules) != len(target.modules) or len(base.modules) <= 31 or
            sha(base.d) != '54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116'):
        return False
    original = dict(index=31, code_load=0x030b5648, code_exec=0x03079418,
                    code_len=9308, data_load=0x030b7aa4, data_exec=0x0300e6bc,
                    data_len=128, bss_exec=0x0300e73c, bss_len=2150)
    moved = target.modules[31]
    length = moved['code_len'] - 9308
    expected = dict(original, code_load=0x0308ce00, code_len=moved['code_len'])
    if (base.modules[31] != original or moved != expected or
            any(a != b for i, (a, b) in enumerate(zip(base.modules, target.modules)) if i != 31) or
            not 16 <= length <= 14060 or length % 4 or
            base.l2f(moved['code_load']) != 0x3d000 or
            any(base.d[0x3d000:0x42b48])):
        return False
    magic, entry, code_end, bss_end = struct.unpack_from('<4I', target.d, 0x3d000 + 9308)
    return (magic == 0x314f5342 and entry & 1 and
            0x0307b884 <= (entry & ~1) < code_end and
            code_end == 0x0307b874 + length and
            code_end <= bss_end <= 0x03080470)


def compatible(base, target):
    if (len(base.d) != len(target.d) or base.fw_len != target.fw_len or
            base.load_base != target.load_base or base.sections != target.sections or
            not compatible_modules(base, target)):
        raise ValueError("target firmware layout differs from stock")
    for section in base.sections:
        # Language strings are deliberately patched; graphics/fonts remain stock.
        if section["name"] == "lang":
            continue
        off, length = section["offset"], section["length"]
        if base.d[off:off + length] != target.d[off:off + length]:
            raise ValueError("target changes protected resource: " + section["name"])


def reconstruct(stock, man):
    changes = validate_manifest(man)
    if len(stock) != man["size"] or sha(stock) != man["base_sha256"]:
        raise ValueError("input is not the exact supported official NANOV170.IMG (SHA-256 mismatch)")
    base = checked_image(stock)
    data = bytearray(stock)
    for off, part in changes:
        data[off:off + len(part)] = part
    if sha(data) != man["target_sha256"]:
        raise ValueError("patched target SHA-256 mismatch; bundle is damaged")
    target = checked_image(data)
    compatible(base, target)
    if target.date != man["default_date"]:
        raise ValueError("manifest date differs from verified target")
    return base, target


def apply(stock_path, output, manifest_path, date=None):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("output already exists; choose a new directory (nothing overwritten)")
    man = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    validate_manifest(man)
    requested = date_value(date or man["default_date"])
    base, target = reconstruct(Path(stock_path).read_bytes(), man)
    if requested <= date_value(base.date):
        raise ValueError("custom date must be later than original stock date")
    custom_date = requested.strftime("%Y%m%d")
    recovery_date = (requested + dt.timedelta(days=1)).strftime("%Y%m%d")
    target.set_date(custom_date)
    target.finalize()
    base.set_date(recovery_date)
    base.finalize()
    report = {"custom_date": custom_date, "recovery_date": recovery_date,
              "source_commit": man["source_commit"], "source_dirty": man["source_dirty"],
              "files": {"custom/NANOV170.IMG": sha(target.d), "recovery/NANOV170.IMG": sha(base.d)}}
    # Stage outside the destination; reserve it exclusively only after validation.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".echo-release-", dir=output.parent) as work:
        staged = Path(work)
        for folder, data in (("custom", target.d), ("recovery", base.d)):
            (staged / folder).mkdir()
            (staged / folder / "NANOV170.IMG").write_bytes(data)
        (staged / "checksums.json").write_text(json.dumps(report, indent=2) + "\n")
        output.mkdir()  # Fails safely if another process has created it.
        try:
            for item in staged.iterdir():
                shutil.move(str(item), output / item.name)
        except BaseException:
            shutil.rmtree(output)
            raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Example: python3 apply_release.py --input ~/Downloads/NANOV170.IMG --output ./nano-ready --date 20261014. Never flashes a device. Choose a date newer than installed firmware; recovery is dated one day later.")
    parser.add_argument("--input", required=True, type=Path, help="original official FiiO V1.7.0 NANOV170.IMG; never modified")
    parser.add_argument("--output", required=True, type=Path, help="new directory for custom/ and recovery/ images; must not exist")
    parser.add_argument("--date", help="YYYYMMDD, default: the release build date in patch.json")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("patch.json"), help="patch manifest (default: beside this script)")
    args = parser.parse_args()
    try:
        print(json.dumps(apply(args.input, args.output, args.manifest, args.date), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, "error: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
