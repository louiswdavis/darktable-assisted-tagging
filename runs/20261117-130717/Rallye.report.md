# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

5035 vehicles/images, identified rate 35%

- identified: 1761 (35%)
- team-obvious: 0 (0%)
- weak-match: 1755 (35%)
- no-references: 0 (0%)
- number-unmatched: 122 (2%)
- conflict: 2 (0%)
- overlapped: 1046 (21%)
- already-tagged: 30 (1%)
- no-vehicle: 319 (6%)
- median weak-match: top-1 0.586, margin 0.029
- colours: no colour 1784, Red 407, Green 337, Black 399, Multi 78, Grey 185, Pink 187, Blue 479, Yellow 120, White 456, Purple 111, Brown 101, Orange 42

## detector score

- 0.00-0.30: 687 boxes, 39 identified
- 0.30-0.40: 296 boxes, 13 identified
- 0.40-0.50: 180 boxes, 16 identified
- 0.50-0.70: 326 boxes, 74 identified
- 0.70-1.00: 3197 boxes, 1619 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one team tag only; add under `rules.sponsor_keywords` after checking:
- `sale` → `Motorsport|Number|33`: 4 identified, would hint 6 unidentified
- `copper` → `Motorsport|Number|31`: 10 identified, would hint 4 unidentified
- `motorhomes` → `Motorsport|Number|33`: 3 identified, would hint 3 unidentified
- `horse` → `Motorsport|Number|31`: 10 identified, would hint 2 unidentified
- `olsbergs` → `Motorsport|Number|85`: 3 identified, would hint 2 unidentified
- `advan` → `Motorsport|Number|104`: 2 identified, would hint 1 unidentified
- `llington` → `Motorsport|Number|104`: 2 identified, would hint 1 unidentified
- `maynard` → `Motorsport|Number|22`: 27 identified, would hint 0 unidentified
- `demontweeks` → `Motorsport|Number|98`: 9 identified, would hint 0 unidentified
- `networkq` → `Motorsport|Number|3`: 9 identified, would hint 0 unidentified
- `aswmc` → `Motorsport|Number|101`: 8 identified, would hint 0 unidentified
- `woolworth` → `Motorsport|Number|11`: 8 identified, would hint 0 unidentified
- `mobil` → `Motorsport|Number|62`: 7 identified, would hint 0 unidentified
- `cibie` → `Motorsport|Number|44`: 6 identified, would hint 0 unidentified
- `llookers` → `Motorsport|Number|62`: 6 identified, would hint 0 unidentified
- `graphic` → `Motorsport|Number|31`: 5 identified, would hint 0 unidentified
- `motul` → `Motorsport|Number|44`: 5 identified, would hint 0 unidentified
- `optimal` → `Motorsport|Number|31`: 5 identified, would hint 0 unidentified
- `andudno` → `Motorsport|Number|62`: 4 identified, would hint 0 unidentified
- `autosport` → `Motorsport|Number|100`: 4 identified, would hint 0 unidentified

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
- burst 90: 9 frames over 2s, largest gap 2s, 8 with vehicles, 1 without
- burst 111: 9 frames over 4s, largest gap 2s, 8 with vehicles, 1 without
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

## weak-match (1755)

