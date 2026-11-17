# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

5021 vehicles/images, identified rate 50%

- identified: 2529 (50%)
- team-obvious: 0 (0%)
- weak-match: 1261 (25%)
- no-references: 0 (0%)
- number-unmatched: 70 (1%)
- conflict: 13 (0%)
- overlapped: 867 (17%)
- already-tagged: 27 (1%)
- no-vehicle: 254 (5%)
- median weak-match: top-1 0.588, margin 0.030
- colours: no colour 1562, Red 467, Black 423, Multi 96, Grey 199, Purple 120, Green 381, Pink 206, Yellow 135, White 474, Blue 533, Brown 99, Orange 45

## detector score

- 0.00-0.30: 611 boxes, 62 identified
- 0.30-0.40: 266 boxes, 40 identified
- 0.40-0.50: 155 boxes, 22 identified
- 0.50-0.70: 243 boxes, 41 identified
- 0.70-1.00: 3465 boxes, 2364 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one team tag only; add under `rules.sponsor_keywords` after checking:
- `alpine` → `Motorsport|Number|52`: 5 identified, would hint 1 unidentified
- `olsbergs` → `Motorsport|Number|85`: 3 identified, would hint 1 unidentified
- `chronographes` → `Motorsport|Number|74`: 2 identified, would hint 1 unidentified
- `llington` → `Motorsport|Number|104`: 2 identified, would hint 1 unidentified
- `mcrae` → `Motorsport|Number|3`: 2 identified, would hint 1 unidentified
- `mintex` → `Motorsport|Number|115`: 2 identified, would hint 1 unidentified
- `woolworth` → `Motorsport|Number|11`: 11 identified, would hint 0 unidentified
- `networkq` → `Motorsport|Number|3`: 9 identified, would hint 0 unidentified
- `andy` → `Motorsport|Number|27`: 8 identified, would hint 0 unidentified
- `aswmc` → `Motorsport|Number|101`: 8 identified, would hint 0 unidentified
- `motorhomes` → `Motorsport|Number|33`: 8 identified, would hint 0 unidentified
- `llookers` → `Motorsport|Number|62`: 7 identified, would hint 0 unidentified
- `tommi` → `Motorsport|Number|22`: 6 identified, would hint 0 unidentified
- `mobil` → `Motorsport|Number|62`: 5 identified, would hint 0 unidentified
- `andudno` → `Motorsport|Number|62`: 4 identified, would hint 0 unidentified
- `autosport` → `Motorsport|Number|100`: 4 identified, would hint 0 unidentified
- `llandudno` → `Motorsport|Number|62`: 4 identified, would hint 0 unidentified
- `mmishimoto` → `Motorsport|Number|75`: 4 identified, would hint 0 unidentified
- `sparco` → `Motorsport|Number|62`: 4 identified, would hint 0 unidentified
- `advan` → `Motorsport|Number|104`: 3 identified, would hint 0 unidentified

