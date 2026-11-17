# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

233 vehicles/images, identified rate 55%

- identified: 127 (55%)
- team-obvious: 0 (0%)
- weak-match: 72 (31%)
- no-references: 0 (0%)
- number-unmatched: 4 (2%)
- conflict: 0 (0%)
- overlapped: 22 (9%)
- already-tagged: 0 (0%)
- no-vehicle: 8 (3%)
- median weak-match: top-1 0.556, margin 0.040
- colours: Grey 19, Multi 66, Brown 2, Black 37, no colour 22, Blue 41, Red 34, White 3, Green 1

## detector score

- 0.00-0.30: 39 boxes, 3 identified
- 0.30-0.40: 16 boxes, 1 identified
- 0.40-0.50: 8 boxes, 1 identified
- 0.50-0.70: 5 boxes, 3 identified
- 0.70-1.00: 157 boxes, 119 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one team tag only; add under `rules.sponsor_keywords` after checking:
- `skoda` → `Motorsport|Number|39`: 2 identified, would hint 2 unidentified
- `lombard` → `Motorsport|Number|104`: 5 identified, would hint 0 unidentified
- `optimal` → `Motorsport|Number|31`: 4 identified, would hint 0 unidentified
- `graphic` → `Motorsport|Number|31`: 3 identified, would hint 0 unidentified
- `kitchen` → `Motorsport|Number|102`: 3 identified, would hint 0 unidentified
- `moss` → `Motorsport|Number|103`: 2 identified, would hint 0 unidentified
- `motorsport` → `Motorsport|Number|104`: 2 identified, would hint 0 unidentified
- `tucker` → `Motorsport|Number|103`: 2 identified, would hint 0 unidentified
- `turbos` → `Motorsport|Number|39`: 2 identified, would hint 0 unidentified

## bursts (32 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×14, 1s ×17, 2s ×1
frames per burst: 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 7, 7, 8, 8, 9, 10, 10, 15

closest to the next burst (possible split):
- burst 14: 6 frames, next burst starts 2s later
- burst 28: 10 frames, next burst starts 2s later
- burst 5: 10 frames, next burst starts 3s later
- burst 11: 6 frames, next burst starts 3s later
- burst 22: 4 frames, next burst starts 3s later
- burst 16: 8 frames, next burst starts 4s later
- burst 18: 4 frames, next burst starts 4s later
- burst 24: 3 frames, next burst starts 4s later
- burst 29: 3 frames, next burst starts 4s later
- burst 31: 3 frames, next burst starts 4s later
- burst 3: 9 frames, next burst starts 5s later
- burst 20: 4 frames, next burst starts 5s later
- burst 25: 2 frames, next burst starts 5s later
- burst 30: 7 frames, next burst starts 6s later
- burst 21: 3 frames, next burst starts 7s later
- burst 1: 4 frames, next burst starts 8s later
- burst 17: 2 frames, next burst starts 8s later
- burst 6: 4 frames, next burst starts 11s later
- burst 10: 15 frames, next burst starts 11s later
- burst 13: 6 frames, next burst starts 12s later

largest within-burst gap (possible merge):
- burst 2: 6 frames over 2s, largest gap 2s, 2 with vehicles, 4 without
- burst 1: 4 frames over 2s, largest gap 1s, 4 with vehicles, 0 without
- burst 3: 9 frames over 4s, largest gap 1s, 9 with vehicles, 0 without
- burst 4: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 5: 10 frames over 1s, largest gap 1s, 10 with vehicles, 0 without
- burst 7: 7 frames over 1s, largest gap 1s, 5 with vehicles, 2 without
- burst 8: 8 frames over 1s, largest gap 1s, 8 with vehicles, 0 without
- burst 10: 15 frames over 2s, largest gap 1s, 15 with vehicles, 0 without
- burst 13: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 14: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 16: 8 frames over 1s, largest gap 1s, 8 with vehicles, 0 without
- burst 19: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 21: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 22: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 23: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 28: 10 frames over 4s, largest gap 1s, 8 with vehicles, 2 without
- burst 30: 7 frames over 1s, largest gap 1s, 7 with vehicles, 0 without
- burst 31: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 6: 4 frames over 0s, largest gap 0s, 4 with vehicles, 0 without
- burst 9: 6 frames over 0s, largest gap 0s, 6 with vehicles, 0 without

