# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

6067 vehicles/images, identified rate 28%

- identified: 1725 (28%)
- team-obvious: 0 (0%)
- weak-match: 2420 (40%)
- no-references: 0 (0%)
- number-unmatched: 177 (3%)
- conflict: 0 (0%)
- overlapped: 1568 (26%)
- already-tagged: 30 (0%)
- no-vehicle: 147 (2%)
- median weak-match: top-1 0.555, margin 0.028
- colours: Black 1503, Red 398, Multi 1343, Grey 366, Blue 424, no colour 1571, Green 92, White 57, Brown 78, Orange 19, Yellow 32, Pink 6, Purple 1

## detector score

- 0.00-0.30: 1465 boxes, 55 identified
- 0.30-0.40: 541 boxes, 18 identified
- 0.40-0.50: 265 boxes, 19 identified
- 0.50-0.70: 390 boxes, 71 identified
- 0.70-1.00: 3229 boxes, 1562 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one team tag only; add under `rules.sponsor_keywords` after checking:
- `martini` → `Motorsport|Number|97`: 7 identified, would hint 11 unidentified
- `copper` → `Motorsport|Number|31`: 9 identified, would hint 5 unidentified
- `hella` → `Motorsport|Number|31`: 2 identified, would hint 4 unidentified
- `olsbergs` → `Motorsport|Number|85`: 3 identified, would hint 3 unidentified
- `motorhomes` → `Motorsport|Number|33`: 2 identified, would hint 3 unidentified
- `patrick` → `Motorsport|Number|45`: 2 identified, would hint 2 unidentified
- `horse` → `Motorsport|Number|31`: 8 identified, would hint 1 unidentified
- `advan` → `Motorsport|Number|104`: 2 identified, would hint 1 unidentified
- `llington` → `Motorsport|Number|104`: 2 identified, would hint 1 unidentified
- `maynard` → `Motorsport|Number|22`: 27 identified, would hint 0 unidentified
- `aswmc` → `Motorsport|Number|101`: 12 identified, would hint 0 unidentified
- `cibie` → `Motorsport|Number|44`: 8 identified, would hint 0 unidentified
- `motul` → `Motorsport|Number|44`: 8 identified, would hint 0 unidentified
- `woolworth` → `Motorsport|Number|11`: 8 identified, would hint 0 unidentified
- `mobil` → `Motorsport|Number|62`: 6 identified, would hint 0 unidentified
- `bevan` → `Motorsport|Number|98`: 4 identified, would hint 0 unidentified
- `cobra` → `Motorsport|Number|102`: 4 identified, would hint 0 unidentified
- `ethan` → `Motorsport|Number|104`: 4 identified, would hint 0 unidentified
- `moss` → `Motorsport|Number|103`: 4 identified, would hint 0 unidentified
- `optimal` → `Motorsport|Number|31`: 4 identified, would hint 0 unidentified

## bursts (775 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×426, 1s ×305, 2s ×43, 541s ×1
frames per burst: 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 12, 12, 12, 13, 13, 13, 13, 13, 13, 14, 14, 14, 14, 15, 15, 15, 15, 15, 15, 15, 15, 15, 16, 16, 16, 17, 17, 17, 17, 18, 18, 18, 19, 20, 21, 22, 23, 23, 30, 216

closest to the next burst (possible split):
- burst 385: 216 frames, next burst starts -1191s later
- burst 35: 3 frames, next burst starts 2s later
- burst 50: 9 frames, next burst starts 2s later
- burst 59: 5 frames, next burst starts 2s later
- burst 126: 6 frames, next burst starts 2s later
- burst 140: 10 frames, next burst starts 2s later
- burst 147: 6 frames, next burst starts 2s later
- burst 165: 2 frames, next burst starts 2s later
- burst 192: 5 frames, next burst starts 2s later
- burst 237: 2 frames, next burst starts 2s later
- burst 275: 5 frames, next burst starts 2s later
- burst 279: 4 frames, next burst starts 2s later
- burst 293: 2 frames, next burst starts 2s later
- burst 305: 5 frames, next burst starts 2s later
- burst 367: 5 frames, next burst starts 2s later
- burst 369: 2 frames, next burst starts 2s later
- burst 374: 2 frames, next burst starts 2s later
- burst 377: 2 frames, next burst starts 2s later
- burst 390: 1 frames, next burst starts 2s later
- burst 413: 5 frames, next burst starts 2s later

