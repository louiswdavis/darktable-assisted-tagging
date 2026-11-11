# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

183 vehicles/images, identified rate 10%

- identified: 19 (10%)
- team-obvious: 0 (0%)
- weak-match: 132 (72%)
- no-references: 0 (0%)
- number-unmatched: 1 (1%)
- conflict: 0 (0%)
- overlapped: 5 (3%)
- already-tagged: 0 (0%)
- no-vehicle: 26 (14%)
- median weak-match: top-1 0.550, margin 0.039

## detector score

- 0.00-0.30: 11 boxes, 0 identified
- 0.30-0.40: 4 boxes, 0 identified
- 0.40-0.50: 5 boxes, 0 identified
- 0.50-0.70: 7 boxes, 0 identified
- 0.70-1.00: 130 boxes, 19 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one tag prefix only; add under `rules.sponsor_keywords` after checking:
- `lucas` → `Sports|Hill Climb|Rallye Prescott|35`: 2 identified, would hint 0 unidentified

## bursts (40 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×22, 1s ×16, 2s ×2
frames per burst: 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 9, 9, 10

closest to the next burst (possible split):
- burst 1: 5 frames, next burst starts 2s later
- burst 6: 3 frames, next burst starts 3s later
- burst 16: 10 frames, next burst starts 3s later
- burst 29: 5 frames, next burst starts 3s later
- burst 39: 4 frames, next burst starts 3s later
- burst 3: 4 frames, next burst starts 4s later
- burst 8: 6 frames, next burst starts 4s later
- burst 22: 4 frames, next burst starts 4s later
- burst 24: 2 frames, next burst starts 4s later
- burst 14: 5 frames, next burst starts 5s later
- burst 20: 6 frames, next burst starts 5s later
- burst 27: 6 frames, next burst starts 5s later
- burst 36: 4 frames, next burst starts 7s later
- burst 37: 3 frames, next burst starts 8s later
- burst 34: 4 frames, next burst starts 15s later
- burst 21: 3 frames, next burst starts 18s later
- burst 38: 3 frames, next burst starts 21s later
- burst 2: 3 frames, next burst starts 24s later
- burst 4: 3 frames, next burst starts 24s later
- burst 31: 6 frames, next burst starts 25s later

largest within-burst gap (possible merge):
- burst 1: 5 frames over 2s, largest gap 2s, 4 with vehicles, 1 without
- burst 31: 6 frames over 2s, largest gap 2s, 6 with vehicles, 0 without
- burst 8: 6 frames over 1s, largest gap 1s, 5 with vehicles, 1 without
- burst 9: 3 frames over 1s, largest gap 1s, 1 with vehicles, 2 without
- burst 12: 9 frames over 2s, largest gap 1s, 4 with vehicles, 5 without
- burst 14: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 15: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 16: 10 frames over 1s, largest gap 1s, 5 with vehicles, 5 without
- burst 17: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 19: 6 frames over 2s, largest gap 1s, 5 with vehicles, 1 without
- burst 20: 6 frames over 1s, largest gap 1s, 2 with vehicles, 4 without
- burst 22: 4 frames over 1s, largest gap 1s, 1 with vehicles, 3 without
- burst 23: 9 frames over 2s, largest gap 1s, 9 with vehicles, 0 without
- burst 25: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 26: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 30: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 32: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 38: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 2: 3 frames over 0s, largest gap 0s, 3 with vehicles, 0 without
- burst 3: 4 frames over 0s, largest gap 0s, 4 with vehicles, 0 without

## weak-match (132)