## bursts (775 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×426, 1s ×306, 2s ×42, 541s ×1
frames per burst: 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 12, 12, 12, 13, 13, 13, 13, 13, 13, 14, 14, 14, 14, 15, 15, 15, 15, 15, 15, 15, 15, 15, 16, 16, 16, 17, 17, 17, 17, 18, 18, 18, 19, 20, 21, 22, 23, 23, 30, 216

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
- burst 26: 6 frames over 2s, largest gap 2s, 6 with vehicles, 0 without
- burst 47: 5 frames over 2s, largest gap 2s, 5 with vehicles, 0 without
- burst 78: 8 frames over 3s, largest gap 2s, 8 with vehicles, 0 without
- burst 90: 9 frames over 2s, largest gap 2s, 8 with vehicles, 1 without
- burst 111: 9 frames over 4s, largest gap 2s, 9 with vehicles, 0 without
- burst 114: 6 frames over 2s, largest gap 2s, 3 with vehicles, 3 without
- burst 146: 6 frames over 2s, largest gap 2s, 6 with vehicles, 0 without
- burst 147: 6 frames over 3s, largest gap 2s, 6 with vehicles, 0 without
- burst 149: 5 frames over 2s, largest gap 2s, 5 with vehicles, 0 without
- burst 156: 5 frames over 3s, largest gap 2s, 5 with vehicles, 0 without
- burst 163: 8 frames over 2s, largest gap 2s, 8 with vehicles, 0 without
- burst 164: 10 frames over 4s, largest gap 2s, 10 with vehicles, 0 without
- burst 196: 4 frames over 2s, largest gap 2s, 4 with vehicles, 0 without
- burst 220: 15 frames over 7s, largest gap 2s, 15 with vehicles, 0 without
- burst 236: 9 frames over 2s, largest gap 2s, 7 with vehicles, 2 without
- burst 238: 6 frames over 2s, largest gap 2s, 6 with vehicles, 0 without
- burst 244: 3 frames over 2s, largest gap 2s, 3 with vehicles, 0 without

## weak-match (1261)