largest within-burst gap (possible merge):
- burst 385: 216 frames over 1711s, largest gap 541s, 216 with vehicles, 0 without
- burst 1: 3 frames over 3s, largest gap 2s, 3 with vehicles, 0 without
- burst 14: 18 frames over 6s, largest gap 2s, 18 with vehicles, 0 without
- burst 18: 5 frames over 3s, largest gap 2s, 5 with vehicles, 0 without
- burst 26: 6 frames over 2s, largest gap 2s, 6 with vehicles, 0 without
- burst 47: 5 frames over 2s, largest gap 2s, 5 with vehicles, 0 without
- burst 78: 8 frames over 3s, largest gap 2s, 8 with vehicles, 0 without
- burst 90: 9 frames over 2s, largest gap 2s, 9 with vehicles, 0 without
- burst 111: 9 frames over 4s, largest gap 2s, 9 with vehicles, 0 without
- burst 114: 6 frames over 2s, largest gap 2s, 2 with vehicles, 4 without
- burst 146: 6 frames over 2s, largest gap 2s, 5 with vehicles, 1 without
- burst 147: 6 frames over 3s, largest gap 2s, 6 with vehicles, 0 without
- burst 149: 5 frames over 2s, largest gap 2s, 5 with vehicles, 0 without
- burst 156: 5 frames over 3s, largest gap 2s, 5 with vehicles, 0 without
- burst 163: 8 frames over 2s, largest gap 2s, 8 with vehicles, 0 without
- burst 164: 10 frames over 4s, largest gap 2s, 10 with vehicles, 0 without
- burst 196: 4 frames over 2s, largest gap 2s, 4 with vehicles, 0 without
- burst 220: 15 frames over 7s, largest gap 2s, 15 with vehicles, 0 without
- burst 236: 9 frames over 2s, largest gap 2s, 6 with vehicles, 3 without
- burst 238: 6 frames over 2s, largest gap 2s, 6 with vehicles, 0 without

## weak-match (2420)