- `202397` box 0: `74` 0.263, `113` 0.262, `62` 0.251; below_min_sim, short by 0.337; detector 0.85; ocr saw no text; pod black (yellow 0.000, aspect 1.6); colour Green (G0.90); lever: weak match, add references from this angle
- `199493` box 0: `62` 0.276, `113` 0.273, `39` 0.269; below_min_sim, short by 0.324; detector 0.91; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); colour unclear (W0.48 G0.46); lever: weak match, add references from this angle
- `200979` box 0: `74` 0.282, `115` 0.261, `113` 0.258; below_min_sim, short by 0.318; detector 0.87; ocr saw no text; pod black (yellow 0.000, aspect 2.8); colour White (W0.59 G0.21 Bk0.05 B0.05); lever: weak match, add references from this angle
- `201331` box 0: `39` 0.283, `47` 0.273, `3` 0.267; below_min_sim, short by 0.317; detector 0.74; ocr saw no text; pod black (yellow 0.000, aspect 2.5); colour unclear (Bk0.34 G0.34 B0.09 P0.09 W0.07); lever: weak match, add references from this angle
- `200093` box 1: `74` 0.285, `87` 0.274, `112` 0.255; below_min_sim, short by 0.315; detector 0.49; ocr saw no text; pod black (yellow 0.000, aspect 1.4); colour Black (Bk0.61 G0.22 W0.06); lever: weak match, add references from this angle
- `202079` box 2: `47` 0.287, `76` 0.261, `115` 0.250; below_min_sim, short by 0.313; detector 0.20; ocr saw no text; pod black (yellow 0.000, aspect 1.4); colour Black (Bk0.65 G0.15 B0.06 G0.06); lever: weak match, add references from this angle
- `199913` box 0: `74` 0.291, `113` 0.287, `97` 0.287; below_min_sim, short by 0.309; detector 0.90; ocr saw `品` 0.63 h0.06, `aLiveyrace GrapH` 0.36 h0.03; pod yellow (yellow 0.009, aspect 1.2); colour Multi (M0.83 W0.07); lever: weak match, add references from this angle
- `198495` box 0: `74` 0.291, `39` 0.270, `109` 0.264; below_min_sim, short by 0.309; detector 0.92; ocr saw `JAFFA` 0.94 h0.03, `Sponsored By` 0.91 h0.04, `The Wife` 0.62 h0.05; pod unclear (yellow 0.000, aspect 1.3); colour Blue (Bl0.63 G0.16 M0.08); lever: weak match, add references from this angle
- `201347` box 0: `31` 0.295, `47` 0.259, `27` 0.257; below_min_sim, short by 0.305; detector 0.75; ocr saw no text; pod black (yellow 0.000, aspect 2.7); colour Black (Bk0.91 G0.05); lever: weak match, add references from this angle
- `199911` box 0: `113` 0.296, `74` 0.295, `112` 0.292; below_min_sim, short by 0.303; detector 0.88; ocr saw `ALiveyrace GrapH` 0.42 h0.03, `` 0.00 h0.07; pod yellow (yellow 0.009, aspect 1.2); colour Multi (M0.81 W0.09); lever: weak match, add references from this angle
- `199857` box 0: `74` 0.298, `113` 0.272, `112` 0.263; below_min_sim, short by 0.302; detector 0.96; ocr saw `ly Tyre Centre` 0.77 h0.12, `A` 0.43 h0.14, `aombard` 0.23 h0.14; pod black (yellow 0.000, aspect 1.7); colour Blue (Bl0.70 G0.10 W0.06 M0.05); lever: weak match, add references from this angle
- `201375` box 0: `74` 0.300, `113` 0.259, `3` 0.257; below_min_sim, short by 0.300; detector 0.73; ocr saw no text; pod black (yellow 0.000, aspect 2.4); colour Black (Bk0.72 G0.16); lever: weak match, add references from this angle
- `199909` box 0: `113` 0.301, `74` 0.299, `112` 0.286; below_min_sim, short by 0.299; detector 0.91; ocr saw `ALivelyrace Grapl` 0.42 h0.03, `` 0.00 h0.08; pod yellow (yellow 0.009, aspect 1.2); colour Multi (M0.84 W0.10); lever: weak match, add references from this angle
- `205617` box 1: `98` 0.302, `97` 0.296, `103` 0.283; below_min_sim, short by 0.298; detector 0.76; ocr saw `Chro` 0.87 h0.02, `B.R.M` 0.82 h0.09; pod unclear (yellow 0.000, aspect 1.3); colour Black (Bk0.60 P0.22); lever: weak match, add references from this angle
- `200289` box 0: `74` 0.302, `113` 0.302, `112` 0.274; below_min_sim, short by 0.298; detector 0.94; ocr saw `建` 0.52 h0.09; pod black (yellow 0.000, aspect 1.8); colour Purple (P0.86 Bl0.07); lever: weak match, add references from this angle
- `201343` box 0: `31` 0.303, `47` 0.278, `27` 0.278; below_min_sim, short by 0.296; detector 0.62; ocr saw no text; pod black (yellow 0.000, aspect 3.0); colour Black (Bk0.85 G0.05); lever: weak match, add references from this angle
- `201349` box 0: `78` 0.305, `76` 0.299, `113` 0.298; below_min_sim, short by 0.295; detector 0.84; ocr saw no text; pod black (yellow 0.000, aspect 2.5); colour Black (Bk0.78 G0.14); lever: weak match, add references from this angle
- `199481` box 0: `74` 0.306, `39` 0.300, `115` 0.258; below_min_sim, short by 0.293; detector 0.95; ocr saw no text; pod yellow (yellow 0.005, aspect 1.8); colour Green (G0.93); lever: weak match, add references from this angle
- `199487` box 3: `113` 0.309, `112` 0.308, `98` 0.300; below_min_sim, short by 0.291; detector 0.67; ocr saw no text; pod yellow (yellow 0.004, aspect 0.7); colour Blue (Bl0.46 M0.28 G0.18); lever: weak match, add references from this angle
- `199915` box 1: `62` 0.309, `97` 0.309, `109` 0.291; below_min_sim, short by 0.291; detector 0.92; ocr saw `T坊` 0.13 h0.11; pod yellow (yellow 0.047, aspect 0.8); colour unclear (B0.24 Y0.23 P0.23 M0.16 P0.06 O0.05); lever: weak match, add references from this angle
- … 1735 more in report.json

