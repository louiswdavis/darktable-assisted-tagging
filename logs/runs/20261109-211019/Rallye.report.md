# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

2069 vehicles/images, identified rate 18%

- identified: 380 (18%)
- team-obvious: 0 (0%)
- weak-match: 0 (0%)
- no-references: 1477 (71%)
- number-unmatched: 0 (0%)
- conflict: 0 (0%)
- overlapped: 93 (4%)
- already-tagged: 0 (0%)
- no-vehicle: 119 (6%)

## detector score

- 0.00-0.30: 75 boxes, 2 identified
- 0.30-0.40: 47 boxes, 4 identified
- 0.40-0.50: 46 boxes, 6 identified
- 0.50-0.70: 146 boxes, 29 identified
- 0.70-1.00: 1636 boxes, 339 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one tag prefix only; add under `rules.sponsor_keywords` after checking:
- `maynard` → `Sports|Hill Climb|Rallye Prescott|22`: 16 identified, would hint 10 unidentified
- `piaa` → `Sports|Hill Climb|Rallye Prescott|28`: 3 identified, would hint 4 unidentified
- `hella` → `Sports|Hill Climb|Rallye Prescott|58`: 8 identified, would hint 0 unidentified
- `cibie` → `Sports|Hill Climb|Rallye Prescott|44`: 7 identified, would hint 0 unidentified
- `colwynbay` → `Sports|Hill Climb|Rallye Prescott|62`: 6 identified, would hint 0 unidentified
- `dunloptyres` → `Sports|Hill Climb|Rallye Prescott|58`: 6 identified, would hint 0 unidentified
- `motul` → `Sports|Hill Climb|Rallye Prescott|44`: 6 identified, would hint 0 unidentified
- `llookers` → `Sports|Hill Climb|Rallye Prescott|62`: 4 identified, would hint 0 unidentified
- `andyz` → `Sports|Hill Climb|Rallye Prescott|27`: 3 identified, would hint 0 unidentified
- `knott` → `Sports|Hill Climb|Rallye Prescott|25`: 3 identified, would hint 0 unidentified
- `llandudno` → `Sports|Hill Climb|Rallye Prescott|62`: 3 identified, would hint 0 unidentified
- `llooke` → `Sports|Hill Climb|Rallye Prescott|62`: 3 identified, would hint 0 unidentified
- `sparco` → `Sports|Hill Climb|Rallye Prescott|62`: 3 identified, would hint 0 unidentified
- `audisport` → `Sports|Hill Climb|Rallye Prescott|94`: 2 identified, would hint 0 unidentified
- `bilstein` → `Sports|Hill Climb|Rallye Prescott|94`: 2 identified, would hint 0 unidentified
- `colwyn` → `Sports|Hill Climb|Rallye Prescott|62`: 2 identified, would hint 0 unidentified
- `driving` → `Sports|Hill Climb|Rallye Prescott|25`: 2 identified, would hint 0 unidentified
- `networko` → `Sports|Hill Climb|Rallye Prescott|3`: 2 identified, would hint 0 unidentified
- `ookers` → `Sports|Hill Climb|Rallye Prescott|62`: 2 identified, would hint 0 unidentified
- `otoyota` → `Sports|Hill Climb|Rallye Prescott|5`: 2 identified, would hint 0 unidentified

## bursts (328 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×146, 1s ×152, 2s ×29, 541s ×1
frames per burst: 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 10, 10, 10, 10, 10, 10, 10, 10, 11, 11, 12, 12, 13, 13, 13, 13, 13, 13, 14, 14, 15, 15, 15, 15, 15, 15, 18, 22, 23, 216

