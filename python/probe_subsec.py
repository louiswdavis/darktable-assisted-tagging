"""Scratch probe (delete after use): prints each TIFF-based RAW's capture time with sub-seconds
and the interval to the previous file, to see whether burst cadence is readable. Reads the EXIF
block directly, so it needs no packages (Sony .ARW, DNG, NEF, CR2 are all TIFF containers).

Usage: python probe_subsec.py FILE_OR_FOLDER [more ...]   (files are sorted by name)
"""

import os
import struct
import sys

HEAD_BYTES = 4_000_000
EXIF_IFD, DATETIME_ORIGINAL, SUBSEC_ORIGINAL = 0x8769, 0x9003, 0x9291
SKIP = (".xmp", ".txt")


def read_ifd(buf: bytes, offset: int, end: str) -> dict:
    """{tag: value} for one IFD; ASCII values as str, a LONG as int, anything else skipped."""
    (count,) = struct.unpack_from(end + "H", buf, offset)
    out = {}
    for i in range(count):
        tag, typ, n, val = struct.unpack_from(end + "HHI4s", buf, offset + 2 + i * 12)
        if typ == 2:  # ASCII
            raw = val[:n] if n <= 4 else buf[struct.unpack(end + "I", val)[0]:][:n]
            out[tag] = raw.split(b"\0")[0].decode("ascii", "replace").strip()
        elif typ == 4 and n == 1:  # LONG
            out[tag] = struct.unpack(end + "I", val)[0]
    return out


def read_times(path: str) -> tuple:
    """(datetime string, sub-second digits, error)."""
    with open(path, "rb") as f:
        buf = f.read(HEAD_BYTES)
    if buf[:2] not in (b"II", b"MM"):
        return "", "", "not a TIFF container"
    end = "<" if buf[:2] == b"II" else ">"
    try:
        (ifd0,) = struct.unpack_from(end + "I", buf, 4)
        exif = read_ifd(buf, read_ifd(buf, ifd0, end).get(EXIF_IFD, 0), end)
    except struct.error:
        return "", "", "EXIF block is outside the first %d bytes" % HEAD_BYTES
    return exif.get(DATETIME_ORIGINAL, ""), exif.get(SUBSEC_ORIGINAL, ""), "" if DATETIME_ORIGINAL in exif else "no EXIF time"


def seconds(dt: str, sub: str) -> float:
    h, m, s = (int(x) for x in dt.split(" ")[1].split(":"))
    return h * 3600 + m * 60 + s + (float("0." + sub) if sub.isdigit() else 0.0)


paths = []
for arg in sys.argv[1:]:
    paths += [os.path.join(arg, n) for n in sorted(os.listdir(arg))] if os.path.isdir(arg) else [arg]
prev = None
for p in paths:
    if p.lower().endswith(SKIP):
        continue
    dt, sub, err = read_times(p)
    if not dt:
        print(f"{os.path.basename(p)}  no time ({err})")
        continue
    t = seconds(dt, sub)
    gap = "" if prev is None else f"  +{t - prev:.3f}s"
    print(f"{os.path.basename(p)}  {dt}.{sub or '??'}{gap}")
    prev = t
