"""Verify the exact crypto integration changes against pinned upstream files."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

VENDOR = Path(__file__).resolve().parents[1] / "vendor"

for name in ("snow", "libcrux-platform"):
    manifest = json.loads((VENDOR / f"{name}-upstream.json").read_text())
    hashes = manifest.get("files", manifest)
    with tempfile.TemporaryDirectory(prefix="voicevault-vendor-") as scratch:
        restored = Path(scratch) / name
        shutil.copytree(VENDOR / name, restored)
        subprocess.run(["git", "apply", "--reverse", "--whitespace=nowarn",
                        str(VENDOR / f"{name}-voicevault.patch")],
                       cwd=restored, check=True)
        files = {str(p.relative_to(restored)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in restored.rglob("*") if p.is_file()}
        assert files == hashes, f"{name} differs from upstream plus its recorded patch"
        print(f"PASS: {name}, {len(files)} upstream file hashes and exact local patch")
