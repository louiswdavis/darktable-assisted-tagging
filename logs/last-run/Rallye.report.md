# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

464 vehicles/images, identified rate 16%

- identified: 74 (16%)
- team-obvious: 0 (0%)
- weak-match: 179 (39%)
- no-references: 0 (0%)
- number-unmatched: 1 (0%)
- conflict: 0 (0%)
- overlapped: 202 (44%)
- already-tagged: 0 (0%)
- no-vehicle: 8 (2%)
- median weak-match: top-1 0.468, margin 0.036

## detector score

- 0.00-0.30: 61 boxes, 2 identified
- 0.30-0.40: 47 boxes, 0 identified
- 0.40-0.50: 45 boxes, 1 identified
- 0.50-0.70: 78 boxes, 7 identified
- 0.70-1.00: 225 boxes, 64 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one tag prefix only; add under `rules.sponsor_keywords` after checking:
- `totip` → `Sports|Hill Climb|Rallye Prescott|86`: 2 identified, would hint 2 unidentified
- `martini` → `Sports|Hill Climb|Rallye Prescott|97`: 5 identified, would hint 1 unidentified
- `diesel` → `Sports|Hill Climb|Rallye Prescott|86`: 4 identified, would hint 0 unidentified
- `jeans` → `Sports|Hill Climb|Rallye Prescott|86`: 4 identified, would hint 0 unidentified
- `eans` → `Sports|Hill Climb|Rallye Prescott|86`: 2 identified, would hint 0 unidentified
- `esel` → `Sports|Hill Climb|Rallye Prescott|86`: 2 identified, would hint 0 unidentified

## bursts (79 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×56, 1s ×21, 2s ×2
frames per burst: 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 6, 6, 7, 7

closest to the next burst (possible split):
- burst 40: 2 frames, next burst starts 2s later
- burst 45: 2 frames, next burst starts 2s later
- burst 50: 1 frames, next burst starts 2s later
- burst 58: 1 frames, next burst starts 2s later
- burst 62: 2 frames, next burst starts 2s later
- burst 3: 1 frames, next burst starts 3s later
- burst 19: 2 frames, next burst starts 3s later
- burst 27: 2 frames, next burst starts 3s later
- burst 41: 3 frames, next burst starts 3s later
- burst 48: 3 frames, next burst starts 3s later
- burst 54: 2 frames, next burst starts 3s later
- burst 56: 2 frames, next burst starts 3s later
- burst 68: 2 frames, next burst starts 3s later
- burst 69: 2 frames, next burst starts 3s later
- burst 71: 2 frames, next burst starts 3s later
- burst 2: 1 frames, next burst starts 4s later
- burst 4: 1 frames, next burst starts 4s later
- burst 28: 2 frames, next burst starts 4s later
- burst 37: 2 frames, next burst starts 4s later
- burst 38: 2 frames, next burst starts 4s later

largest within-burst gap (possible merge):
- burst 32: 4 frames over 2s, largest gap 2s, 3 with vehicles, 1 without
- burst 34: 3 frames over 2s, largest gap 2s, 3 with vehicles, 0 without
- burst 7: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 8: 2 frames over 1s, largest gap 1s, 2 with vehicles, 0 without
- burst 11: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 12: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 16: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 22: 7 frames over 1s, largest gap 1s, 7 with vehicles, 0 without
- burst 23: 7 frames over 1s, largest gap 1s, 7 with vehicles, 0 without
- burst 24: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 25: 6 frames over 2s, largest gap 1s, 6 with vehicles, 0 without
- burst 31: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 37: 2 frames over 1s, largest gap 1s, 2 with vehicles, 0 without
- burst 39: 6 frames over 1s, largest gap 1s, 5 with vehicles, 1 without
- burst 41: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 43: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 46: 4 frames over 2s, largest gap 1s, 4 with vehicles, 0 without
- burst 49: 2 frames over 1s, largest gap 1s, 2 with vehicles, 0 without
- burst 53: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 59: 2 frames over 1s, largest gap 1s, 2 with vehicles, 0 without

## weak-match (179)