- `205245` box 1: `22` 0.260, `74` 0.257, `97` 0.228; below_min_sim, short by 0.340; detector 0.91; ocr saw `group` 0.99, `burminghan` 0.45, `patrickymotors` 0.44; pod unclear (yellow 0.000, aspect 0.9); lever: weak match, add references from this angle
- `205493` box 1: `74` 0.284, `39` 0.246, `49` 0.222; below_min_sim, short by 0.316; detector 0.32; ocr saw no text; pod black (yellow 0.000, aspect 2.6); lever: weak match, add references from this angle
- `205243` box 1: `74` 0.287, `47` 0.277, `97` 0.262; below_min_sim, short by 0.313; detector 0.92; ocr saw `group` 0.99, `birmingham` 0.99, `bournemouth` 0.98; pod unclear (yellow 0.000, aspect 1.1); lever: weak match, add references from this angle
- `205247` box 1: `74` 0.298, `97` 0.239, `47` 0.209; below_min_sim, short by 0.302; detector 0.92; ocr saw `motors` 0.99, `group` 0.86; pod unclear (yellow 0.000, aspect 0.6); lever: weak match, add references from this angle
- `205231` box 0: `74` 0.331, `39` 0.270, `81` 0.245; below_min_sim, short by 0.269; detector 0.64; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7); lever: weak match, add references from this angle
- `205435` box 0: `39` 0.332, `42` 0.329, `35` 0.314; below_min_sim, short by 0.268; detector 0.80; ocr saw no text; pod unclear (yellow 0.001, aspect 1.1); lever: weak match, add references from this angle
- `205335` box 0: `74` 0.342, `39` 0.279, `47` 0.219; below_min_sim, short by 0.258; detector 0.23; ocr saw no text; pod black (yellow 0.000, aspect 11.9); lever: weak match, add references from this angle
- `205361` box 0: `50` 0.364, `55` 0.348, `76` 0.341; below_min_sim, short by 0.236; detector 0.81; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2); lever: weak match, add references from this angle
- `205363` box 0: `85` 0.372, `50` 0.349, `76` 0.342; below_min_sim, short by 0.228; detector 0.88; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2); lever: weak match, add references from this angle
- `205359` box 0: `85` 0.372, `76` 0.368, `50` 0.363; below_min_sim, short by 0.228; detector 0.89; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2); lever: weak match, add references from this angle
- `205491` box 1: `74` 0.373, `39` 0.264, `35` 0.249; below_min_sim, short by 0.227; detector 0.73; ocr saw no text; pod black (yellow 0.000, aspect 1.4); lever: weak match, add references from this angle
- `205233` box 0: `74` 0.378, `35` 0.315, `47` 0.273; below_min_sim, short by 0.222; detector 0.49; ocr saw no text; pod unclear (yellow 0.000, aspect 0.9); lever: weak match, add references from this angle
- `205245` box 0: `74` 0.383, `83` 0.319, `76` 0.295; below_min_sim, short by 0.217; detector 0.47; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); lever: weak match, add references from this angle
- `205247` box 0: `74` 0.384, `83` 0.318, `76` 0.294; below_min_sim, short by 0.216; detector 0.37; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); lever: weak match, add references from this angle
- `205243` box 0: `74` 0.395, `83` 0.326, `76` 0.302; below_min_sim, short by 0.205; detector 0.49; ocr saw no text; pod black (yellow 0.000, aspect 1.4); lever: weak match, add references from this angle
- `205395` box 0: `83` 0.409, `42` 0.400, `41` 0.376; below_min_sim, short by 0.191; detector 0.54; ocr saw no text; pod black (yellow 0.000, aspect 2.6); lever: weak match, add references from this angle
- `205357` box 0: `50` 0.421, `76` 0.387, `85` 0.374; below_min_sim, short by 0.179; detector 0.88; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); lever: weak match, add references from this angle
- `205333` box 0: `81` 0.425, `76` 0.390, `55` 0.369; below_min_sim, short by 0.175; detector 0.81; ocr saw `you` 0.44; pod black (yellow 0.000, aspect 1.7); lever: weak match, add references from this angle
- `205257` box 2: `74` 0.444, `81` 0.265, `39` 0.255; below_min_sim, short by 0.156; detector 0.24; ocr saw no text; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `205299` box 1: `47` 0.445, `49` 0.425, `35` 0.414; below_min_sim, short by 0.155; detector 0.41; ocr saw no text; pod black (yellow 0.000, aspect 4.7); lever: weak match, add references from this angle
- … 112 more in report.json

## number-unmatched (1)

- `205491` box 0: `67` 0.642, `66` 0.642, `26` 0.490; margin_too_small, short by 0.099; detector 0.93; read `768`; pod black (yellow 0.000, aspect 3.0); lever: no entry has number 768

## overlapped (5)

