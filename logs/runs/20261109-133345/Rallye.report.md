# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

381 vehicles/images, identified rate 30%

- identified: 114 (30%)
- team-obvious: 0 (0%)
- weak-match: 0 (0%)
- no-references: 224 (59%)
- number-unmatched: 0 (0%)
- conflict: 0 (0%)
- overlapped: 33 (9%)
- already-tagged: 0 (0%)
- no-vehicle: 10 (3%)

## detector score

- 0.00-0.30: 29 boxes, 3 identified
- 0.30-0.40: 15 boxes, 4 identified
- 0.40-0.50: 15 boxes, 0 identified
- 0.50-0.70: 35 boxes, 5 identified
- 0.70-1.00: 277 boxes, 102 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one tag prefix only; add under `rules.sponsor_keywords` after checking:
- `diesel` → `Sports|Hill Climb|Rallye Prescott|86`: 2 identified, would hint 0 unidentified

## bursts (33 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×15, 1s ×17, 2s ×1
frames per burst: 4, 4, 4, 4, 6, 6, 6, 6, 8, 8, 8, 8, 8, 8, 10, 10, 10, 10, 10, 10, 10, 10, 12, 12, 12, 12, 12, 14, 14, 16, 18, 20, 22

closest to the next burst (possible split):
- burst 6: 18 frames, next burst starts 2s later
- burst 15: 10 frames, next burst starts 2s later
- burst 21: 10 frames, next burst starts 3s later
- burst 24: 4 frames, next burst starts 3s later
- burst 27: 12 frames, next burst starts 3s later
- burst 30: 6 frames, next burst starts 3s later
- burst 9: 8 frames, next burst starts 5s later
- burst 13: 10 frames, next burst starts 5s later
- burst 3: 16 frames, next burst starts 9s later
- burst 7: 20 frames, next burst starts 10s later
- burst 11: 22 frames, next burst starts 10s later
- burst 25: 10 frames, next burst starts 10s later
- burst 5: 8 frames, next burst starts 11s later
- burst 14: 4 frames, next burst starts 11s later
- burst 22: 4 frames, next burst starts 11s later
- burst 31: 12 frames, next burst starts 11s later
- burst 10: 10 frames, next burst starts 13s later
- burst 28: 14 frames, next burst starts 13s later
- burst 2: 12 frames, next burst starts 14s later
- burst 19: 12 frames, next burst starts 14s later

largest within-burst gap (possible merge):
- burst 3: 16 frames over 3s, largest gap 2s, 16 with vehicles, 0 without
- burst 2: 12 frames over 1s, largest gap 1s, 12 with vehicles, 0 without
- burst 6: 18 frames over 1s, largest gap 1s, 18 with vehicles, 0 without
- burst 7: 20 frames over 2s, largest gap 1s, 18 with vehicles, 2 without
- burst 8: 10 frames over 1s, largest gap 1s, 10 with vehicles, 0 without
- burst 9: 8 frames over 1s, largest gap 1s, 8 with vehicles, 0 without
- burst 10: 10 frames over 1s, largest gap 1s, 10 with vehicles, 0 without
- burst 11: 22 frames over 1s, largest gap 1s, 22 with vehicles, 0 without
- burst 12: 8 frames over 1s, largest gap 1s, 8 with vehicles, 0 without
- burst 15: 10 frames over 1s, largest gap 1s, 10 with vehicles, 0 without
- burst 18: 10 frames over 1s, largest gap 1s, 10 with vehicles, 0 without
- burst 19: 12 frames over 1s, largest gap 1s, 12 with vehicles, 0 without
- burst 21: 10 frames over 1s, largest gap 1s, 10 with vehicles, 0 without
- burst 23: 10 frames over 1s, largest gap 1s, 8 with vehicles, 2 without
- burst 25: 10 frames over 1s, largest gap 1s, 7 with vehicles, 3 without
- burst 28: 14 frames over 1s, largest gap 1s, 14 with vehicles, 0 without
- burst 32: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 33: 14 frames over 1s, largest gap 1s, 14 with vehicles, 0 without
- burst 1: 8 frames over 0s, largest gap 0s, 8 with vehicles, 0 without
- burst 4: 6 frames over 0s, largest gap 0s, 6 with vehicles, 0 without

