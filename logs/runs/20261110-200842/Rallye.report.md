# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

129 vehicles/images, identified rate 28%

- identified: 36 (28%)
- team-obvious: 0 (0%)
- weak-match: 73 (57%)
- no-references: 0 (0%)
- number-unmatched: 0 (0%)
- conflict: 0 (0%)
- overlapped: 3 (2%)
- already-tagged: 0 (0%)
- no-vehicle: 17 (13%)
- median weak-match: top-1 0.597, margin 0.035

## detector score

- 0.00-0.30: 7 boxes, 0 identified
- 0.30-0.40: 4 boxes, 0 identified
- 0.40-0.50: 2 boxes, 0 identified
- 0.50-0.70: 12 boxes, 3 identified
- 0.70-1.00: 87 boxes, 33 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one tag prefix only; add under `rules.sponsor_keywords` after checking:
- `lombard` → `Sports|Hill Climb|Rallye Prescott|104`: 5 identified, would hint 0 unidentified
- `kitchen` → `Sports|Hill Climb|Rallye Prescott|44`: 2 identified, would hint 0 unidentified

## bursts (25 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×9, 1s ×14, 2s ×2
frames per burst: 2, 2, 2, 2, 2, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 7, 7, 8, 9, 9, 10

closest to the next burst (possible split):
- burst 1: 4 frames, next burst starts 3s later
- burst 8: 6 frames, next burst starts 3s later
- burst 12: 2 frames, next burst starts 3s later
- burst 21: 10 frames, next burst starts 3s later
- burst 19: 9 frames, next burst starts 5s later
- burst 17: 4 frames, next burst starts 8s later
- burst 2: 2 frames, next burst starts 9s later
- burst 9: 4 frames, next burst starts 9s later
- burst 11: 4 frames, next burst starts 11s later
- burst 22: 4 frames, next burst starts 11s later
- burst 6: 3 frames, next burst starts 12s later
- burst 14: 5 frames, next burst starts 12s later
- burst 4: 2 frames, next burst starts 13s later
- burst 3: 2 frames, next burst starts 15s later
- burst 24: 8 frames, next burst starts 15s later
- burst 20: 5 frames, next burst starts 17s later
- burst 16: 4 frames, next burst starts 25s later
- burst 13: 5 frames, next burst starts 29s later
- burst 15: 9 frames, next burst starts 37s later
- burst 10: 5 frames, next burst starts 38s later

largest within-burst gap (possible merge):
- burst 15: 9 frames over 4s, largest gap 2s, 9 with vehicles, 0 without
- burst 18: 6 frames over 2s, largest gap 2s, 3 with vehicles, 3 without
- burst 1: 4 frames over 1s, largest gap 1s, 0 with vehicles, 4 without
- burst 2: 2 frames over 1s, largest gap 1s, 0 with vehicles, 2 without
- burst 6: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 7: 2 frames over 1s, largest gap 1s, 2 with vehicles, 0 without
- burst 8: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 9: 4 frames over 1s, largest gap 1s, 2 with vehicles, 2 without
- burst 10: 5 frames over 2s, largest gap 1s, 4 with vehicles, 1 without
- burst 13: 5 frames over 1s, largest gap 1s, 4 with vehicles, 1 without
- burst 17: 4 frames over 2s, largest gap 1s, 3 with vehicles, 1 without
- burst 19: 9 frames over 4s, largest gap 1s, 9 with vehicles, 0 without
- burst 20: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 21: 10 frames over 1s, largest gap 1s, 10 with vehicles, 0 without
- burst 23: 7 frames over 1s, largest gap 1s, 5 with vehicles, 2 without
- burst 24: 8 frames over 1s, largest gap 1s, 8 with vehicles, 0 without
- burst 3: 2 frames over 0s, largest gap 0s, 2 with vehicles, 0 without
- burst 4: 2 frames over 0s, largest gap 0s, 2 with vehicles, 0 without
- burst 5: 7 frames over 0s, largest gap 0s, 7 with vehicles, 0 without
- burst 11: 4 frames over 0s, largest gap 0s, 4 with vehicles, 0 without