- `199707` box 0: `85` 0.278, `21` 0.264, `26` 0.258; below_min_sim, short by 0.322; detector 0.87; ocr saw `Castrol` 0.98 h0.16, `P` 0.21 h0.05; pod unclear (yellow 0.000, aspect 1.0); colour Pink (P0.92); lever: weak match, add references from this angle
- `199523` box 0: `21` 0.292, `74` 0.279, `62` 0.270; below_min_sim, short by 0.308; detector 0.75; ocr saw `EBC` 0.97 h0.04, `FASSI` 0.94 h0.04, `SSIC SPEED CH` 0.73 h0.02; pod unclear (yellow 0.001, aspect 0.6); colour Red (R0.73 G0.10 P0.06); lever: weak match, add references from this angle
- `199705` box 0: `21` 0.295, `62` 0.280, `26` 0.276; below_min_sim, short by 0.305; detector 0.93; ocr saw `Castrol` 0.99 h0.22, `NUPKYKARKKUNEN` 0.22 h0.05; pod black (yellow 0.000, aspect 1.5); colour Pink (P0.92 W0.05); lever: weak match, add references from this angle
- `199455` box 0: `39` 0.296, `43` 0.277, `60` 0.276; below_min_sim, short by 0.304; detector 0.91; ocr saw no text; pod black (yellow 0.000, aspect 1.4); colour Pink (P0.96); lever: weak match, add references from this angle
- `201349` box 0: `78` 0.298, `113` 0.295, `67` 0.273; below_min_sim, short by 0.302; detector 0.74; ocr saw no text; pod black (yellow 0.000, aspect 2.6); colour Black (Bk0.79 P0.08 G0.08); lever: weak match, add references from this angle
- `199703` box 0: `21` 0.302, `62` 0.275, `63` 0.275; below_min_sim, short by 0.298; detector 0.92; ocr saw `Castrol` 0.98 h0.21, `NUPKYKARKKUNEN` 0.51 h0.04; pod black (yellow 0.000, aspect 1.5); colour Pink (P0.93); lever: weak match, add references from this angle
- `201347` box 0: `62` 0.310, `78` 0.260, `113` 0.231; below_min_sim, short by 0.290; detector 0.91; ocr saw no text; pod black (yellow 0.000, aspect 2.6); colour Black (Bk0.85 G0.10); lever: weak match, add references from this angle
- `202073` box 0: `21` 0.314, `63` 0.303, `62` 0.286; below_min_sim, short by 0.286; detector 0.93; ocr saw no text; pod black (yellow 0.000, aspect 6.1); colour White (W0.94); lever: weak match, add references from this angle
- `201353` box 0: `113` 0.317, `62` 0.312, `78` 0.295; below_min_sim, short by 0.283; detector 0.80; ocr saw no text; pod black (yellow 0.000, aspect 2.5); colour Black (Bk0.73 G0.14); lever: weak match, add references from this angle
- `202071` box 0: `21` 0.323, `63` 0.313, `22` 0.296; below_min_sim, short by 0.277; detector 0.93; ocr saw no text; pod black (yellow 0.000, aspect 6.7); colour White (W0.93); lever: weak match, add references from this angle
- `200289` box 0: `41` 0.324, `76` 0.320, `39` 0.302; below_min_sim, short by 0.276; detector 0.96; ocr saw `` 0.00 h0.07; pod black (yellow 0.000, aspect 1.8); colour Purple (P0.87 Bl0.08); lever: weak match, add references from this angle
- `201327` box 0: `55` 0.326, `78` 0.300, `35` 0.297; below_min_sim, short by 0.274; detector 0.91; ocr saw no text; pod black (yellow 0.000, aspect 2.7); colour Black (Bk0.89); lever: weak match, add references from this angle
- `201343` box 0: `62` 0.329, `78` 0.313, `31` 0.298; below_min_sim, short by 0.271; detector 0.93; ocr saw no text; pod black (yellow 0.000, aspect 2.9); colour Black (Bk0.86); lever: weak match, add references from this angle
- `199483` box 0: `21` 0.333, `113` 0.313, `3` 0.281; below_min_sim, short by 0.268; detector 0.97; read `00`; pod black (yellow 0.000, aspect 1.4); colour unclear (W0.23 M0.22 R0.21 G0.18 B0.06); lever: weak match, add references from this angle
- `199489` box 2: `87` 0.334, `76` 0.320, `113` 0.314; below_min_sim, short by 0.267; detector 0.26; ocr saw no text; pod yellow (yellow 0.025, aspect 1.4); colour unclear (R0.32 P0.30 M0.24); lever: weak match, add references from this angle
- `202069` box 1: `21` 0.334, `63` 0.318, `62` 0.295; below_min_sim, short by 0.266; detector 0.92; ocr saw no text; pod black (yellow 0.000, aspect 4.8); colour White (W0.91); lever: weak match, add references from this angle
- `199857` box 0: `41` 0.336, `63` 0.335, `62` 0.300; below_min_sim, short by 0.264; detector 0.97; ocr saw `ly Tyre Centre` 0.75 h0.12, `FaIy` 0.29 h0.13, `oombard` 0.18 h0.14; pod black (yellow 0.000, aspect 1.8); colour Blue (Bl0.52 G0.20 W0.09 M0.07); lever: weak match, add references from this angle
- `199367` box 3: `39` 0.337, `63` 0.333, `21` 0.326; below_min_sim, short by 0.263; detector 0.75; ocr saw `` 0.00 h0.04; pod black (yellow 0.000, aspect 1.8); colour Green (G0.43 G0.15 P0.14 Bk0.13); lever: weak match, add references from this angle
- `202067` box 1: `21` 0.337, `63` 0.307, `50` 0.287; below_min_sim, short by 0.263; detector 0.92; ocr saw no text; pod black (yellow 0.000, aspect 5.1); colour White (W0.89 G0.06); lever: weak match, add references from this angle
- `199909` box 0: `63` 0.339, `21` 0.322, `50` 0.320; below_min_sim, short by 0.261; detector 0.95; ocr saw `品` 0.71 h0.07, `ALiveyrace Graph` 0.28 h0.03; pod yellow (yellow 0.009, aspect 1.2); colour Multi (M0.85 W0.07 P0.05); lever: weak match, add references from this angle
- … 1241 more in report.json

## number-unmatched (70)