## no-references (224)

- `202550` box 0: no candidates; no_references; detector 0.90; ocr saw `dao7zbe` 0.99, `eeoass` 0.96; pod black (yellow 0.000, aspect 1.5); lever: no references yet, add some
- `202551` box 0: no candidates; no_references; detector 0.91; ocr saw `dao7zbe` 0.99, `lnceanees` 0.98, `es` 0.96; pod unclear (yellow 0.001, aspect 1.5); lever: no references yet, add some
- `202552` box 0: no candidates; no_references; detector 0.23; ocr saw `tim` 0.98; pod unclear (yellow 0.000, aspect 1.0); lever: no references yet, add some
- `202552` box 1: no candidates; no_references; detector 0.92; ocr saw `dao7zbe` 0.99, `lessenees` 0.96; pod black (yellow 0.000, aspect 1.5); lever: no references yet, add some
- `202554` box 0: no candidates; no_references; detector 0.90; ocr saw `dao7zbe` 0.99, `nceceers` 0.97, `n` 0.88; pod black (yellow 0.000, aspect 1.5); lever: no references yet, add some
- `202555` box 0: no candidates; no_references; detector 0.89; ocr saw `daotzbe` 0.99, `tensaaaes` 0.97, `acecanes` 0.96; pod unclear (yellow 0.001, aspect 1.5); lever: no references yet, add some
- `202556` box 0: no candidates; no_references; detector 0.92; ocr saw `dao7zbe` 0.99, `encreness` 0.96, `mae` 0.87; pod black (yellow 0.000, aspect 1.6); lever: no references yet, add some
- `202557` box 0: no candidates; no_references; detector 0.28; ocr saw `tim` 0.99; pod unclear (yellow 0.000, aspect 1.0); lever: no references yet, add some
- `202562` box 0: no candidates; no_references; detector 0.60; ocr saw `b0` 0.99; pod black (yellow 0.000, aspect 1.5); lever: no references yet, add some
- `202563` box 0: no candidates; no_references; detector 0.65; ocr saw `b0` 0.99, `rca3o7b` 0.98; pod black (yellow 0.000, aspect 1.5); lever: no references yet, add some
- `202564` box 0: no candidates; no_references; detector 0.75; ocr saw `b0` 0.99; pod black (yellow 0.000, aspect 1.7); lever: no references yet, add some
- `202565` box 0: no candidates; no_references; detector 0.63; ocr saw `b30` 0.99, `rea307` 0.90; pod black (yellow 0.000, aspect 1.7); lever: no references yet, add some
- `202566` box 0: no candidates; no_references; detector 0.74; ocr saw `b0` 0.99; pod black (yellow 0.000, aspect 1.9); lever: no references yet, add some
- `202568` box 0: no candidates; no_references; detector 0.86; ocr saw `b30` 0.99; pod black (yellow 0.000, aspect 2.0); lever: no references yet, add some
- `202569` box 0: no candidates; no_references; detector 0.84; read `736`; pod black (yellow 0.000, aspect 2.0); lever: no references yet, add some
- `202582` box 0: no candidates; no_references; detector 0.77; ocr saw no text; pod black (yellow 0.000, aspect 1.5); lever: no references yet, add some
- `202583` box 0: no candidates; no_references; detector 0.79; ocr saw `rca307b` 0.99; pod black (yellow 0.001, aspect 1.5); lever: no references yet, add some
- `202584` box 0: no candidates; no_references; detector 0.88; ocr saw no text; pod black (yellow 0.000, aspect 1.5); lever: no references yet, add some
- `202585` box 0: no candidates; no_references; detector 0.85; ocr saw `rca307b` 0.99, `tt` 0.88; pod black (yellow 0.000, aspect 1.5); lever: no references yet, add some
- `202586` box 0: no candidates; no_references; detector 0.43; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); lever: no references yet, add some
- … 204 more in report.json

## overlapped (33)

