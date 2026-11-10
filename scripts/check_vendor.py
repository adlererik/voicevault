"""Constrain the local Opus port to initialization-only additions."""
from pathlib import Path
import difflib
import hashlib
import json
import re

root = Path(__file__).resolve().parents[1]
vendor = root / "vendor/opus-rs"
hashes = json.loads((root / "vendor/opus-rs-original-files.json").read_text())
assert set(hashes) == {str(p.relative_to(vendor)) for p in vendor.rglob("*") if p.is_file()}
patch = ""
for name, expected in hashes.items():
    data = (vendor / name).read_bytes()
    if name in ("src/lib.rs", "src/celt.rs"):
        source = data.decode()
        begin = source.index("    /// Quietlink port:")
        end = source.index("    pub fn new(" if name.endswith("lib.rs") else "    pub fn with_sampling_rate(", begin)
        # The original CELT method's documentation precedes our insertion.
        original = source[:begin] + source[end:]
        data = original.encode()
        patch += "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                            fromfile="opus-rs-0.1.41/" + name,
                                            tofile="opus-rs-0.1.41/" + name))
        kind = "OpusEncoder" if name.endswith("lib.rs") else "CeltEncoder"
        structure = source.split("pub struct " + kind + " {", 1)[1].split("\n}", 1)[0]
        structure = re.sub(r'    #\[cfg\(feature = "heap"\)\]\n    [^\n]+\n', "", structure)
        fields = re.findall(r"^    (?:pub )?(\w+):", structure, re.M)
        initializer = source[begin:end]
        written = re.findall(r"\(\*this\)\.(\w+)\)\.write\(", initializer)
        written += re.findall(r"(?:write_from_value|write_new_voip16k)\(&raw mut \(\*this\)\.(\w+)[,)]", initializer)
        assert sorted(fields) == sorted(written), (kind, "each field initialized exactly once", fields, written)
    assert hashlib.sha256(data).hexdigest() == expected, name
# Compare sorted file order, independent of manifest ordering.
expected_patch = (root / "vendor/opus-rs-inplace.patch").read_text()
assert set(patch.split("--- ")[1:]) == set(expected_patch.split("--- ")[1:]), "patch drift"
print(f"PASS: {len(hashes)} upstream files verified; initialization-only patch; encoder field coverage verified")
