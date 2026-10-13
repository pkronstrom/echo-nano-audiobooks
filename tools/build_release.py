#!/usr/bin/env python3
"""Build a deterministic patch-only release ZIP; never include complete firmware."""
import argparse
import json
from pathlib import Path
import subprocess
import zipfile

from apply_release import checked_image, compatible, date_value, reconstruct, sha
from rknano_fw import STOCK

ROOT = Path(__file__).resolve().parents[1]


def sparse_ranges(base, target):
    ranges = []
    start = None
    for i, (before, after) in enumerate(zip(base, target)):
        if before != after and start is None:
            start = i
        if before == after and start is not None:
            ranges.append({"offset": start, "hex": target[start:i].hex()})
            start = None
    if start is not None:
        ranges.append({"offset": start, "hex": target[start:].hex()})
    return ranges


def build(stock_path, target_path, output, icons=None, allow_dirty=False):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("release output already exists; choose a new filename")
    stock, target = Path(stock_path).read_bytes(), Path(target_path).read_bytes()
    if sha(stock) not in STOCK:
        raise ValueError("stock SHA-256 is not supported")
    base_image, target_image = checked_image(stock), checked_image(target)
    compatible(base_image, target_image)
    if date_value(target_image.date) <= date_value(base_image.date):
        raise ValueError("target date must be later than stock")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    if dirty and not allow_dirty:
        raise ValueError("source tree is dirty; commit release sources or explicitly use --allow-dirty for a candidate")
    man = dict(schema=1, base_sha256=sha(stock), target_sha256=sha(target), size=len(stock),
               default_date=target_image.date, source_commit=commit, source_dirty=dirty,
               ranges=sparse_ranges(stock, target))
    reconstruct(stock, man)
    files = {"patch.json": (json.dumps(man, sort_keys=True, indent=2) + "\n").encode()}
    for name in ("apply_release.py", "rknano_fw.py", "prepare_book.py"):
        files[name] = (ROOT / "tools" / name).read_bytes()
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    files["README.md"] = (ROOT / "docs/releases.md").read_bytes()
    book_guide = (ROOT / "docs/audiobooks.md").read_text(encoding="utf-8")
    # Keep the end-user guide independent of repository-only artifact paths,
    # historical build dates and compiler commands.
    book_guide = book_guide[book_guide.index("## Prepare a book"):book_guide.index("## Build\n")]
    book_guide = book_guide.replace("Run from this repository", "Run from the extracted patch folder")
    book_guide = book_guide.replace("python3 tools/prepare_book.py", "python3 prepare_book.py")
    files["audiobooks.md"] = ("# Book preparation and device checks\n\n" + book_guide).encode()
    files["approved-icons.json"] = (ROOT / "docs/approved-icons.json").read_bytes()
    for library in ("tabler", "lucide", "bootstrap"):
        files[f"licenses/{library}.txt"] = (ROOT / "docs/icon-library-assets" / library / "LICENSE").read_bytes()
    if icons:
        files["icon-review.html"] = Path(icons).read_bytes()
    files["SHA256SUMS"] = "".join(f"{sha(data)}  {name}\n" for name, data in sorted(files.items())).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        try:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for name, data in sorted(files.items()):
                    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    return {"archive": str(output), "sha256": sha(output.read_bytes()), "target_sha256": man["target_sha256"],
            "source_commit": commit, "source_dirty": dirty, "ranges": len(man["ranges"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Example: python3 tools/build_release.py --output builds/release/echo-nano-p3a.zip --icons docs/icon-review.html. Requires a locally built target; end users need only Python to apply the ZIP.")
    parser.add_argument("--stock", type=Path, default=ROOT / "NANOV170.IMG")
    parser.add_argument("--target", type=Path, default=ROOT / "out/audiobook/NANOV170.IMG")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--icons", type=Path, help="optional standalone icon review HTML")
    parser.add_argument("--allow-dirty", action="store_true", help="allow a clearly marked uncommitted candidate; avoid for public releases")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.stock, args.target, args.output, args.icons, args.allow_dirty), indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, "error: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