## number-unmatched (122)

- `204531` box 0: `5` 0.389, `121` 0.382, `42` 0.378; below_min_sim, short by 0.211; detector 0.91; read `58`; start list 58>8 -7.27, 5 -8.12 no list read; pod yellow (yellow 0.007, aspect 3.0); colour Pink (P0.69 P0.25); lever: no entry has number 58
- `203261` box 0: `62` 0.391, `26` 0.322, `75` 0.305; below_min_sim, short by 0.209; detector 0.72; read `06`; start list 06>6 -5.93, 60 -6.62 no list read; pod black (yellow 0.000, aspect 2.4); colour Green (G0.73 W0.20); lever: no entry has number 06
- `199685` box 0: `86` 0.392, `94` 0.344, `97` 0.271; below_min_sim, short by 0.208; detector 0.88; read `86`, `37`; start list 86/37>37 0.00, 86 0.00 close call; pod black (yellow 0.000, aspect 1.5); colour unclear (G0.39 W0.21 G0.15 M0.13); lever: no entry has number 86 or 37
- `204539` box 0: `94` 0.482, `3` 0.442, `121` 0.435; below_min_sim, short by 0.118; detector 0.75; read `58`; start list 58>8 -8.11, 28 -8.52 no list read; pod yellow (yellow 0.033, aspect 2.3); colour unclear (P0.31 B0.28 P0.26 R0.09); lever: no entry has number 58
- `199393` box 0: `43` 0.503, `42` 0.470, `30` 0.467; below_min_sim, short by 0.097; detector 0.67; read `56`; start list 56>6 -7.82, 66 -8.11 no list read; pod black (yellow 0.000, aspect 2.3); colour White (W0.55 G0.12 M0.09 G0.08 Bk0.06); lever: no entry has number 56
- `204287` box 0: `121` 0.512, `3` 0.506, `5` 0.506; below_min_sim, short by 0.088; detector 0.92; read `40`; start list 40>80 1.94, 84 0.37 close call; pod black (yellow 0.000, aspect 1.9); colour Red (R0.89 P0.05); lever: no entry has number 40
- `199913` box 1: `26` 0.530, `44` 0.528, `86` 0.496; below_min_sim, short by 0.070; detector 0.94; read `8`; start list 8>18 0.00, 8 0.00 close call; pod yellow (yellow 0.035, aspect 0.9); colour Yellow (Y0.74 B0.13); lever: no entry has number 8
- `199911` box 1: `44` 0.532, `26` 0.530, `86` 0.488; below_min_sim, short by 0.068; detector 0.94; read `8`; start list 8>18 0.41, 28 0.00 close call; pod yellow (yellow 0.037, aspect 0.9); colour Yellow (Y0.75 B0.13); lever: no entry has number 8
- `199909` box 1: `44` 0.542, `26` 0.536, `86` 0.496; below_min_sim, short by 0.058; detector 0.95; read `8`; start list 8>18 0.29, 8 0.00 close call; pod yellow (yellow 0.035, aspect 0.9); colour Yellow (Y0.76 B0.10); lever: no entry has number 8
- `204821` box 0: `44` 0.551, `103` 0.544, `79` 0.528; below_min_sim, short by 0.049; detector 0.36; read `30`; start list 30>30 0.00, 36 -2.60; pod black (yellow 0.000, aspect 2.5); colour Pink (P0.85 R0.12); lever: no entry has number 30
- `198447` box 0: `83` 0.556, `3` 0.481, `75` 0.419; below_min_sim, short by 0.044; detector 0.96; read `52`, `0`; start list 52/0>52 0.00, 10 -0.56 close call; pod black (yellow 0.000, aspect 1.4); colour Blue (Bl0.90); lever: no entry has number 52 or 0
- `202589` box 2: `11` 0.563, `76` 0.545, `26` 0.535; below_min_sim, short by 0.037; detector 0.73; read `307`, `73`; start list 307/73>73 0.00, 730 -2.43; pod black (yellow 0.000, aspect 1.8); colour Black (Bk0.66 B0.15 G0.07); lever: no entry has number 307 or 73
- `199277` box 0: `41` 0.571, `52` 0.555, `62` 0.537; below_min_sim, short by 0.029; detector 0.89; read `33`; start list 33>33 0.00, 3 -7.42; pod yellow (yellow 0.007, aspect 2.4); colour Orange (O0.81 R0.06 G0.06); lever: no entry has number 33
- `202023` box 0: `30` 0.571, `109` 0.565, `42` 0.533; below_min_sim, short by 0.029; detector 0.94; read `73`; start list 73>73 0.00, 13 -7.05; pod black (yellow 0.000, aspect 2.8); colour Red (R0.59 G0.11 G0.10 P0.08); lever: no entry has number 73
- `205399` box 0: `75` 0.571, `97` 0.496, `83` 0.494; below_min_sim, short by 0.029; detector 0.94; read `07`; start list 07>28 0.33, 78 0.18 close call; pod black (yellow 0.000, aspect 1.5); colour Red (R0.46 B0.20 P0.13 P0.11); lever: no entry has number 07
- `198581` box 0: `85` 0.575, `25` 0.557, `46` 0.506; below_min_sim, short by 0.025; detector 0.91; read `06`, `71`; start list 06/71>50 2.01, 101 1.20 close call; pod unclear (yellow 0.000, aspect 1.3); colour unclear (G0.39 G0.37 B0.09 W0.06); lever: no entry has number 06 or 71
- `202587` box 1: `76` 0.577, `44` 0.516, `11` 0.507; below_min_sim, short by 0.023; detector 0.66; read `307`, `2`; start list 307>30 -6.72, 730 -7.38 no list read; pod black (yellow 0.000, aspect 1.7); colour Black (Bk0.79 B0.09); lever: no entry has number 307
- `199711` box 0: `97` 0.578, `86` 0.495, `85` 0.494; below_min_sim, short by 0.022; detector 0.94; read `06`, `71`; start list 06/71>107 2.46, 807 2.27 close call; pod black (yellow 0.000, aspect 1.5); colour Green (G0.56 G0.15 B0.13 W0.06); lever: no entry has number 06 or 71
- `204529` box 0: `3` 0.581, `109` 0.576, `25` 0.566; below_min_sim, short by 0.019; detector 0.93; read `58`; start list 58>68 -7.83, 8 -7.83 no list read; pod yellow (yellow 0.044, aspect 2.9); colour Purple (P0.47 B0.20 R0.14 P0.13); lever: no entry has number 58
- `205403` box 0: `75` 0.585, `66` 0.502, `83` 0.493; below_min_sim, short by 0.015; detector 0.94; read `07`; start list 07>28 0.29, 808 -0.21 close call; pod black (yellow 0.000, aspect 1.5); colour Red (R0.42 B0.20 P0.14 P0.13); lever: no entry has number 07
- … 102 more in report.json