- `199855` box 0: `47` 0.283, `39` 0.270, `74` 0.248; below_min_sim, short by 0.317; detector 0.55; ocr saw `lombard` 0.99, `tyrecentre` 0.99, `ran` 0.53; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `199859` box 0: `74` 0.292, `39` 0.287, `47` 0.263; below_min_sim, short by 0.308; detector 0.66; ocr saw `lombard` 0.99, `rac` 0.96, `rahy` 0.85; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `199857` box 0: `47` 0.293, `39` 0.256, `74` 0.240; below_min_sim, short by 0.307; detector 0.55; ocr saw `lombard` 0.99, `i` 0.78, `ylyecentre` 0.53; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `199913` box 0: `97` 0.300, `27` 0.235, `98` 0.225; below_min_sim, short by 0.300; detector 0.91; ocr saw `olvelyracegraph` 0.38, `tas` 0.15; pod yellow (yellow 0.009, aspect 1.2); lever: weak match, add references from this angle
- `199909` box 0: `97` 0.311, `98` 0.255, `27` 0.229; below_min_sim, short by 0.288; detector 0.86; ocr saw `ilivelyracegrap` 0.36, `sie` 0.17; pod yellow (yellow 0.009, aspect 1.2); lever: weak match, add references from this angle
- `199549` box 0: `74` 0.315, `67` 0.300, `97` 0.277; below_min_sim, short by 0.285; detector 0.71; read `67`; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- `199877` box 0: `98` 0.329, `3` 0.313, `83` 0.285; below_min_sim, short by 0.271; detector 0.82; ocr saw `t` 0.17; pod black (yellow 0.000, aspect 1.9); lever: weak match, add references from this angle
- `199873` box 0: `97` 0.340, `63` 0.318, `60` 0.271; below_min_sim, short by 0.260; detector 0.85; read `6`; pod black (yellow 0.000, aspect 2.0); lever: weak match, add references from this angle
- `199875` box 0: `3` 0.340, `83` 0.325, `97` 0.314; below_min_sim, short by 0.260; detector 0.85; ocr saw no text; pod black (yellow 0.000, aspect 1.9); lever: weak match, add references from this angle
- `199631` box 3: `85` 0.348, `74` 0.344, `39` 0.304; below_min_sim, short by 0.252; detector 0.30; ocr saw no text; pod black (yellow 0.000, aspect 1.4); lever: weak match, add references from this angle
- `199761` box 3: `39` 0.348, `74` 0.328, `35` 0.268; below_min_sim, short by 0.252; detector 0.75; ocr saw no text; pod unclear (yellow 0.000, aspect 1.0); lever: weak match, add references from this angle
- `199547` box 0: `74` 0.349, `67` 0.310, `97` 0.303; below_min_sim, short by 0.251; detector 0.76; read `67`; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- `199915` box 1: `39` 0.351, `74` 0.294, `76` 0.281; below_min_sim, short by 0.249; detector 0.93; ocr saw `tow` 0.98, `7r` 0.50, `xt` 0.38; pod yellow (yellow 0.014, aspect 1.2); lever: weak match, add references from this angle
- `199529` box 2: `67` 0.353, `74` 0.353, `85` 0.294; below_min_sim, short by 0.247; detector 0.33; ocr saw no text; pod black (yellow 0.000, aspect 2.7); lever: weak match, add references from this angle
- `199649` box 3: `74` 0.354, `39` 0.325, `81` 0.213; below_min_sim, short by 0.246; detector 0.31; ocr saw no text; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `199781` box 1: `74` 0.355, `85` 0.339, `49` 0.272; below_min_sim, short by 0.245; detector 0.86; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1); lever: weak match, add references from this angle
- `199873` box 2: `46` 0.356, `56` 0.333, `39` 0.317; below_min_sim, short by 0.243; detector 0.48; ocr saw no text; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `199565` box 0: `74` 0.363, `35` 0.279, `39` 0.254; below_min_sim, short by 0.237; detector 0.92; ocr saw `creralny` 0.12; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `199891` box 1: `98` 0.365, `74` 0.338, `86` 0.329; below_min_sim, short by 0.235; detector 0.49; read `213`; pod yellow (yellow 0.049, aspect 1.2); lever: weak match, add references from this angle
- `199783` box 1: `74` 0.367, `85` 0.338, `97` 0.262; below_min_sim, short by 0.233; detector 0.70; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2); lever: weak match, add references from this angle
- … 159 more in report.json

## number-unmatched (1)

- `199683` box 1: `39` 0.405, `67` 0.301, `83` 0.292; below_min_sim, short by 0.195; detector 0.47; read `175`; pod black (yellow 0.000, aspect 4.0); lever: no entry has number 175

## overlapped (202)