- `199683` box 0: `86` 0.279, `50` 0.278, `63` 0.275; below_min_sim, short by 0.321; detector 0.94; read `86`, `37`; start list 86/37>37 0.00, 86 0.00 close call; pod black (yellow 0.000, aspect 1.5); colour unclear (W0.35 G0.27 G0.15 M0.08 O0.05); lever: no entry has number 86 or 37
- `199685` box 0: `86` 0.292, `39` 0.288, `63` 0.285; below_min_sim, short by 0.308; detector 0.94; read `37`, `86`, `0`; start list 37/86/0>37 0.00, 86 0.00 close call; pod black (yellow 0.000, aspect 1.5); colour unclear (W0.36 G0.27 G0.15 M0.10); lever: no entry has number 37 or 86 or 0
- `204531` box 0: `109` 0.490, `42` 0.422, `32` 0.416; below_min_sim, short by 0.110; detector 0.93; read `58`; start list 58>8 -7.60, 68 -8.11 no list read; pod yellow (yellow 0.006, aspect 3.0); colour Pink (P0.54 P0.18 R0.16 B0.08); lever: no entry has number 58
- `198447` box 0: `83` 0.509, `52` 0.501, `3` 0.476; below_min_sim, short by 0.090; detector 0.97; read `0`, `52`; start list 0/52>10 0.25, 52 0.00 close call; pod black (yellow 0.000, aspect 1.4); colour Blue (Bl0.89); lever: no entry has number 0 or 52
- `202307` box 0: `55` 0.539, `26` 0.526, `22` 0.501; below_min_sim, short by 0.061; detector 0.96; read `60`; start list 60>60 0.00, 6 -3.99; pod black (yellow 0.000, aspect 3.0); colour Pink (P0.75 P0.10 R0.07); lever: no entry has number 60
- `198497` box 0: `43` 0.584, `109` 0.570, `103` 0.566; below_min_sim, short by 0.016; detector 0.95; read `246`; start list 246>82 -5.44, 84 -5.51 no list read; pod unclear (yellow 0.000, aspect 1.2); colour Blue (Bl0.69 B0.06 G0.05); lever: no entry has number 246
- `205447` box 0: `83` 0.592, `76` 0.582, `21` 0.532; below_min_sim, short by 0.008; detector 0.94; read `688`; start list 688>808 -5.23, 68 -5.34 no list read; pod unclear (yellow 0.000, aspect 1.2); colour unclear (P0.21 W0.20 R0.20 G0.13 B0.10 M0.08); lever: no entry has number 688
- `205449` box 0: `76` 0.613, `83` 0.599, `21` 0.510; margin_too_small, short by 0.085; detector 0.94; read `688`; start list 688>68 -4.87, 86 -6.16 no list read; pod unclear (yellow 0.000, aspect 1.2); colour unclear (W0.29 R0.20 P0.13 M0.11 B0.10 G0.09); lever: no entry has number 688
- `204529` box 0: `109` 0.624, `33` 0.604, `47` 0.580; margin_too_small, short by 0.080; detector 0.94; read `58`; start list 58>8 -8.11, 28 -8.52 no list read; pod yellow (yellow 0.042, aspect 2.8); colour Purple (P0.50 B0.18 P0.17 R0.10); lever: no entry has number 58
- `204821` box 0: `103` 0.627, `98` 0.583, `44` 0.580; margin_too_small, short by 0.057; detector 0.89; read `30`; start list 30>30 0.00, 36 -2.35; pod black (yellow 0.000, aspect 2.8); colour Pink (P0.51 R0.40); lever: no entry has number 30
- `204511` box 0: `61` 0.628, `62` 0.609, `94` 0.554; margin_too_small, short by 0.081; detector 0.97; read `131`; start list 131>11 -6.44, 13 -7.82 no list read; pod black (yellow 0.000, aspect 2.7); colour White (W0.63 G0.14 B0.08 Bk0.05); lever: no entry has number 131
- `199909` box 1: `83` 0.632, `102` 0.608, `44` 0.581; margin_too_small, short by 0.077; detector 0.96; read `8`; start list 8>18 0.29, 8 0.00 close call; pod yellow (yellow 0.034, aspect 1.0); colour Yellow (Y0.67 B0.16); lever: no entry has number 8
- `204499` box 0: `104` 0.637, `121` 0.578, `109` 0.549; margin_too_small, short by 0.041; detector 0.96; read `131`; start list 131>31 -6.59, 11 -6.81 no list read; pod black (yellow 0.001, aspect 2.9); colour White (W0.65 G0.17 G0.07); lever: no entry has number 131
- `205445` box 0: `83` 0.637, `76` 0.637, `21` 0.503; margin_too_small, short by 0.099; detector 0.95; read `688`; start list 688>68 -6.07, 808 -6.96 no list read; pod unclear (yellow 0.000, aspect 1.2); colour unclear (W0.27 P0.18 R0.18 G0.12 M0.12 B0.07); lever: no entry has number 688
- `199911` box 1: `83` 0.638, `102` 0.615, `44` 0.599; margin_too_small, short by 0.077; detector 0.96; read `8`; start list 8>18 0.00, 8 0.00 close call; pod yellow (yellow 0.035, aspect 0.9); colour Yellow (Y0.77 B0.11); lever: no entry has number 8
- `202591` box 1: `83` 0.648, `44` 0.631, `102` 0.616; margin_too_small, short by 0.083; detector 0.83; read `307`, `73`; start list 307/73>73 0.00, 730 -2.51; pod black (yellow 0.000, aspect 2.0); colour Black (Bk0.80 B0.09); lever: no entry has number 307 or 73
- `198579` box 0: `21` 0.652, `85` 0.650, `75` 0.588; margin_too_small, short by 0.098; detector 0.93; read `06`, `71`; start list 06/71>50 0.92, 107 0.89 close call; pod unclear (yellow 0.000, aspect 1.3); colour unclear (G0.38 G0.34 B0.13 W0.05); lever: no entry has number 06 or 71
- `199913` box 1: `83` 0.653, `102` 0.626, `44` 0.617; margin_too_small, short by 0.072; detector 0.96; read `8`; start list 8>18 0.29, 8 0.00 close call; pod yellow (yellow 0.037, aspect 0.9); colour Yellow (Y0.79 B0.10); lever: no entry has number 8
- `204541` box 0: `30` 0.662, `94` 0.649, `3` 0.638; margin_too_small, short by 0.088; detector 0.96; read `609`, `58`; start list 609/58>809 -6.86, 5 -7.85 no list read; pod yellow (yellow 0.068, aspect 1.9); colour Red (R0.41 B0.27 P0.21); lever: no entry has number 609 or 58
- `205241` box 0: `103` 0.673, `98` 0.633, `116` 0.628; margin_too_small, short by 0.060; detector 0.94; read `45`; start list 45>4 -6.37, 5 -7.29 no list read; pod unclear (yellow 0.000, aspect 1.1); colour Red (R0.72 B0.17); lever: no entry has number 45
- … 50 more in report.json