## conflict (2)

- `202505` box 0: `21` 0.788, `66` 0.572, `80` 0.551; conflict; detector 0.94; read `7`, `0`; start list 7>86 10.29, 87 7.41; pod black (yellow 0.000, aspect 1.8); colour Black (Bk0.44 P0.21 B0.13 Bl0.07)
- `202121` box 0: `31` 0.926, `54` 0.752, `40` 0.720; conflict; detector 0.94; read `04`; pod black (yellow 0.000, aspect 1.4); colour Green (G0.89)

## overlapped (1046)

- `200449` box 3: `74` 0.220, `97` 0.218, `113` 0.217; overlapped; detector 0.24; ocr saw no text; pod unclear (yellow 0.000, aspect 0.6)
- `201163` box 1: `26` 0.275, `83` 0.258, `3` 0.242; overlapped; detector 0.21; ocr saw `BOURI` 0.54 h0.20; pod black (yellow 0.000, aspect 1.8)
- `200213` box 2: `26` 0.289, `11` 0.250, `64` 0.242; overlapped; detector 0.38; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- `205593` box 2: `112` 0.294, `11` 0.284, `62` 0.284; overlapped; detector 0.45; ocr saw no text; pod black (yellow 0.000, aspect 2.9)
- `199989` box 1: `103` 0.295, `74` 0.272, `113` 0.271; overlapped; detector 0.25; ocr saw no text; pod unclear (yellow 0.000, aspect 0.6)
- `200537` box 1: `78` 0.297, `113` 0.296, `103` 0.294; overlapped; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7)
- `198439` box 1: `74` 0.298, `62` 0.289, `60` 0.280; overlapped; detector 0.29; ocr saw no text; pod black (yellow 0.000, aspect 2.5)
- `199981` box 2: `3` 0.301, `76` 0.265, `103` 0.264; overlapped; detector 0.24; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1)
- `201061` box 1: `103` 0.305, `3` 0.265, `74` 0.264; overlapped; detector 0.37; ocr saw `e` 0.83 h0.35; pod unclear (yellow 0.000, aspect 1.0)
- `205543` box 1: `108` 0.305, `115` 0.287, `74` 0.285; overlapped; detector 0.20; read `2`; pod unclear (yellow 0.000, aspect 0.7)
- `200381` box 1: `113` 0.310, `74` 0.305, `112` 0.299; overlapped; detector 0.25; ocr saw `PEUGEOT` 0.99 h0.34; pod black (yellow 0.000, aspect 4.7)
- `200635` box 1: `26` 0.312, `83` 0.249, `3` 0.210; overlapped; detector 0.21; read `1`; pod black (yellow 0.000, aspect 1.6)
- `201053` box 2: `43` 0.314, `121` 0.274, `74` 0.270; overlapped; detector 0.33; ocr saw `+` 0.11 h0.20; pod unclear (yellow 0.000, aspect 1.1)
- `201329` box 1: `113` 0.318, `103` 0.315, `50` 0.307; overlapped; detector 0.31; ocr saw no text; pod unclear (yellow 0.000, aspect 0.9)
- `198495` box 1: `97` 0.318, `98` 0.317, `75` 0.315; overlapped; detector 0.21; ocr saw no text; pod unclear (yellow 0.000, aspect 0.3)
- `198245` box 2: `39` 0.318, `74` 0.305, `97` 0.294; overlapped; detector 0.26; ocr saw no text; pod black (yellow 0.000, aspect 5.1)
- `201713` box 1: `113` 0.320, `112` 0.294, `11` 0.292; overlapped; detector 0.27; ocr saw no text; pod black (yellow 0.000, aspect 3.2)
- `199455` box 1: `39` 0.320, `97` 0.307, `104` 0.274; overlapped; detector 0.45; ocr saw no text; pod black (yellow 0.000, aspect 1.5)
- `199979` box 3: `3` 0.323, `74` 0.293, `115` 0.287; overlapped; detector 0.29; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2)
- `204535` box 1: `3` 0.324, `104` 0.296, `42` 0.287; overlapped; detector 0.28; ocr saw `TYRES` 0.88 h0.09; pod yellow (yellow 0.002, aspect 1.7)
- … 1026 more in report.json