- `202051` box 1: `74` 0.262, `112` 0.249, `113` 0.245; below_min_sim, short by 0.338; detector 0.33; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7); colour Multi (G0.60 Bl0.27 Bk0.12); lever: weak match, add references from this angle
- `202397` box 0: `74` 0.263, `113` 0.262, `62` 0.251; below_min_sim, short by 0.337; detector 0.85; ocr saw no text; pod black (yellow 0.000, aspect 1.6); colour Green (G0.56 G0.30 Bk0.10); lever: weak match, add references from this angle
- `199493` box 0: `62` 0.276, `113` 0.273, `39` 0.269; below_min_sim, short by 0.324; detector 0.91; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); colour White (W0.87 G0.10); lever: weak match, add references from this angle
- `199523` box 0: `74` 0.277, `113` 0.272, `62` 0.259; below_min_sim, short by 0.323; detector 0.93; ocr saw `FASSI` 0.99 h0.04, `EBC` 0.96 h0.04, `SN Classics and Motorsport` 0.95 h0.03; pod unclear (yellow 0.001, aspect 0.6); colour Red (R0.61 Bk0.24 G0.07); lever: weak match, add references from this angle
- `200979` box 0: `74` 0.282, `115` 0.261, `113` 0.258; below_min_sim, short by 0.318; detector 0.87; ocr saw no text; pod black (yellow 0.000, aspect 2.8); colour Multi (Bk0.67 Bl0.25 G0.08); lever: weak match, add references from this angle
- `200093` box 1: `74` 0.285, `87` 0.274, `112` 0.255; below_min_sim, short by 0.315; detector 0.49; ocr saw no text; pod black (yellow 0.000, aspect 1.4); colour Black (Bk0.85 G0.14); lever: weak match, add references from this angle
- `205491` box 1: `74` 0.288, `112` 0.263, `113` 0.261; below_min_sim, short by 0.312; detector 0.31; ocr saw no text; pod black (yellow 0.000, aspect 3.8); colour Black (Bk0.94 G0.06); lever: weak match, add references from this angle
- `202047` box 1: `112` 0.289, `98` 0.287, `115` 0.281; below_min_sim, short by 0.311; detector 0.38; ocr saw no text; pod unclear (yellow 0.000, aspect 0.4); colour Blue (Bl0.54 G0.31 Bk0.15); lever: weak match, add references from this angle
- `199913` box 0: `74` 0.291, `113` 0.287, `97` 0.287; below_min_sim, short by 0.309; detector 0.90; ocr saw `Alivelyrace Graph` 0.49 h0.03, `LONE` 0.19 h0.06; pod yellow (yellow 0.009, aspect 1.2); colour Multi (G0.42 Bl0.20 R0.17 Y0.14); lever: weak match, add references from this angle
- `198495` box 0: `74` 0.291, `39` 0.270, `109` 0.264; below_min_sim, short by 0.309; detector 0.92; ocr saw `Sponsored By` 0.99 h0.04, `The Wife` 0.98 h0.05, `JAFFA` 0.94 h0.03; pod unclear (yellow 0.000, aspect 1.3); colour Blue (Bl0.53 G0.29 Bk0.14); lever: weak match, add references from this angle
- `201347` box 0: `31` 0.295, `47` 0.259, `27` 0.257; below_min_sim, short by 0.305; detector 0.75; ocr saw no text; pod black (yellow 0.000, aspect 2.7); colour Black (Bk0.99); lever: weak match, add references from this angle
- `199911` box 0: `113` 0.296, `74` 0.295, `112` 0.292; below_min_sim, short by 0.303; detector 0.88; ocr saw `Aliveyrace Graph` 0.72 h0.03, `E` 0.34 h0.07; pod yellow (yellow 0.009, aspect 1.2); colour Multi (G0.43 Bl0.21 R0.17 Y0.14); lever: weak match, add references from this angle
- `199857` box 0: `74` 0.298, `113` 0.272, `112` 0.263; below_min_sim, short by 0.302; detector 0.96; read `4`; pod black (yellow 0.000, aspect 1.7); colour Blue (Bl0.43 G0.39 W0.09 Bk0.06); lever: weak match, add references from this angle
- `201375` box 0: `74` 0.300, `113` 0.259, `3` 0.257; below_min_sim, short by 0.300; detector 0.73; ocr saw no text; pod black (yellow 0.000, aspect 2.4); colour Black (Bk0.79 G0.18); lever: weak match, add references from this angle
- `201331` box 0: `47` 0.301, `31` 0.300, `3` 0.290; below_min_sim, short by 0.299; detector 0.74; ocr saw no text; pod black (yellow 0.000, aspect 2.0); colour Black (Bk0.99); lever: weak match, add references from this angle
- `199909` box 0: `113` 0.301, `74` 0.299, `112` 0.286; below_min_sim, short by 0.299; detector 0.91; ocr saw `Aliveyrace Grap` 0.54 h0.03, `Ear` 0.19 h0.08; pod yellow (yellow 0.009, aspect 1.2); colour Multi (G0.42 Bl0.21 R0.17 Y0.14); lever: weak match, add references from this angle
- `202081` box 0: `74` 0.301, `98` 0.292, `112` 0.279; below_min_sim, short by 0.299; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 1.5); colour Multi (W0.56 G0.38); lever: weak match, add references from this angle
- `205617` box 1: `98` 0.302, `97` 0.296, `103` 0.283; below_min_sim, short by 0.298; detector 0.76; ocr saw `Chro` 0.87 h0.02, `B.R.M` 0.55 h0.09; pod unclear (yellow 0.000, aspect 1.3); colour Black (Bk0.85 G0.14); lever: weak match, add references from this angle
- `200289` box 0: `74` 0.302, `113` 0.302, `112` 0.274; below_min_sim, short by 0.298; detector 0.94; read `1`; pod black (yellow 0.000, aspect 1.8); colour Blue (Bl0.80 P0.10); lever: weak match, add references from this angle
- `201343` box 0: `31` 0.303, `47` 0.278, `27` 0.278; below_min_sim, short by 0.296; detector 0.62; ocr saw no text; pod black (yellow 0.000, aspect 3.0); colour Black (Bk1.00); lever: weak match, add references from this angle
- … 2400 more in report.json

## number-unmatched (177)