closest to the next burst (possible split):
- burst 298: 216 frames, next burst starts -1191s later
- burst 38: 6 frames, next burst starts 2s later
- burst 52: 13 frames, next burst starts 2s later
- burst 57: 7 frames, next burst starts 2s later
- burst 59: 6 frames, next burst starts 2s later
- burst 77: 2 frames, next burst starts 2s later
- burst 86: 3 frames, next burst starts 2s later
- burst 105: 5 frames, next burst starts 2s later
- burst 150: 2 frames, next burst starts 2s later
- burst 188: 5 frames, next burst starts 2s later
- burst 192: 4 frames, next burst starts 2s later
- burst 206: 2 frames, next burst starts 2s later
- burst 218: 5 frames, next burst starts 2s later
- burst 280: 5 frames, next burst starts 2s later
- burst 282: 2 frames, next burst starts 2s later
- burst 287: 2 frames, next burst starts 2s later
- burst 290: 2 frames, next burst starts 2s later
- burst 303: 1 frames, next burst starts 2s later
- burst 326: 5 frames, next burst starts 2s later
- burst 5: 5 frames, next burst starts 3s later

largest within-burst gap (possible merge):
- burst 298: 216 frames over 1711s, largest gap 541s, 216 with vehicles, 0 without
- burst 2: 9 frames over 2s, largest gap 2s, 8 with vehicles, 1 without
- burst 23: 9 frames over 4s, largest gap 2s, 9 with vehicles, 0 without
- burst 26: 6 frames over 2s, largest gap 2s, 3 with vehicles, 3 without
- burst 58: 9 frames over 4s, largest gap 2s, 6 with vehicles, 3 without
- burst 59: 6 frames over 3s, largest gap 2s, 6 with vehicles, 0 without
- burst 61: 5 frames over 2s, largest gap 2s, 5 with vehicles, 0 without
- burst 68: 5 frames over 3s, largest gap 2s, 5 with vehicles, 0 without
- burst 75: 8 frames over 2s, largest gap 2s, 8 with vehicles, 0 without
- burst 76: 10 frames over 4s, largest gap 2s, 10 with vehicles, 0 without
- burst 109: 4 frames over 2s, largest gap 2s, 4 with vehicles, 0 without
- burst 133: 15 frames over 7s, largest gap 2s, 15 with vehicles, 0 without
- burst 149: 9 frames over 2s, largest gap 2s, 5 with vehicles, 4 without
- burst 151: 6 frames over 2s, largest gap 2s, 4 with vehicles, 2 without
- burst 157: 3 frames over 2s, largest gap 2s, 3 with vehicles, 0 without
- burst 165: 4 frames over 2s, largest gap 2s, 4 with vehicles, 0 without
- burst 170: 8 frames over 3s, largest gap 2s, 8 with vehicles, 0 without
- burst 172: 5 frames over 2s, largest gap 2s, 5 with vehicles, 0 without
- burst 186: 6 frames over 4s, largest gap 2s, 6 with vehicles, 0 without
- burst 193: 4 frames over 2s, largest gap 2s, 4 with vehicles, 0 without

## no-references (1477)