## weak-match (73)

- `203149` box 0: `78` 0.317, `76` 0.292, `83` 0.256; below_min_sim, short by 0.283; detector 0.21; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7); lever: weak match, add references from this angle
- `203261` box 0: `74` 0.360, `35` 0.334, `39` 0.323; below_min_sim, short by 0.240; detector 0.60; ocr saw `x90` 0.68; pod black (yellow 0.000, aspect 2.5); lever: weak match, add references from this angle
- `203143` box 0: `47` 0.380, `62` 0.374, `39` 0.344; below_min_sim, short by 0.221; detector 0.73; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2); lever: weak match, add references from this angle
- `203141` box 0: `26` 0.385, `39` 0.379, `40` 0.378; below_min_sim, short by 0.215; detector 0.84; ocr saw no text; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `203135` box 0: `78` 0.390, `47` 0.329, `80` 0.287; below_min_sim, short by 0.210; detector 0.47; ocr saw no text; pod black (yellow 0.000, aspect 2.2); lever: weak match, add references from this angle
- `203147` box 0: `78` 0.397, `76` 0.321, `83` 0.265; below_min_sim, short by 0.203; detector 0.67; ocr saw no text; pod yellow (yellow 0.004, aspect 1.4); lever: weak match, add references from this angle
- `203261` box 1: `74` 0.397, `83` 0.393, `39` 0.352; below_min_sim, short by 0.203; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 1.0); lever: weak match, add references from this angle
- `203251` box 0: `39` 0.397, `83` 0.321, `85` 0.321; below_min_sim, short by 0.203; detector 0.30; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7); lever: weak match, add references from this angle
- `203175` box 0: `35` 0.409, `85` 0.329, `39` 0.319; below_min_sim, short by 0.191; detector 0.27; ocr saw no text; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- `203151` box 0: `40` 0.417, `60` 0.382, `80` 0.360; below_min_sim, short by 0.183; detector 0.60; ocr saw no text; pod black (yellow 0.000, aspect 1.7); lever: weak match, add references from this angle
- `203129` box 0: `78` 0.425, `47` 0.262, `44` 0.261; below_min_sim, short by 0.175; detector 0.28; ocr saw no text; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `203137` box 0: `78` 0.437, `65` 0.307, `97` 0.302; below_min_sim, short by 0.163; detector 0.61; ocr saw no text; pod black (yellow 0.001, aspect 2.2); lever: weak match, add references from this angle
- `203133` box 0: `78` 0.451, `65` 0.312, `47` 0.282; below_min_sim, short by 0.149; detector 0.57; ocr saw `cun` 0.42; pod black (yellow 0.000, aspect 2.1); lever: weak match, add references from this angle
- `203127` box 0: `78` 0.460, `47` 0.237, `76` 0.235; below_min_sim, short by 0.140; detector 0.19; ocr saw no text; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- `203131` box 0: `78` 0.460, `65` 0.320, `35` 0.297; below_min_sim, short by 0.140; detector 0.42; ocr saw `fhs380` 0.81; pod unclear (yellow 0.001, aspect 1.8); lever: weak match, add references from this angle
- `203249` box 0: `83` 0.461, `56` 0.438, `62` 0.433; below_min_sim, short by 0.139; detector 0.88; ocr saw `rally` 0.95, `the` 0.26; pod unclear (yellow 0.000, aspect 1.4); lever: weak match, add references from this angle
- `203259` box 0: `86` 0.471, `85` 0.408, `39` 0.406; below_min_sim, short by 0.129; detector 0.57; ocr saw `skod` 0.99, `eispogza` 0.60; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `203203` box 0: `85` 0.471, `39` 0.454, `63` 0.414; below_min_sim, short by 0.129; detector 0.36; ocr saw no text; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- `203201` box 0: `80` 0.494, `62` 0.484, `30` 0.406; below_min_sim, short by 0.106; detector 0.93; ocr saw no text; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `203153` box 0: `35` 0.496, `85` 0.452, `39` 0.417; below_min_sim, short by 0.104; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- … 53 more in report.json