- `199717` box 0: `113` 0.310, `112` 0.269, `83` 0.222; below_min_sim, short by 0.290; detector 0.95; read `6`; start list 6>16 2.53, 6 0.00; pod unclear (yellow 0.000, aspect 1.3); colour Multi (W0.25 R0.22 P0.16 G0.16 Y0.14); lever: no entry has number 6
- `199715` box 0: `113` 0.323, `112` 0.287, `62` 0.248; below_min_sim, short by 0.277; detector 0.95; read `6`; start list 6>16 2.97, 46 0.20; pod unclear (yellow 0.000, aspect 1.3); colour Multi (W0.24 G0.20 R0.18 P0.15 Y0.15); lever: no entry has number 6
- `204531` box 0: `5` 0.389, `121` 0.382, `42` 0.378; below_min_sim, short by 0.211; detector 0.91; read `58`; start list 58>8 -6.85, 50 -7.68 no list read; pod yellow (yellow 0.007, aspect 3.0); colour Black (Bk0.72 R0.12 G0.10 B0.05); lever: no entry has number 58
- `203261` box 0: `62` 0.391, `26` 0.322, `75` 0.305; below_min_sim, short by 0.209; detector 0.72; read `06`; start list 06>64 -5.87, 62 -6.66 no list read; pod black (yellow 0.000, aspect 2.4); colour Black (Bk0.80 G0.17); lever: no entry has number 06
- `199685` box 0: `86` 0.392, `94` 0.344, `97` 0.271; below_min_sim, short by 0.208; detector 0.88; read `86`, `37`; start list 86/37>37 0.00, 86 0.00 close call; pod black (yellow 0.000, aspect 1.5); colour Multi (G0.52 G0.27 R0.08 W0.06 Bk0.05); lever: no entry has number 86 or 37
- `201581` box 0: `115` 0.415, `103` 0.385, `112` 0.373; below_min_sim, short by 0.185; detector 0.23; read `2`; start list 2>2 0.00, 22 -3.97; pod black (yellow 0.000, aspect 1.7); colour Black (Bk0.94); lever: no entry has number 2
- `198881` box 0: `31` 0.434, `40` 0.432, `21` 0.425; below_min_sim, short by 0.166; detector 0.85; read `0`; start list 0>6 -5.57, 8 -7.52 no list read; pod unclear (yellow 0.000, aspect 1.3); colour White (W0.73 G0.14 Y0.07); lever: no entry has number 0
- `203241` box 2: `98` 0.442, `74` 0.382, `115` 0.376; below_min_sim, short by 0.158; detector 0.24; read `2`; start list 2>2 0.00, 26 -0.10 close call; pod black (yellow 0.000, aspect 1.7); colour Black (Bk0.74 G0.17 B0.05); lever: no entry has number 2
- `198777` box 0: `98` 0.444, `75` 0.413, `3` 0.407; below_min_sim, short by 0.156; detector 0.95; read `0`, `6`; start list 0>10 -3.58, 2 -6.09; pod unclear (yellow 0.000, aspect 1.4); colour Orange (O0.61 G0.19 B0.12 Bk0.06); lever: no entry has number 0
- `201029` box 0: `22` 0.475, `115` 0.378, `98` 0.377; below_min_sim, short by 0.125; detector 0.84; read `0`; start list 0>6 -6.24, 8 -6.99 no list read; pod unclear (yellow 0.000, aspect 1.3); colour Multi (Bk0.64 B0.24 W0.08); lever: no entry has number 0
- `203247` box 0: `5` 0.478, `39` 0.464, `80` 0.443; below_min_sim, short by 0.122; detector 0.95; read `90`; start list 90>90 0.00, 790 -2.72; pod unclear (yellow 0.000, aspect 1.4); colour Multi (Bk0.41 G0.40 G0.11); lever: no entry has number 90
- `204539` box 0: `94` 0.482, `3` 0.442, `121` 0.435; below_min_sim, short by 0.118; detector 0.75; read `58`; start list 58>8 -5.96, 28 -6.89 no list read; pod yellow (yellow 0.033, aspect 2.3); colour Multi (Bk0.39 R0.26 G0.15 P0.14); lever: no entry has number 58
- `201027` box 0: `22` 0.487, `115` 0.402, `112` 0.387; below_min_sim, short by 0.113; detector 0.86; read `0`; start list 0>6 -6.07, 8 -6.64 no list read; pod unclear (yellow 0.000, aspect 1.3); colour Multi (Bk0.62 B0.25 W0.08); lever: no entry has number 0
- `199393` box 0: `43` 0.503, `42` 0.470, `30` 0.467; below_min_sim, short by 0.097; detector 0.67; read `56`; start list 56>50 -9.21, 51 -9.21 no list read; pod black (yellow 0.000, aspect 2.3); colour Grey (G0.53 Bk0.25 W0.15); lever: no entry has number 56
- `199913` box 1: `26` 0.530, `44` 0.528, `86` 0.496; below_min_sim, short by 0.070; detector 0.94; read `8`; start list 8>18 0.69, 28 0.69 close call; pod yellow (yellow 0.035, aspect 0.9); colour Brown (B0.57 R0.22 Bk0.09 O0.06); lever: no entry has number 8
- `199911` box 1: `44` 0.532, `26` 0.530, `86` 0.488; below_min_sim, short by 0.068; detector 0.94; read `8`; start list 8>18 0.69, 28 0.69 close call; pod yellow (yellow 0.037, aspect 0.9); colour Brown (B0.58 R0.21 Bk0.08 O0.06); lever: no entry has number 8
- `198377` box 0: `101` 0.536, `97` 0.515, `26` 0.425; below_min_sim, short by 0.064; detector 0.82; read `1`; start list 1>10 0.05, 1 0.00 close call; pod black (yellow 0.000, aspect 2.8); colour Multi (G0.33 W0.21 R0.20 Bl0.14 Bk0.10); lever: no entry has number 1
- `199909` box 1: `44` 0.542, `26` 0.536, `86` 0.496; below_min_sim, short by 0.058; detector 0.95; read `8`; start list 8>18 0.69, 28 0.69 close call; pod yellow (yellow 0.035, aspect 0.9); colour Brown (B0.58 R0.21 Bk0.08 O0.06); lever: no entry has number 8
- `198447` box 0: `83` 0.556, `3` 0.481, `75` 0.419; below_min_sim, short by 0.044; detector 0.96; read `52`, `0`; start list 52/0>10 0.34, 52 0.00 close call; pod black (yellow 0.000, aspect 1.4); colour Blue (Bl0.55 G0.27 Bk0.13); lever: no entry has number 52 or 0
- `199471` box 1: `60` 0.557, `97` 0.510, `83` 0.479; below_min_sim, short by 0.043; detector 0.93; read `2`; start list 2>121 6.18, 21 5.77 close call; pod yellow (yellow 0.010, aspect 1.6); colour Green (G0.79 Bk0.18); lever: no entry has number 2
- … 157 more in report.json