- `203007` box 0: no candidates; no_references; detector 0.79; ocr saw `martini` 0.98; pod black (yellow 0.000, aspect 1.8); lever: no references yet, add some
- `203009` box 0: no candidates; no_references; detector 0.89; ocr saw `martini` 0.97, `dacing` 0.43; pod black (yellow 0.000, aspect 1.9); lever: no references yet, add some
- `203011` box 0: no candidates; no_references; detector 0.86; ocr saw `a` 0.38; pod black (yellow 0.000, aspect 2.1); lever: no references yet, add some
- `203013` box 0: no candidates; no_references; detector 0.91; read `5`; pod black (yellow 0.000, aspect 2.2); lever: no references yet, add some
- `203015` box 0: no candidates; no_references; detector 0.90; ocr saw `of` 0.41; pod black (yellow 0.000, aspect 2.4); lever: no references yet, add some
- `203017` box 0: no candidates; no_references; detector 0.92; ocr saw `a` 0.39; pod black (yellow 0.000, aspect 2.5); lever: no references yet, add some
- `203021` box 0: no candidates; no_references; detector 0.92; read `5`; pod black (yellow 0.000, aspect 2.7); lever: no references yet, add some
- `203025` box 0: no candidates; no_references; detector 0.92; ocr saw `i` 0.51, `the` 0.30, `t` 0.28; pod black (yellow 0.000, aspect 1.5); lever: no references yet, add some
- `203027` box 0: no candidates; no_references; detector 0.87; ocr saw `i` 0.38, `i` 0.31, `a` 0.20; pod black (yellow 0.000, aspect 1.6); lever: no references yet, add some
- `203029` box 0: no candidates; no_references; detector 0.93; ocr saw `get` 0.28; pod black (yellow 0.000, aspect 1.6); lever: no references yet, add some
- `203031` box 0: no candidates; no_references; detector 0.93; ocr saw `i` 0.52, `a` 0.32; pod black (yellow 0.001, aspect 1.6); lever: no references yet, add some
- `203033` box 0: no candidates; no_references; detector 0.92; ocr saw no text; pod unclear (yellow 0.001, aspect 1.7); lever: no references yet, add some
- `203035` box 0: no candidates; no_references; detector 0.94; ocr saw no text; pod black (yellow 0.000, aspect 1.8); lever: no references yet, add some
- `203037` box 0: no candidates; no_references; detector 0.29; ocr saw `martinip` 0.97, `ae` 0.27; pod black (yellow 0.000, aspect 1.6); lever: no references yet, add some
- `203039` box 0: no candidates; no_references; detector 0.52; ocr saw `martiniracins` 0.25; pod black (yellow 0.000, aspect 1.5); lever: no references yet, add some
- `203043` box 0: no candidates; no_references; detector 0.92; ocr saw `oy` 0.23; pod black (yellow 0.000, aspect 2.4); lever: no references yet, add some
- `203045` box 0: no candidates; no_references; detector 0.81; ocr saw no text; pod black (yellow 0.000, aspect 2.2); lever: no references yet, add some
- `203047` box 0: no candidates; no_references; detector 0.50; ocr saw no text; pod black (yellow 0.000, aspect 1.6); lever: no references yet, add some
- `203047` box 1: no candidates; no_references; detector 0.46; ocr saw no text; pod black (yellow 0.000, aspect 2.4); lever: no references yet, add some
- `203051` box 0: no candidates; no_references; detector 0.87; ocr saw no text; pod black (yellow 0.000, aspect 2.9); lever: no references yet, add some
- … 1457 more in report.json

## overlapped (93)

- `203037` box 1: no candidates; overlapped; detector 0.90; ocr saw `lans` 0.18; pod black (yellow 0.000, aspect 1.6)
- `203039` box 1: no candidates; overlapped; detector 0.89; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- `203051` box 1: no candidates; overlapped; detector 0.26; ocr saw no text; pod black (yellow 0.000, aspect 1.5)
- `203153` box 1: no candidates; overlapped; detector 0.38; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `203175` box 1: no candidates; overlapped; detector 0.89; ocr saw no text; pod black (yellow 0.000, aspect 1.7)
- `203203` box 1: no candidates; overlapped; detector 0.92; ocr saw no text; pod black (yellow 0.000, aspect 2.6)
- `203691` box 1: no candidates; overlapped; detector 0.30; ocr saw no text; pod unclear (yellow 0.000, aspect 0.5)
- `203757` box 1: no candidates; overlapped; detector 0.82; ocr saw no text; pod black (yellow 0.000, aspect 2.6)
- `203783` box 1: no candidates; overlapped; detector 0.28; ocr saw no text; pod black (yellow 0.000, aspect 2.3)
- `203895` box 1: no candidates; overlapped; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `203937` box 1: no candidates; overlapped; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 1.7)
- `203939` box 1: no candidates; overlapped; detector 0.74; ocr saw `castral` 0.63; pod black (yellow 0.000, aspect 1.9)
- `203939` box 2: no candidates; overlapped; detector 0.21; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2)
- `203963` box 1: no candidates; overlapped; detector 0.92; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `204211` box 1: no candidates; overlapped; detector 0.56; ocr saw `upers` 0.56; pod unclear (yellow 0.000, aspect 0.8)
- `204359` box 1: no candidates; overlapped; detector 0.80; ocr saw no text; pod unclear (yellow 0.000, aspect 0.5)
- `204429` box 1: no candidates; overlapped; detector 0.24; read `9`; pod unclear (yellow 0.000, aspect 0.6)
- `204431` box 1: no candidates; overlapped; detector 0.20; ocr saw no text; pod unclear (yellow 0.000, aspect 0.5)
- `204475` box 1: no candidates; overlapped; detector 0.58; ocr saw `lomba` 0.99; pod unclear (yellow 0.000, aspect 1.2)
- `204491` box 1: no candidates; overlapped; detector 0.84; ocr saw no text; pod black (yellow 0.000, aspect 1.7)
- … 73 more in report.json

