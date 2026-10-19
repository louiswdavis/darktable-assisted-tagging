"""Scratch probe (delete after use): prints each file's capture time with sub-seconds and the
interval to the previous file, to see whether burst cadence is readable.

Usage: python probe_subsec.py FILE_OR_FOLDER [more ...]   (files are sorted by name)
"""

import io
import os
import sys

from PIL import Image

DATETIME_ORIGINAL, SUBSEC_ORIGINAL, EXIF_IFD = 0x9003, 0x9291, 0x8769


def read_times(path: str) -> tuple:
    """(datetime string, subsec string, source) from the file itself, else its RAW preview."""
    tried = []
    try:
        exif = Image.open(path).getexif()
        ifd = exif.get_ifd(EXIF_IFD)
        if ifd.get(DATETIME_ORIGINAL):
            return ifd[DATETIME_ORIGINAL], str(ifd.get(SUBSEC_ORIGINAL, "")), "file"
        tried.append("file has no EXIF time")
    except Exception as e:
        tried.append(f"file: {e.__class__.__name__}")
    try:
        import rawpy
        with rawpy.imread(path) as raw:
            exif = Image.open(io.BytesIO(raw.extract_thumb().data)).getexif()
            ifd = exif.get_ifd(EXIF_IFD)
            if ifd.get(DATETIME_ORIGINAL):
                return ifd[DATETIME_ORIGINAL], str(ifd.get(SUBSEC_ORIGINAL, "")), "preview"
            tried.append("preview has no EXIF time")
    except Exception as e:
        tried.append(f"preview: {e.__class__.__name__}")
    return "", "", "; ".join(tried)


def seconds(dt: str, sub: str) -> float:
    h, m, s = (int(x) for x in dt.split(" ")[1].split(":"))
    return h * 3600 + m * 60 + s + (float("0." + sub) if sub.isdigit() else 0.0)


paths = []
for arg in sys.argv[1:]:
    paths += [os.path.join(arg, n) for n in sorted(os.listdir(arg))] if os.path.isdir(arg) else [arg]
prev = None
for p in paths:
    dt, sub, src = read_times(p)
    if not dt:
        print(f"{os.path.basename(p)}  no time ({src})")
        continue
    t = seconds(dt, sub)
    gap = "" if prev is None else f"  +{t - prev:.3f}s"
    print(f"{os.path.basename(p)}  {dt}.{sub or '??'}  [{src}]{gap}")
    prev = t