## overlapped (1568)

- `200449` box 3: `74` 0.220, `97` 0.218, `113` 0.217; overlapped; detector 0.24; ocr saw no text; pod unclear (yellow 0.000, aspect 0.6)
- `202053` box 2: `112` 0.263, `74` 0.263, `113` 0.251; overlapped; detector 0.23; ocr saw no text; pod unclear (yellow 0.000, aspect 0.6)
- `201163` box 1: `26` 0.275, `83` 0.258, `3` 0.242; overlapped; detector 0.21; ocr saw `BOUR` 0.98 h0.20; pod black (yellow 0.000, aspect 1.8)
- `202079` box 3: `47` 0.287, `76` 0.261, `115` 0.250; overlapped; detector 0.20; ocr saw no text; pod black (yellow 0.000, aspect 1.4)
- `200213` box 2: `26` 0.289, `11` 0.250, `64` 0.242; overlapped; detector 0.38; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- `205593` box 2: `112` 0.294, `11` 0.284, `62` 0.284; overlapped; detector 0.45; ocr saw no text; pod black (yellow 0.000, aspect 2.9)
- `199989` box 1: `103` 0.295, `74` 0.272, `113` 0.271; overlapped; detector 0.25; ocr saw no text; pod unclear (yellow 0.000, aspect 0.6)
- `200537` box 2: `78` 0.297, `113` 0.296, `103` 0.294; overlapped; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7)
- `198439` box 1: `74` 0.298, `62` 0.289, `60` 0.280; overlapped; detector 0.29; ocr saw no text; pod black (yellow 0.000, aspect 2.5)
- `202081` box 2: `76` 0.299, `74` 0.270, `115` 0.248; overlapped; detector 0.26; ocr saw no text; pod unclear (yellow 0.000, aspect 0.9)
- `199981` box 2: `3` 0.301, `76` 0.265, `103` 0.264; overlapped; detector 0.24; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1)
- `202201` box 2: `74` 0.303, `115` 0.290, `11` 0.279; overlapped; detector 0.37; ocr saw no text; pod black (yellow 0.000, aspect 2.1)
- `201969` box 2: `113` 0.304, `112` 0.294, `74` 0.271; overlapped; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 2.9)
- `201061` box 1: `103` 0.305, `3` 0.265, `74` 0.264; overlapped; detector 0.37; ocr saw `e` 0.87 h0.35; pod unclear (yellow 0.000, aspect 1.0)
- `205543` box 1: `108` 0.305, `115` 0.287, `74` 0.285; overlapped; detector 0.20; read `2`; pod unclear (yellow 0.000, aspect 0.7)
- `200381` box 1: `113` 0.310, `74` 0.305, `112` 0.299; overlapped; detector 0.25; ocr saw `PEUGEOT` 0.99 h0.34; pod black (yellow 0.000, aspect 4.7)
- `205491` box 2: `74` 0.312, `115` 0.274, `112` 0.270; overlapped; detector 0.23; ocr saw no text; pod unclear (yellow 0.000, aspect 1.4)
- `200635` box 1: `26` 0.312, `83` 0.249, `3` 0.210; overlapped; detector 0.21; read `1`; pod black (yellow 0.000, aspect 1.6)
- `201053` box 2: `43` 0.314, `121` 0.274, `74` 0.270; overlapped; detector 0.33; ocr saw `S` 0.55 h0.20; pod unclear (yellow 0.000, aspect 1.1)
- `201791` box 3: `115` 0.316, `98` 0.306, `103` 0.306; overlapped; detector 0.32; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- … 1548 more in report.json