## overlapped (3)

- `203153` box 1: `40` 0.451, `22` 0.413, `55` 0.356; overlapped; detector 0.38; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `203203` box 1: `62` 0.573, `82` 0.456, `22` 0.446; overlapped; detector 0.92; ocr saw no text; pod black (yellow 0.000, aspect 2.6)
- `203175` box 1: `85` 0.617, `62` 0.607, `39` 0.596; overlapped; detector 0.89; ocr saw no text; pod black (yellow 0.000, aspect 1.7)

## no-vehicle (17)

- `203083` burst 1: no vehicle at 0.2: strongest person 0.89 (0.09x0.29 of frame), strongest vehicle car 0.53 (0.07x0.06 of frame)
- `203085` burst 1: no vehicle at 0.2: strongest person 0.89 (0.09x0.29 of frame), strongest vehicle car 0.68 (0.07x0.06 of frame)
- `203087` burst 1: no vehicle at 0.2: strongest person 0.88 (0.09x0.28 of frame), strongest vehicle car 0.47 (0.07x0.06 of frame)
- `203089` burst 1: no vehicle at 0.2: strongest person 0.88 (0.09x0.28 of frame), strongest vehicle car 0.59 (0.07x0.06 of frame)
- `203091` burst 2: no vehicle at 0.2: strongest person 0.88 (0.10x0.28 of frame), strongest vehicle car 0.63 (0.07x0.06 of frame)
- `203093` burst 2: no vehicle at 0.2: strongest person 0.88 (0.10x0.29 of frame), strongest vehicle car 0.64 (0.07x0.06 of frame)
- `203139` burst 9: no vehicle at 0.2: strongest class 13 0.53 (0.99x0.29 of frame), strongest vehicle motorcycle 0.01 (0.07x0.05 of frame)
- `203145` burst 9: no vehicle at 0.2: strongest class 13 0.41 (1.00x0.41 of frame), strongest vehicle motorcycle 0.06 (0.09x0.07 of frame)
- `203155` burst 10: no vehicle at 0.2: strongest train 0.35 (1.01x0.86 of frame), strongest vehicle motorcycle 0.19 (0.23x0.33 of frame)
- `203177` burst 13: no vehicle at 0.2: strongest person 0.16 (0.79x1.02 of frame), strongest vehicle car 0.02 (0.45x0.99 of frame)
- `203221` burst 17: no vehicle at 0.2: strongest class 13 0.58 (1.00x0.51 of frame), strongest vehicle car 0.17 (0.18x0.11 of frame)
- `203223` burst 18: no vehicle at 0.2: strongest car 0.88 (0.07x0.07 of frame), strongest vehicle car 0.88 (0.07x0.07 of frame)
- `203225` burst 18: no vehicle at 0.2: strongest car 0.84 (0.07x0.07 of frame), strongest vehicle car 0.84 (0.07x0.07 of frame)
- `203227` burst 18: no vehicle at 0.2: strongest car 0.72 (0.07x0.07 of frame), strongest vehicle car 0.72 (0.07x0.07 of frame)
- `203301` burst 23: no vehicle at 0.2: strongest class 62 0.54 (0.83x1.00 of frame), strongest vehicle car 0.01 (0.98x0.99 of frame)
- `203303` burst 23: no vehicle at 0.2: strongest class 73 0.01 (0.10x0.08 of frame), strongest vehicle car 0.01 (0.22x0.71 of frame)
- `203331` burst 25: no vehicle at 0.2: strongest class 62 0.45 (0.55x0.99 of frame), strongest vehicle car 0.01 (1.07x1.02 of frame)