## no-vehicle (119)

- `203041` burst 2: no vehicle at 0.2: strongest class 13 0.30 (1.00x1.00 of frame), strongest vehicle car 0.14 (0.47x0.33 of frame)
- `203049` burst 3: no vehicle at 0.2: strongest class 28 0.17 (0.34x0.26 of frame), strongest vehicle car 0.03 (0.10x0.05 of frame)
- `203075` burst 7: no vehicle at 0.2: strongest person 0.91 (0.18x0.42 of frame), strongest vehicle motorcycle 0.02 (0.04x0.07 of frame)
- `203077` burst 7: no vehicle at 0.2: strongest person 0.92 (0.18x0.43 of frame), strongest vehicle truck 0.01 (0.14x0.76 of frame)
- `203079` burst 8: no vehicle at 0.2: strongest person 0.91 (0.18x0.44 of frame), strongest vehicle motorcycle 0.02 (0.03x0.06 of frame)
- `203081` burst 8: no vehicle at 0.2: strongest person 0.90 (0.18x0.44 of frame), strongest vehicle motorcycle 0.01 (0.04x0.11 of frame)
- `203083` burst 9: no vehicle at 0.2: strongest person 0.89 (0.09x0.29 of frame), strongest vehicle car 0.53 (0.07x0.06 of frame)
- `203085` burst 9: no vehicle at 0.2: strongest person 0.89 (0.09x0.29 of frame), strongest vehicle car 0.68 (0.07x0.06 of frame)
- `203087` burst 9: no vehicle at 0.2: strongest person 0.88 (0.09x0.28 of frame), strongest vehicle car 0.47 (0.07x0.06 of frame)
- `203089` burst 9: no vehicle at 0.2: strongest person 0.88 (0.09x0.28 of frame), strongest vehicle car 0.59 (0.07x0.06 of frame)
- `203091` burst 10: no vehicle at 0.2: strongest person 0.88 (0.10x0.28 of frame), strongest vehicle car 0.63 (0.07x0.06 of frame)
- `203093` burst 10: no vehicle at 0.2: strongest person 0.88 (0.10x0.29 of frame), strongest vehicle car 0.64 (0.07x0.06 of frame)
- `203139` burst 17: no vehicle at 0.2: strongest class 13 0.53 (0.99x0.29 of frame), strongest vehicle motorcycle 0.01 (0.07x0.05 of frame)
- `203145` burst 17: no vehicle at 0.2: strongest class 13 0.41 (1.00x0.41 of frame), strongest vehicle motorcycle 0.06 (0.09x0.07 of frame)
- `203155` burst 18: no vehicle at 0.2: strongest train 0.35 (1.01x0.86 of frame), strongest vehicle motorcycle 0.19 (0.23x0.33 of frame)
- `203177` burst 21: no vehicle at 0.2: strongest person 0.16 (0.79x1.02 of frame), strongest vehicle car 0.02 (0.45x0.99 of frame)
- `203221` burst 25: no vehicle at 0.2: strongest class 13 0.58 (1.00x0.51 of frame), strongest vehicle car 0.17 (0.18x0.11 of frame)
- `203223` burst 26: no vehicle at 0.2: strongest car 0.88 (0.07x0.07 of frame), strongest vehicle car 0.88 (0.07x0.07 of frame)
- `203225` burst 26: no vehicle at 0.2: strongest car 0.84 (0.07x0.07 of frame), strongest vehicle car 0.84 (0.07x0.07 of frame)
- `203227` burst 26: no vehicle at 0.2: strongest car 0.72 (0.07x0.07 of frame), strongest vehicle car 0.72 (0.07x0.07 of frame)
- … 99 more in report.json