## no-vehicle (147)

- `202303` burst 25: no vehicle at 0.2: strongest vehicle 0.12 (0.21x0.12 of frame)
- `202305` burst 25: no vehicle at 0.2: strongest vehicle 0.08 (0.40x0.13 of frame)
- `202325` burst 27: no vehicle at 0.2: strongest vehicle 0.14 (0.15x0.05 of frame)
- `202347` burst 28: no vehicle at 0.2: strongest vehicle 0.11 (0.04x0.02 of frame)
- `202349` burst 28: no vehicle at 0.2: strongest vehicle 0.10 (0.02x0.02 of frame)
- `202997` burst 87: no vehicle at 0.2: strongest vehicle 0.14 (0.96x0.98 of frame)
- `202999` burst 87: no vehicle at 0.2: strongest vehicle 0.19 (0.54x0.99 of frame)
- `203079` burst 96: no vehicle at 0.2: strongest vehicle 0.19 (0.41x0.35 of frame)
- `203081` burst 96: no vehicle at 0.2: strongest vehicle 0.17 (0.83x0.64 of frame)
- `203083` burst 97: no vehicle at 0.2: strongest vehicle 0.85 (0.07x0.06 of frame)
- `203085` burst 97: no vehicle at 0.2: strongest vehicle 0.83 (0.07x0.06 of frame)
- `203087` burst 97: no vehicle at 0.2: strongest vehicle 0.86 (0.07x0.06 of frame)
- `203089` burst 97: no vehicle at 0.2: strongest vehicle 0.84 (0.07x0.06 of frame)
- `203091` burst 98: no vehicle at 0.2: strongest vehicle 0.77 (0.06x0.06 of frame)
- `203093` burst 98: no vehicle at 0.2: strongest vehicle 0.77 (0.06x0.06 of frame)
- `203139` burst 105: no vehicle at 0.2: strongest vehicle 0.15 (0.06x0.07 of frame)
- `203145` burst 105: no vehicle at 0.2: strongest vehicle 0.34 (0.07x0.07 of frame)
- `203177` burst 109: no vehicle at 0.2: strongest vehicle 0.18 (1.00x1.00 of frame)
- `203223` burst 114: no vehicle at 0.2: strongest vehicle 0.93 (0.07x0.07 of frame)
- `203225` burst 114: no vehicle at 0.2: strongest vehicle 0.94 (0.07x0.07 of frame)
- … 127 more in report.json