## weak-match (72)

- `203257` box 1: `74` 0.323, `115` 0.316, `11` 0.312; below_min_sim, short by 0.277; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 1.6); colour Black (Bk0.99); lever: weak match, add references from this angle
- `203251` box 0: `74` 0.351, `115` 0.313, `39` 0.293; below_min_sim, short by 0.249; detector 0.34; ocr saw no text; pod black (yellow 0.000, aspect 1.5); colour Multi (Bk0.60 G0.37); lever: weak match, add references from this angle
- `203261` box 3: `115` 0.389, `74` 0.378, `11` 0.318; below_min_sim, short by 0.211; detector 0.41; ocr saw no text; pod black (yellow 0.000, aspect 2.5); colour Black (Bk1.00); lever: weak match, add references from this angle
- `203261` box 1: `74` 0.395, `113` 0.369, `115` 0.360; below_min_sim, short by 0.205; detector 0.50; ocr saw `t` 0.40 h0.05; pod unclear (yellow 0.000, aspect 0.8); colour Black (Bk0.95); lever: weak match, add references from this angle
- `203259` box 1: `115` 0.399, `11` 0.376, `108` 0.349; below_min_sim, short by 0.201; detector 0.44; ocr saw no text; pod black (yellow 0.000, aspect 2.4); colour Black (Bk0.99); lever: weak match, add references from this angle
- `203249` box 0: `3` 0.425, `5` 0.409, `8` 0.384; below_min_sim, short by 0.175; detector 0.95; read `1`; pod unclear (yellow 0.000, aspect 1.4); colour Black (Bk0.70 G0.17 G0.13); lever: weak match, add references from this angle
- `203353` box 2: `116` 0.426, `112` 0.414, `113` 0.405; below_min_sim, short by 0.174; detector 0.23; ocr saw no text; pod black (yellow 0.000, aspect 2.9); colour Grey (G0.57 W0.27 R0.12); lever: weak match, add references from this angle
- `203403` box 1: `74` 0.434, `113` 0.378, `115` 0.354; below_min_sim, short by 0.166; detector 0.23; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7); colour Multi (Bk0.62 B0.24 G0.08 O0.06); lever: weak match, add references from this angle
- `203371` box 1: `98` 0.446, `39` 0.371, `74` 0.339; below_min_sim, short by 0.154; detector 0.47; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8); colour Red (R0.53 Bk0.19 B0.11 G0.09 Bl0.07); lever: weak match, add references from this angle
- `203467` box 1: `98` 0.446, `39` 0.392, `76` 0.329; below_min_sim, short by 0.154; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 0.9); colour Black (Bk0.77 R0.18); lever: weak match, add references from this angle
- `203291` box 1: `113` 0.449, `112` 0.438, `103` 0.413; below_min_sim, short by 0.151; detector 0.34; ocr saw no text; pod unclear (yellow 0.000, aspect 0.6); colour Grey (G1.00); lever: weak match, add references from this angle
- `203471` box 1: `98` 0.451, `39` 0.366, `115` 0.334; below_min_sim, short by 0.149; detector 0.32; ocr saw no text; pod unclear (yellow 0.000, aspect 0.9); colour Black (Bk0.78 R0.17); lever: weak match, add references from this angle
- `203351` box 1: `35` 0.458, `116` 0.456, `113` 0.433; below_min_sim, short by 0.142; detector 0.27; ocr saw no text; pod black (yellow 0.000, aspect 3.8); colour Multi (G0.38 W0.34 R0.16 Bl0.08); lever: weak match, add references from this angle
- `203473` box 1: `98` 0.468, `39` 0.371, `115` 0.353; below_min_sim, short by 0.132; detector 0.25; ocr saw no text; pod unclear (yellow 0.000, aspect 0.9); colour Black (Bk0.78 R0.17); lever: weak match, add references from this angle
- `203365` box 1: `98` 0.469, `39` 0.380, `74` 0.336; below_min_sim, short by 0.131; detector 0.35; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8); colour Red (R0.56 Bk0.19 B0.11 G0.09); lever: weak match, add references from this angle
- `203235` box 1: `98` 0.470, `74` 0.427, `115` 0.361; below_min_sim, short by 0.130; detector 0.23; read `2`; pod black (yellow 0.000, aspect 1.7); colour Multi (Bk0.44 G0.32 B0.15 R0.06); lever: weak match, add references from this angle
- `203239` box 2: `98` 0.472, `74` 0.408, `115` 0.404; below_min_sim, short by 0.128; detector 0.35; read `5`; pod black (yellow 0.000, aspect 1.6); colour Black (Bk0.68 G0.18 B0.09); lever: weak match, add references from this angle
- `203373` box 1: `98` 0.472, `39` 0.373, `76` 0.337; below_min_sim, short by 0.128; detector 0.34; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8); colour Red (R0.54 Bk0.20 B0.12 G0.09); lever: weak match, add references from this angle
- `203381` box 0: `26` 0.476, `98` 0.411, `121` 0.386; below_min_sim, short by 0.124; detector 0.49; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1); colour Black (Bk0.63 G0.19 Bl0.17); lever: weak match, add references from this angle
- `203355` box 2: `35` 0.478, `116` 0.468, `113` 0.453; below_min_sim, short by 0.122; detector 0.22; ocr saw no text; pod black (yellow 0.000, aspect 4.0); colour Multi (G0.40 W0.32 R0.15 Bl0.09); lever: weak match, add references from this angle
- … 52 more in report.json