## no-vehicle (319)

- `202303` burst 25: no vehicle at 0.2: strongest vehicle 0.12 (0.21x0.12 of frame)
- `202305` burst 25: no vehicle at 0.2: strongest vehicle 0.08 (0.40x0.13 of frame)
- `202325` burst 27: no vehicle at 0.2: strongest vehicle 0.14 (0.15x0.05 of frame)
- `202347` burst 28: no vehicle at 0.2: strongest vehicle 0.11 (0.04x0.02 of frame)
- `202349` burst 28: no vehicle at 0.2: strongest vehicle 0.10 (0.02x0.02 of frame)
- `202371` burst 30: no car: the box check dropped 1 boxes
- `202479` burst 40: no car: the box check dropped 3 boxes
- `202481` burst 40: no car: the box check dropped 3 boxes
- `202483` burst 40: no car: the box check dropped 1 boxes
- `202593` burst 49: no car: the box check dropped 1 boxes
- `202791` burst 67: no car: the box check dropped 2 boxes
- `202997` burst 87: no vehicle at 0.2: strongest vehicle 0.14 (0.96x0.98 of frame)
- `202999` burst 87: no vehicle at 0.2: strongest vehicle 0.19 (0.54x0.99 of frame)
- `203041` burst 90: no car: the box check dropped 1 boxes
- `203075` burst 95: no car: the box check dropped 1 boxes
- `203077` burst 95: no car: the box check dropped 2 boxes
- `203079` burst 96: no vehicle at 0.2: strongest vehicle 0.19 (0.41x0.35 of frame)
- `203081` burst 96: no vehicle at 0.2: strongest vehicle 0.17 (0.83x0.64 of frame)
- `203083` burst 97: no vehicle at 0.2: strongest vehicle 0.85 (0.07x0.06 of frame)
- `203085` burst 97: no vehicle at 0.2: strongest vehicle 0.83 (0.07x0.06 of frame)
- … 299 more in report.json