- `202628` box 1: no candidates; overlapped; detector 0.48; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3)
- `202629` box 1: no candidates; overlapped; detector 0.41; ocr saw `sex` 0.81; pod unclear (yellow 0.000, aspect 1.3)
- `202632` box 1: no candidates; overlapped; detector 0.71; ocr saw `ks` 0.91; pod unclear (yellow 0.000, aspect 1.1)
- `202632` box 2: no candidates; overlapped; detector 0.45; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `202633` box 1: no candidates; overlapped; detector 0.72; ocr saw `k13` 0.97; pod unclear (yellow 0.000, aspect 1.2)
- `202633` box 2: no candidates; overlapped; detector 0.45; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `202638` box 1: no candidates; overlapped; detector 0.71; ocr saw `f75` 0.98; pod unclear (yellow 0.000, aspect 1.3)
- `202642` box 1: no candidates; overlapped; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2)
- `202643` box 1: no candidates; overlapped; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2)
- `202670` box 1: no candidates; overlapped; detector 0.37; ocr saw `l7band` 0.99; pod unclear (yellow 0.000, aspect 0.9)
- `202671` box 1: no candidates; overlapped; detector 0.43; ocr saw `l7band` 0.99; pod unclear (yellow 0.000, aspect 0.9)
- `202672` box 1: no candidates; overlapped; detector 0.47; read `76`; pod black (yellow 0.000, aspect 1.7)
- `202673` box 1: no candidates; overlapped; detector 0.46; read `76`; pod black (yellow 0.000, aspect 1.6)
- `202740` box 0: no candidates; overlapped; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 2.3)
- `202742` box 0: no candidates; overlapped; detector 0.24; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- `202743` box 1: no candidates; overlapped; detector 0.94; ocr saw `a` 0.96; pod black (yellow 0.000, aspect 1.9)
- `202746` box 1: no candidates; overlapped; detector 0.90; ocr saw no text; pod black (yellow 0.000, aspect 2.2)
- `202747` box 1: no candidates; overlapped; detector 0.90; ocr saw no text; pod black (yellow 0.000, aspect 2.2)
- `202764` box 1: no candidates; overlapped; detector 0.27; read `79`; pod black (yellow 0.000, aspect 2.9)
- `202765` box 1: no candidates; overlapped; detector 0.29; read `79`; pod black (yellow 0.000, aspect 2.9)
- … 13 more in report.json

## no-vehicle (10)

- `202592` burst 5: no vehicle at 0.2: strongest car 0.51 (0.09x0.05 of frame), strongest vehicle car 0.51 (0.09x0.05 of frame)
- `202593` burst 5: no vehicle at 0.2: strongest car 0.48 (0.10x0.05 of frame), strongest vehicle car 0.48 (0.10x0.05 of frame)
- `202594` burst 5: no vehicle at 0.2: strongest car 0.78 (0.10x0.05 of frame), strongest vehicle car 0.78 (0.10x0.05 of frame)
- `202644` burst 7: no vehicle at 0.2: strongest person 0.85 (0.17x0.52 of frame), strongest vehicle motorcycle 0.16 (0.48x0.32 of frame)
- `202645` burst 7: no vehicle at 0.2: strongest person 0.85 (0.17x0.52 of frame), strongest vehicle motorcycle 0.13 (0.48x0.32 of frame)
- `202790` burst 23: no vehicle at 0.2: strongest train 0.22 (1.00x0.55 of frame), strongest vehicle car 0.13 (1.00x0.57 of frame)
- `202791` burst 23: no vehicle at 0.2: strongest train 0.23 (1.00x0.55 of frame), strongest vehicle car 0.15 (1.00x0.58 of frame)
- `202800` burst 25: no vehicle at 0.2: strongest person 0.21 (0.23x0.14 of frame), strongest vehicle car 0.15 (0.24x0.12 of frame)
- `202804` burst 25: no vehicle at 0.2: strongest person 0.19 (0.23x0.21 of frame), strongest vehicle car 0.11 (0.22x0.14 of frame)
- `202805` burst 25: no vehicle at 0.2: strongest person 0.31 (0.23x0.28 of frame), strongest vehicle car 0.04 (0.22x0.19 of frame)