## number-unmatched (4)

- `203261` box 0: `62` 0.391, `26` 0.322, `75` 0.305; below_min_sim, short by 0.209; detector 0.72; read `06`; start list 06>64 -5.87, 62 -6.66 no list read; pod black (yellow 0.000, aspect 2.4); colour Black (Bk0.80 G0.17); lever: no entry has number 06
- `203241` box 2: `98` 0.442, `74` 0.382, `115` 0.376; below_min_sim, short by 0.158; detector 0.24; read `2`; start list 2>2 0.00, 26 -0.10 close call; pod black (yellow 0.000, aspect 1.7); colour Black (Bk0.74 G0.17 B0.05); lever: no entry has number 2
- `203247` box 0: `5` 0.478, `39` 0.464, `80` 0.443; below_min_sim, short by 0.122; detector 0.95; read `90`; start list 90>90 0.00, 790 -2.72; pod unclear (yellow 0.000, aspect 1.4); colour Multi (Bk0.41 G0.40 G0.11); lever: no entry has number 90
- `203337` box 0: `103` 0.753, `104` 0.680, `98` 0.668; margin_too_small, short by 0.026; detector 0.94; read `2`; start list 2>2 0.00, 1 -2.09 close call; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.57 G0.20 Bk0.11 W0.07); lever: no entry has number 2

## overlapped (22)

