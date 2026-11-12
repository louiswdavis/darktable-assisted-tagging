# Run with: python python/test_common.py
# Exercises common.py and checks it is still the copy shared with the culling repo; stdlib only.

import hashlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

# Shared byte for byte with the culling repo: bump COMMON_SHA256 in its test_score_images.py too.
COMMON_SHA256 = "e18eed8d2048bb379ed2bdbb9d5292803bc589858750f00e529115bde0ae4480"

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


with open(common.__file__, "rb") as f:
    digest = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()
check("common.py matches the shared copy", digest, COMMON_SHA256)
# Shared byte for byte with the culling repo: bump VEHICLE_DETECT_SHA256 in its test_score_images.py too.
VEHICLE_DETECT_SHA256 = "b1c2d1d6da0d9458a24108990f3a2c53c5b2ac294127adf391f4e966a0997180"
with open(os.path.join(os.path.dirname(common.__file__), "vehicle_detect.py"), "rb") as f:
    digest = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()
check("vehicle_detect.py matches the shared copy", digest, VEHICLE_DETECT_SHA256)
check("RAW_EXTENSIONS has the dot form", ".arw" in common.RAW_EXTENSIONS and "arw" not in common.RAW_EXTENSIONS, True)
check("RAW_EXTENSIONS count", len(common.RAW_EXTENSIONS), 32)

with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "x.txt")
    with open(p, "w") as f:
        f.write("old")
    try:
        with common.atomic_write(p) as f:
            f.write("new")
            raise RuntimeError("abort")
    except RuntimeError:
        pass
    with open(p) as f:
        check("atomic_write keeps the old file on failure", f.read(), "old")
    with common.atomic_write(p) as f:
        f.write("new")
    with open(p) as f:
        check("atomic_write replaces on success", f.read(), "new")
    with common.atomic_write(os.path.join(d, "b.bin"), "wb") as f:
        f.write(b"\x00\xff")
    with open(os.path.join(d, "b.bin"), "rb") as f:
        check("atomic_write binary mode", f.read(), b"\x00\xff")
    check("atomic_write leaves no temp file", sorted(os.listdir(d)), ["b.bin", "x.txt"])

print("")
if failures == 0:
    print("all tests passed")
    sys.exit(0)
print(f"{failures} test(s) failed")
sys.exit(1)