## conflict (13)

- `202327` box 0: `21` 0.760, `61` 0.647, `66` 0.634; conflict; detector 0.91; ocr saw no text; pod black (yellow 0.000, aspect 1.5); colour Pink (P0.96)
- `202505` box 0: `86` 0.919, `21` 0.882, `75` 0.588; conflict; detector 0.95; read `7`; start list 7>86 10.09, 87 7.41; pod black (yellow 0.000, aspect 1.8); colour Black (Bk0.53 P0.17 B0.10 Bl0.06)
- `202493` box 0: `10` 0.942, `60` 0.881, `101` 0.833; conflict; detector 0.94; ocr saw `福` 0.10 h0.06, `1` 0.04 h0.06; pod black (yellow 0.001, aspect 1.8); colour Red (R0.47 B0.18 P0.16 P0.08)
- `202489` box 0: `10` 0.958, `60` 0.916, `101` 0.841; conflict; detector 0.93; read `0`; pod yellow (yellow 0.001, aspect 1.8); colour Red (R0.53 P0.18 B0.13 P0.08)
- `203013` box 0: `97` 0.979, `16` 0.816, `101` 0.697; conflict; detector 0.95; read `16`; start list 16>16 0.00, 18 -3.26 (weak read); pod black (yellow 0.000, aspect 2.3); colour Pink (P0.61 M0.15 R0.08 W0.08)
- `202681` box 0: `76` 0.984, `78` 0.983, `35` 0.755; conflict; detector 0.94; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2); colour Brown (B0.72 W0.08 G0.07)
- `202687` box 0: `76` 0.986, `78` 0.977, `35` 0.750; conflict; detector 0.95; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); colour Brown (B0.76 G0.14)
- `202689` box 0: `76` 0.987, `78` 0.970, `35` 0.740; conflict; detector 0.95; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); colour Brown (B0.60 G0.21 W0.07)
- `202661` box 0: `76` 0.989, `78` 0.975, `35` 0.670; conflict; detector 0.97; ocr saw `2784NO` 0.72 h0.08; pod unclear (yellow 0.000, aspect 1.3); colour Brown (B0.76 G0.12)
- `202693` box 0: `76` 0.992, `78` 0.967, `35` 0.734; conflict; detector 0.96; ocr saw no text; pod unclear (yellow 0.000, aspect 1.4); colour Brown (B0.49 G0.19 W0.17)
- `202659` box 0: `76` 0.994, `78` 0.952, `35` 0.705; conflict; detector 0.96; ocr saw `2784:NO` 0.39 h0.06; pod unclear (yellow 0.000, aspect 1.3); colour Brown (B0.80 G0.10)
- `202691` box 0: `76` 0.996, `78` 0.966, `35` 0.767; conflict; detector 0.96; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); colour Brown (B0.66 G0.11 W0.08)
- `202657` box 0: `76` 0.996, `78` 0.930, `35` 0.688; conflict; detector 0.97; ocr saw `2784NO` 0.70 h0.08, `` 0.00 h0.08; pod unclear (yellow 0.000, aspect 1.1); colour Brown (B0.81 G0.08)