- `203253` box 1: `11` 0.337, `74` 0.325, `115` 0.324; overlapped; detector 0.22; ocr saw no text; pod black (yellow 0.000, aspect 3.2)
- `203495` box 1: `26` 0.350, `47` 0.319, `97` 0.306; overlapped; detector 0.20; ocr saw `Abbey Carpet` 0.86 h0.12, `& Flouor` 0.42 h0.10; pod black (yellow 0.000, aspect 2.9)
- `203489` box 1: `83` 0.367, `103` 0.363, `113` 0.354; overlapped; detector 0.22; ocr saw no text; pod black (yellow 0.000, aspect 1.7)
- `203259` box 2: `62` 0.390, `74` 0.386, `113` 0.383; overlapped; detector 0.26; ocr saw no text; pod black (yellow 0.000, aspect 1.8)
- `203319` box 1: `26` 0.412, `39` 0.370, `62` 0.351; overlapped; detector 0.26; ocr saw `oha` 0.30 h0.08; pod black (yellow 0.000, aspect 2.2)
- `203261` box 2: `83` 0.419, `85` 0.406, `43` 0.369; overlapped; detector 0.38; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8)
- `203251` box 2: `62` 0.435, `97` 0.373, `3` 0.352; overlapped; detector 0.34; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8)
- `203299` box 1: `103` 0.438, `115` 0.379, `112` 0.378; overlapped; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7)
- `203281` box 1: `64` 0.475, `103` 0.433, `98` 0.370; overlapped; detector 0.22; read `28`; pod black (yellow 0.000, aspect 1.5)
- `203507` box 1: `109` 0.505, `94` 0.457, `86` 0.449; overlapped; detector 0.49; ocr saw no text; pod unclear (yellow 0.000, aspect 0.9)
- `203431` box 1: `27` 0.524, `54` 0.517, `75` 0.487; overlapped; detector 0.21; ocr saw no text; pod yellow (yellow 0.001, aspect 1.6)
- `203497` box 1: `109` 0.527, `121` 0.468, `47` 0.430; overlapped; detector 0.34; ocr saw `Abbey Carpet` 0.93 h0.08, `& Floor` 0.63 h0.07; pod black (yellow 0.000, aspect 2.1)
- `203383` box 1: `62` 0.539, `3` 0.536, `46` 0.517; overlapped; detector 0.28; ocr saw no text; pod unclear (yellow 0.000, aspect 1.4)
- `203355` box 1: `98` 0.545, `86` 0.511, `109` 0.481; overlapped; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 2.4)
- `203429` box 1: `31` 0.547, `40` 0.516, `27` 0.505; overlapped; detector 0.23; ocr saw `STA` 0.89 h0.07; pod black (yellow 0.000, aspect 1.6)
- `203381` box 1: `26` 0.548, `62` 0.544, `108` 0.459; overlapped; detector 0.81; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1)
- `203361` box 1: `98` 0.552, `94` 0.435, `103` 0.420; overlapped; detector 0.30; ocr saw `UP` 0.46 h0.07, `E5S` 0.25 h0.06, `nat` 0.24 h0.06; pod unclear (yellow 0.001, aspect 1.3)
- `203297` box 1: `98` 0.571, `39` 0.528, `103` 0.525; overlapped; detector 0.24; ocr saw no text; pod black (yellow 0.000, aspect 2.6)
- `203251` box 1: `3` 0.639, `62` 0.491, `103` 0.479; overlapped; detector 0.61; ocr saw no text; pod unclear (yellow 0.000, aspect 0.6)
- `203555` box 1: `76` 0.685, `112` 0.620, `44` 0.516; overlapped; detector 0.22; read `506`; pod black (yellow 0.000, aspect 1.4)
- … 2 more in report.json

## no-vehicle (8)

- `203223` burst 2: no vehicle at 0.2: strongest vehicle 0.93 (0.07x0.07 of frame)
- `203225` burst 2: no vehicle at 0.2: strongest vehicle 0.94 (0.07x0.07 of frame)
- `203227` burst 2: no vehicle at 0.2: strongest vehicle 0.93 (0.07x0.07 of frame)
- `203229` burst 2: no vehicle at 0.2: strongest vehicle 0.93 (0.07x0.07 of frame)
- `203301` burst 7: no vehicle at 0.2: strongest vehicle 0.16 (0.99x1.00 of frame)
- `203303` burst 7: no vehicle at 0.2: strongest vehicle 0.06 (0.40x0.96 of frame)
- `203523` burst 28: no vehicle at 0.2: strongest vehicle 0.16 (1.00x0.50 of frame)
- `203525` burst 28: no vehicle at 0.2: strongest vehicle 0.14 (1.00x0.50 of frame)