- `199683` box 2: `62` 0.320, `39` 0.311, `83` 0.309; overlapped; detector 0.69; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- `199685` box 2: `62` 0.336, `39` 0.321, `83` 0.319; overlapped; detector 0.70; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- `199569` box 1: `22` 0.343, `74` 0.336, `78` 0.332; overlapped; detector 0.48; ocr saw no text; pod black (yellow 0.000, aspect 4.7)
- `199525` box 2: `85` 0.345, `39` 0.335, `74` 0.329; overlapped; detector 0.54; ocr saw no text; pod black (yellow 0.000, aspect 2.3)
- `199567` box 1: `39` 0.353, `74` 0.340, `85` 0.287; overlapped; detector 0.42; ocr saw no text; pod black (yellow 0.000, aspect 4.9)
- `199531` box 3: `46` 0.357, `81` 0.352, `87` 0.319; overlapped; detector 0.83; ocr saw no text; pod black (yellow 0.000, aspect 1.7)
- `199875` box 1: `46` 0.359, `87` 0.315, `98` 0.309; overlapped; detector 0.52; read `1`; pod black (yellow 0.000, aspect 2.4)
- `199551` box 1: `74` 0.361, `67` 0.358, `83` 0.351; overlapped; detector 0.41; ocr saw no text; pod black (yellow 0.000, aspect 1.8)
- `199647` box 1: `47` 0.361, `39` 0.355, `22` 0.355; overlapped; detector 0.32; ocr saw no text; pod black (yellow 0.000, aspect 2.2)
- `199855` box 1: `42` 0.362, `22` 0.338, `74` 0.330; overlapped; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `199653` box 1: `67` 0.362, `39` 0.329, `83` 0.319; overlapped; detector 0.23; ocr saw no text; pod black (yellow 0.000, aspect 1.5)
- `199887` box 2: `74` 0.365, `67` 0.357, `83` 0.345; overlapped; detector 0.22; ocr saw no text; pod black (yellow 0.000, aspect 1.5)
- `199877` box 1: `46` 0.368, `87` 0.368, `60` 0.304; overlapped; detector 0.61; ocr saw no text; pod black (yellow 0.000, aspect 2.3)
- `199605` box 2: `74` 0.369, `39` 0.343, `67` 0.342; overlapped; detector 0.20; ocr saw `isuzt` 0.53; pod black (yellow 0.000, aspect 1.4)
- `199927` box 2: `40` 0.373, `58` 0.354, `98` 0.342; overlapped; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 0.2)
- `199731` box 1: `55` 0.378, `42` 0.375, `30` 0.332; overlapped; detector 0.31; ocr saw no text; pod black (yellow 0.000, aspect 2.8)
- `199647` box 3: `22` 0.379, `39` 0.362, `47` 0.351; overlapped; detector 0.37; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8)
- `199725` box 3: `39` 0.379, `74` 0.376, `67` 0.370; overlapped; detector 0.62; ocr saw no text; pod black (yellow 0.000, aspect 2.9)
- `199781` box 3: `39` 0.380, `74` 0.370, `35` 0.370; overlapped; detector 0.45; ocr saw no text; pod black (yellow 0.000, aspect 3.5)
- `199861` box 1: `74` 0.381, `83` 0.362, `22` 0.339; overlapped; detector 0.43; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- … 182 more in report.json

## no-vehicle (8)

- `199707` burst 32: no vehicle at 0.2: strongest person 0.94 (0.37x0.98 of frame), strongest vehicle truck 0.17 (0.74x0.98 of frame)
- `199735` burst 38: no vehicle at 0.2: strongest bus 0.51 (0.97x1.00 of frame), strongest vehicle truck 0.07 (0.99x1.01 of frame)
- `199737` burst 38: no vehicle at 0.2: strongest train 0.34 (1.01x1.00 of frame), strongest vehicle truck 0.06 (1.01x0.98 of frame)
- `199739` burst 39: no vehicle at 0.2: strongest person 0.73 (0.45x0.98 of frame), strongest vehicle car 0.15 (1.01x0.97 of frame)
- `199851` burst 62: no vehicle at 0.2: strongest train 0.55 (1.00x1.11 of frame), strongest vehicle truck 0.06 (0.94x1.10 of frame)
- `199853` burst 62: no vehicle at 0.2: strongest train 0.52 (1.00x1.08 of frame), strongest vehicle truck 0.11 (0.95x1.07 of frame)
- `199905` burst 75: no vehicle at 0.2: strongest person 0.67 (0.30x0.10 of frame), strongest vehicle car 0.19 (1.00x0.96 of frame)
- `199907` burst 75: no vehicle at 0.2: strongest person 0.61 (0.32x0.10 of frame), strongest vehicle car 0.12 (1.00x0.98 of frame)