## overlapped (867)

- `202613` box 1: `47` 0.246, `82` 0.228, `39` 0.218; overlapped; detector 0.24; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8)
- `200537` box 1: `113` 0.286, `47` 0.261, `22` 0.260; overlapped; detector 0.28; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7)
- `199951` box 1: `80` 0.307, `55` 0.304, `26` 0.295; overlapped; detector 0.34; ocr saw no text; pod unclear (yellow 0.000, aspect 0.4)
- `200155` box 1: `62` 0.318, `113` 0.301, `47` 0.276; overlapped; detector 0.20; ocr saw no text; pod unclear (yellow 0.000, aspect 0.9)
- `204197` box 1: `55` 0.319, `43` 0.310, `115` 0.304; overlapped; detector 0.26; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1)
- `201417` box 2: `62` 0.320, `21` 0.313, `74` 0.294; overlapped; detector 0.24; ocr saw no text; pod black (yellow 0.000, aspect 2.0)
- `205043` box 2: `115` 0.323, `41` 0.312, `76` 0.310; overlapped; detector 0.25; read `2`, `8`; pod black (yellow 0.000, aspect 1.6)
- `199621` box 1: `22` 0.324, `105` 0.322, `78` 0.308; overlapped; detector 0.29; ocr saw no text; pod black (yellow 0.000, aspect 2.1)
- `199137` box 2: `39` 0.332, `76` 0.315, `87` 0.298; overlapped; detector 0.51; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1)
- `199707` box 3: `97` 0.335, `63` 0.308, `113` 0.303; overlapped; detector 0.43; ocr saw no text; pod unclear (yellow 0.000, aspect 1.0)
- `199703` box 1: `97` 0.338, `8` 0.315, `39` 0.306; overlapped; detector 0.33; ocr saw no text; pod black (yellow 0.000, aspect 3.1)
- `205091` box 2: `46` 0.338, `35` 0.316, `47` 0.292; overlapped; detector 0.37; ocr saw no text; pod black (yellow 0.000, aspect 2.4)
- `201345` box 1: `31` 0.340, `40` 0.319, `27` 0.294; overlapped; detector 0.79; ocr saw no text; pod black (yellow 0.000, aspect 2.6)
- `200007` box 1: `62` 0.342, `83` 0.333, `39` 0.325; overlapped; detector 0.25; ocr saw no text; pod unclear (yellow 0.000, aspect 0.5)
- `202565` box 2: `41` 0.342, `76` 0.335, `115` 0.331; overlapped; detector 0.22; read `208`; pod black (yellow 0.000, aspect 1.8)
- `198931` box 1: `80` 0.344, `26` 0.332, `35` 0.321; overlapped; detector 0.30; ocr saw no text; pod unclear (yellow 0.000, aspect 1.0)
- `204247` box 2: `115` 0.344, `76` 0.325, `41` 0.323; overlapped; detector 0.60; read `208`; pod black (yellow 0.000, aspect 2.7)
- `199705` box 3: `95` 0.345, `97` 0.333, `39` 0.322; overlapped; detector 0.35; ocr saw no text; pod unclear (yellow 0.000, aspect 1.4)
- `201655` box 1: `115` 0.345, `42` 0.332, `62` 0.331; overlapped; detector 0.27; ocr saw no text; pod black (yellow 0.000, aspect 2.9)
- `201179` box 1: `47` 0.347, `121` 0.315, `3` 0.301; overlapped; detector 0.29; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7)
- … 847 more in report.json