- `205491` box 2: `74` 0.423, `83` 0.359, `55` 0.322; overlapped; detector 0.23; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2)
- `205493` box 2: `74` 0.456, `55` 0.332, `83` 0.326; overlapped; detector 0.38; ocr saw no text; pod black (yellow 0.000, aspect 2.6)
- `205243` box 2: `74` 0.480, `39` 0.323, `35` 0.314; overlapped; detector 0.75; ocr saw no text; pod unclear (yellow 0.000, aspect 0.3)
- `205245` box 2: `74` 0.484, `35` 0.350, `39` 0.335; overlapped; detector 0.77; ocr saw no text; pod unclear (yellow 0.000, aspect 0.3)
- `205247` box 2: `74` 0.504, `35` 0.345, `39` 0.311; overlapped; detector 0.67; ocr saw no text; pod unclear (yellow 0.000, aspect 0.3)

## no-vehicle (26)

- `205227` burst 1: no vehicle at 0.2: strongest class 13 0.16 (0.84x0.98 of frame), strongest vehicle car 0.04 (0.86x0.99 of frame)
- `205265` burst 8: no vehicle at 0.2: strongest class 13 0.64 (0.99x0.34 of frame), strongest vehicle car 0.01 (0.08x0.03 of frame)
- `205277` burst 9: no vehicle at 0.2: strongest car 0.92 (0.09x0.05 of frame), strongest vehicle car 0.92 (0.09x0.05 of frame)
- `205279` burst 9: no vehicle at 0.2: strongest car 0.89 (0.09x0.05 of frame), strongest vehicle car 0.89 (0.09x0.05 of frame)
- `205293` burst 10: no vehicle at 0.2: strongest car 0.67 (0.03x0.17 of frame), strongest vehicle car 0.67 (0.03x0.17 of frame)
- `205295` burst 11: no vehicle at 0.2: strongest car 0.90 (0.06x0.06 of frame), strongest vehicle car 0.90 (0.06x0.06 of frame)
- `205307` burst 12: no vehicle at 0.2: strongest person 0.60 (0.02x0.06 of frame), strongest vehicle car 0.06 (0.07x0.06 of frame)
- `205309` burst 12: no vehicle at 0.2: strongest person 0.56 (0.02x0.07 of frame), strongest vehicle car 0.03 (0.04x0.04 of frame)
- `205311` burst 12: no vehicle at 0.2: strongest car 0.64 (0.08x0.06 of frame), strongest vehicle car 0.64 (0.08x0.06 of frame)
- `205313` burst 12: no vehicle at 0.2: strongest car 0.88 (0.08x0.06 of frame), strongest vehicle car 0.88 (0.08x0.06 of frame)
- `205315` burst 12: no vehicle at 0.2: strongest car 0.93 (0.07x0.06 of frame), strongest vehicle car 0.93 (0.07x0.06 of frame)
- `205343` burst 16: no vehicle at 0.2: strongest car 0.91 (0.06x0.06 of frame), strongest vehicle car 0.91 (0.06x0.06 of frame)
- `205345` burst 16: no vehicle at 0.2: strongest car 0.88 (0.05x0.06 of frame), strongest vehicle car 0.88 (0.05x0.06 of frame)
- `205347` burst 16: no vehicle at 0.2: strongest car 0.88 (0.05x0.07 of frame), strongest vehicle car 0.88 (0.05x0.07 of frame)
- `205349` burst 16: no vehicle at 0.2: strongest car 0.88 (0.06x0.07 of frame), strongest vehicle car 0.88 (0.06x0.07 of frame)
- `205351` burst 16: no vehicle at 0.2: strongest car 0.91 (0.07x0.07 of frame), strongest vehicle car 0.91 (0.07x0.07 of frame)
- `205385` burst 19: no vehicle at 0.2: strongest car 0.87 (0.06x0.05 of frame), strongest vehicle car 0.87 (0.06x0.05 of frame)
- `205387` burst 20: no vehicle at 0.2: strongest car 0.83 (0.07x0.06 of frame), strongest vehicle car 0.83 (0.07x0.06 of frame)
- `205389` burst 20: no vehicle at 0.2: strongest car 0.83 (0.08x0.06 of frame), strongest vehicle car 0.83 (0.08x0.06 of frame)
- `205391` burst 20: no vehicle at 0.2: strongest person 0.52 (0.02x0.06 of frame), strongest vehicle car 0.17 (0.06x0.05 of frame)
- … 6 more in report.json