## no-vehicle (254)

- `202325` burst 27: no vehicle at 0.2: strongest vehicle 0.27 (0.05x0.04 of frame)
- `202347` burst 28: no vehicle at 0.2: strongest vehicle 0.08 (0.04x0.02 of frame)
- `202349` burst 28: no vehicle at 0.2: strongest vehicle 0.10 (0.04x0.02 of frame)
- `202479` burst 40: no car: the box check dropped 1 boxes (crowd 0.03 at 0.27)
- `202481` burst 40: no car: the box check dropped 1 boxes (crowd 0.02 at 0.34)
- `202997` burst 87: no car: the box check dropped 1 boxes (road 0.03 at 0.20)
- `202999` burst 87: no car: the box check dropped 1 boxes (road 0.04 at 0.39)
- `203041` burst 90: no vehicle at 0.2: strongest vehicle 0.11 (0.56x0.42 of frame)
- `203075` burst 95: no car: the box check dropped 1 boxes (trees 0.01 at 0.26)
- `203077` burst 95: no car: the box check dropped 1 boxes (trees 0.01 at 0.28)
- `203079` burst 96: no vehicle at 0.2: strongest vehicle 0.20 (0.23x0.71 of frame)
- `203081` burst 96: no car: the box check dropped 2 boxes (building 0.07 at 0.27, trees 0.01 at 0.33)
- `203083` burst 97: no vehicle at 0.2: strongest vehicle 0.76 (0.07x0.06 of frame)
- `203085` burst 97: no vehicle at 0.2: strongest vehicle 0.76 (0.07x0.06 of frame)
- `203087` burst 97: no vehicle at 0.2: strongest vehicle 0.70 (0.07x0.06 of frame)
- `203089` burst 97: no vehicle at 0.2: strongest vehicle 0.69 (0.07x0.06 of frame)
- `203091` burst 98: no vehicle at 0.2: strongest vehicle 0.69 (0.07x0.06 of frame)
- `203093` burst 98: no vehicle at 0.2: strongest vehicle 0.71 (0.07x0.06 of frame)
- `203139` burst 105: no car: the box check dropped 1 boxes (trees 0.04 at 0.33)
- `203177` burst 109: no car: the box check dropped 1 boxes (person 0.07 at 0.30)
- … 234 more in report.json
