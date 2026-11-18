# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1

## Summary

5010 vehicles/images, identified rate 32%

- identified: 1593 (32%)
- team-obvious: 0 (0%)
- weak-match: 2080 (42%)
- no-references: 0 (0%)
- number-unmatched: 149 (3%)
- conflict: 52 (1%)
- overlapped: 868 (17%)
- already-tagged: 17 (0%)
- no-vehicle: 251 (5%)
- median weak-match: top-1 0.509, margin 0.035
- colours: no colour 1918, Red 402, Black 343, Multi 91, Grey 177, Purple 80, Green 327, Pink 204, White 441, Blue 492, Brown 96, Yellow 127, Orange 44

## detector score

- 0.00-0.30: 610 boxes, 8 identified
- 0.30-0.40: 265 boxes, 6 identified
- 0.40-0.50: 155 boxes, 1 identified
- 0.50-0.70: 243 boxes, 13 identified
- 0.70-1.00: 3469 boxes, 1565 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one team tag only; add under `rules.sponsor_keywords` after checking:
- `woolworth` → `Motorsport|Number|11`: 4 identified, would hint 6 unidentified
- `simpson` → `Motorsport|Number|70`: 2 identified, would hint 5 unidentified
- `sale` → `Motorsport|Number|33`: 7 identified, would hint 4 unidentified
- `turbos` → `Motorsport|Number|90`: 4 identified, would hint 4 unidentified
- `martini` → `Motorsport|Number|97`: 13 identified, would hint 3 unidentified
- `ndhiv` → `Motorsport|Number|66`: 3 identified, would hint 3 unidentified
- `skod` → `Motorsport|Number|50`: 2 identified, would hint 2 unidentified
- `olsbergs` → `Motorsport|Number|85`: 3 identified, would hint 1 unidentified
- `helix` → `Motorsport|Number|94`: 2 identified, would hint 1 unidentified
- `networkq` → `Motorsport|Number|3`: 9 identified, would hint 0 unidentified
- `andy` → `Motorsport|Number|27`: 8 identified, would hint 0 unidentified
- `aswmc` → `Motorsport|Number|101`: 8 identified, would hint 0 unidentified
- `motorhomes` → `Motorsport|Number|33`: 8 identified, would hint 0 unidentified
- `demontweeks` → `Motorsport|Number|98`: 7 identified, would hint 0 unidentified
- `llookers` → `Motorsport|Number|80`: 4 identified, would hint 0 unidentified
- `bevan` → `Motorsport|Number|98`: 3 identified, would hint 0 unidentified
- `cibie` → `Motorsport|Number|14`: 3 identified, would hint 0 unidentified
- `hillclimb` → `Motorsport|Number|83`: 3 identified, would hint 0 unidentified
- `kitchen` → `Motorsport|Number|102`: 3 identified, would hint 0 unidentified
- `knott` → `Motorsport|Number|25`: 3 identified, would hint 0 unidentified

## bursts (776 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×429, 1s ×305, 2s ×41, 541s ×1
frames per burst: 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 12, 12, 12, 13, 13, 13, 13, 13, 13, 14, 14, 14, 14, 15, 15, 15, 15, 15, 15, 15, 15, 15, 16, 16, 16, 17, 17, 17, 17, 18, 18, 18, 19, 20, 21, 22, 23, 23, 30, 216

closest to the next burst (possible split):
- burst 385: 216 frames, next burst starts -1191s later
- burst 35: 6 frames, next burst starts 2s later
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
- burst 252: 4 frames over 2s, largest gap 2s, 4 with vehicles, 0 without

## weak-match (2080)

- `202451` box 0: `790` 0.197, `60` 0.196, `52` 0.186; below_min_sim, short by 0.403; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 5.7); colour Green (G0.95); lever: weak match, add references from this angle
- `201709` box 0: `84` 0.206, `39` 0.202, `87` 0.197; below_min_sim, short by 0.394; detector 0.59; ocr saw no text; pod yellow (yellow 0.001, aspect 2.5); colour Green (G0.64 Y0.14 Bk0.05 W0.05); lever: weak match, add references from this angle
- `205287` box 1: `39` 0.213, `64` 0.197, `790` 0.197; below_min_sim, short by 0.387; detector 0.33; ocr saw `` 0.00 h0.05; pod unclear (yellow 0.000, aspect 1.1); colour unclear (G0.42 Bk0.41 G0.06); lever: weak match, add references from this angle
- `198229` box 0: `39` 0.216, `790` 0.215, `87` 0.211; below_min_sim, short by 0.384; detector 0.97; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.76); lever: weak match, add references from this angle
- `201655` box 0: `87` 0.216, `84` 0.197, `64` 0.192; below_min_sim, short by 0.384; detector 0.27; ocr saw no text; pod black (yellow 0.000, aspect 3.7); colour unclear (R0.30 M0.19 B0.12 G0.11 G0.09 W0.06 P0.06); lever: weak match, add references from this angle
- `199391` box 2: `84` 0.218, `87` 0.210, `790` 0.196; below_min_sim, short by 0.382; detector 0.20; ocr saw no text; pod black (yellow 0.000, aspect 3.9); colour unclear (Bk0.68 G0.15 G0.08); lever: weak match, add references from this angle
- `199857` box 0: `790` 0.218, `39` 0.201, `64` 0.194; below_min_sim, short by 0.382; detector 0.97; ocr saw `ly Tyre Centre` 0.75 h0.12, `FaIy` 0.29 h0.13, `oombard` 0.18 h0.14; pod black (yellow 0.000, aspect 1.8); colour Blue (Bl0.52 G0.20 W0.09 M0.07); lever: weak match, add references from this angle
- `199565` box 0: `84` 0.224, `64` 0.216, `87` 0.213; below_min_sim, short by 0.376; detector 0.96; ocr saw no text; pod black (yellow 0.000, aspect 1.6); colour Black (Bk0.70 G0.12); lever: weak match, add references from this angle
- `201635` box 0: `87` 0.227, `39` 0.215, `790` 0.195; below_min_sim, short by 0.373; detector 0.33; ocr saw no text; pod black (yellow 0.000, aspect 5.0); colour Green (G0.90 Bk0.06); lever: weak match, add references from this angle
- `199487` box 2: `39` 0.231, `41` 0.224, `87` 0.223; below_min_sim, short by 0.369; detector 0.21; ocr saw no text; pod yellow (yellow 0.009, aspect 0.7); colour unclear (Bl0.35 G0.21 M0.20 Y0.09 P0.08); lever: weak match, add references from this angle
- `205433` box 1: `39` 0.232, `41` 0.207, `790` 0.205; below_min_sim, short by 0.368; detector 0.90; ocr saw no text; pod black (yellow 0.000, aspect 1.6); colour unclear (G0.46 W0.29 G0.06 M0.05); lever: weak match, add references from this angle
- `199563` box 0: `84` 0.236, `64` 0.233, `87` 0.231; below_min_sim, short by 0.364; detector 0.96; ocr saw no text; pod black (yellow 0.000, aspect 1.6); colour Black (Bk0.71 G0.14); lever: weak match, add references from this angle
- `201831` box 0: `39` 0.237, `87` 0.235, `84` 0.229; below_min_sim, short by 0.363; detector 0.51; ocr saw no text; pod black (yellow 0.000, aspect 4.9); colour Purple (P0.61 Bk0.18 M0.07); lever: weak match, add references from this angle
- `205589` box 1: `87` 0.237, `84` 0.235, `790` 0.201; below_min_sim, short by 0.363; detector 0.27; ocr saw no text; pod black (yellow 0.000, aspect 2.0); colour unclear (Bk0.43 G0.27 G0.06 W0.06 B0.05); lever: weak match, add references from this angle
- `199649` box 3: `39` 0.237, `87` 0.236, `790` 0.205; below_min_sim, short by 0.363; detector 0.77; ocr saw no text; pod black (yellow 0.000, aspect 1.5); colour unclear (W0.60 G0.25); lever: weak match, add references from this angle
- `199239` box 0: `39` 0.238, `87` 0.214, `790` 0.196; below_min_sim, short by 0.362; detector 0.31; ocr saw no text; pod black (yellow 0.000, aspect 1.8); colour Grey (G0.47 W0.31 B0.07 G0.06); lever: weak match, add references from this angle
- `199523` box 0: `790` 0.238, `87` 0.231, `78` 0.205; below_min_sim, short by 0.362; detector 0.75; ocr saw `EBC` 0.97 h0.04, `FASSI` 0.94 h0.04, `SSIC SPEED CH` 0.73 h0.02; pod unclear (yellow 0.001, aspect 0.6); colour Red (R0.73 G0.10 P0.06); lever: weak match, add references from this angle
- `199717` box 1: `790` 0.239, `39` 0.232, `87` 0.197; below_min_sim, short by 0.361; detector 0.23; ocr saw `BMM` 0.90 h0.40; pod black (yellow 0.000, aspect 3.3); colour unclear (O0.57 R0.36); lever: weak match, add references from this angle
- `205269` box 1: `790` 0.240, `39` 0.228, `87` 0.227; below_min_sim, short by 0.360; detector 0.25; ocr saw no text; pod black (yellow 0.000, aspect 3.9); colour unclear (Bk0.46 B0.41); lever: weak match, add references from this angle
- `204935` box 0: `790` 0.240, `39` 0.208, `87` 0.189; below_min_sim, short by 0.360; detector 0.29; ocr saw `-` 0.43 h0.13, `VEW BAR` 0.41 h0.13; pod black (yellow 0.000, aspect 4.7); colour unclear (R0.24 G0.24 W0.10 G0.10 M0.10 B0.08 P0.06); lever: weak match, add references from this angle
- … 2060 more in report.json

## number-unmatched (149)

- `199715` box 0: `790` 0.276, `39` 0.231, `87` 0.190; below_min_sim, short by 0.324; detector 0.91; read `6`; start list 6>6 0.00, 16 -0.60 close call; pod unclear (yellow 0.000, aspect 1.4); colour Pink (P0.67 R0.16 B0.06 P0.06); lever: no entry has number 6
- `199683` box 0: `790` 0.289, `97` 0.203, `39` 0.196; below_min_sim, short by 0.311; detector 0.94; read `86`, `37`; start list 86/37>37 0.00, 86 0.00 close call; pod black (yellow 0.000, aspect 1.5); colour unclear (W0.35 G0.27 G0.15 M0.08 O0.05); lever: no entry has number 86 or 37
- `199685` box 0: `790` 0.297, `64` 0.217, `39` 0.204; below_min_sim, short by 0.302; detector 0.94; read `37`, `86`, `0`; start list 37/86/0>37 0.00, 86 0.00 close call; pod black (yellow 0.000, aspect 1.5); colour unclear (W0.36 G0.27 G0.15 M0.10); lever: no entry has number 37 or 86 or 0
- `199717` box 0: `790` 0.314, `83` 0.281, `67` 0.246; below_min_sim, short by 0.286; detector 0.92; read `6`; start list 6>76 0.25, 6 0.00 close call; pod unclear (yellow 0.000, aspect 1.4); colour Pink (P0.90); lever: no entry has number 6
- `203073` box 0: `732` 0.331, `52` 0.321, `39` 0.294; below_min_sim, short by 0.269; detector 0.35; read `86`; start list 86>86 0.00, 36 -1.78 close call; pod black (yellow 0.000, aspect 2.9); colour unclear (R0.44 P0.43); lever: no entry has number 86
- `204531` box 0: `730` 0.384, `732` 0.383, `47` 0.378; below_min_sim, short by 0.216; detector 0.93; read `58`; start list 58>8 -7.60, 68 -8.11 no list read; pod yellow (yellow 0.006, aspect 3.0); colour Pink (P0.54 P0.18 R0.16 B0.08); lever: no entry has number 58
- `200181` box 0: `820` 0.395, `119` 0.393, `27` 0.385; below_min_sim, short by 0.205; detector 0.95; read `62`; start list 62>62 0.00, 102 -0.76 close call; pod black (yellow 0.000, aspect 2.1); colour Brown (B0.69 O0.16); lever: no entry has number 62
- `199517` box 0: `40` 0.401, `731` 0.311, `95` 0.244; below_min_sim, short by 0.199; detector 0.93; read `12`; start list 12>120 0.44, 12 0.00 close call; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.67 P0.13 R0.05); lever: no entry has number 12
- `198579` box 0: `83` 0.455, `85` 0.438, `75` 0.423; below_min_sim, short by 0.145; detector 0.93; read `06`, `71`; start list 06/71>50 0.92, 107 0.89 close call; pod unclear (yellow 0.000, aspect 1.3); colour unclear (G0.38 G0.34 B0.13 W0.05); lever: no entry has number 06 or 71
- `199785` box 0: `83` 0.458, `104` 0.454, `790` 0.445; below_min_sim, short by 0.142; detector 0.96; read `100`, `52`; start list 100/52>100 0.00, 52 0.00 close call; pod unclear (yellow 0.000, aspect 1.3); colour Blue (Bl0.49 P0.36); lever: no entry has number 100 or 52
- `200179` box 0: `820` 0.465, `27` 0.422, `60` 0.418; below_min_sim, short by 0.135; detector 0.95; read `62`; start list 62>102 0.31, 62 0.00 close call; pod black (yellow 0.000, aspect 2.0); colour Brown (B0.75 O0.10); lever: no entry has number 62
- `205447` box 0: `97` 0.476, `26` 0.447, `112` 0.432; below_min_sim, short by 0.124; detector 0.94; read `688`; start list 688>808 -5.23, 68 -5.34 no list read; pod unclear (yellow 0.000, aspect 1.2); colour unclear (P0.21 W0.20 R0.20 G0.13 B0.10 M0.08); lever: no entry has number 688
- `205449` box 0: `97` 0.477, `112` 0.465, `26` 0.465; below_min_sim, short by 0.123; detector 0.94; read `688`; start list 688>68 -4.87, 86 -6.16 no list read; pod unclear (yellow 0.000, aspect 1.2); colour unclear (W0.29 R0.20 P0.13 M0.11 B0.10 G0.09); lever: no entry has number 688
- `205445` box 0: `112` 0.480, `26` 0.467, `97` 0.452; below_min_sim, short by 0.120; detector 0.95; read `688`; start list 688>68 -6.07, 808 -6.96 no list read; pod unclear (yellow 0.000, aspect 1.2); colour unclear (W0.27 P0.18 R0.18 G0.12 M0.12 B0.07); lever: no entry has number 688
- `199711` box 0: `97` 0.499, `796` 0.476, `94` 0.455; below_min_sim, short by 0.101; detector 0.95; read `06`, `71`; start list 06/71>807 1.37, 107 1.28 close call; pod black (yellow 0.000, aspect 1.5); colour Green (G0.57 G0.17 B0.11 W0.06); lever: no entry has number 06 or 71
- `199393` box 0: `121` 0.500, `730` 0.480, `43` 0.468; below_min_sim, short by 0.100; detector 0.95; read `56`; start list 56>6 -7.82, 36 -8.11 no list read; pod black (yellow 0.000, aspect 2.7); colour White (W0.55 M0.10 G0.09 G0.07 Bk0.05); lever: no entry has number 56
- `202023` box 0: `30` 0.501, `42` 0.485, `64` 0.477; below_min_sim, short by 0.099; detector 0.95; read `73`; start list 73>73 0.00, 3 -6.05; pod black (yellow 0.000, aspect 2.8); colour Red (R0.62 G0.10 G0.07 P0.07); lever: no entry has number 73
- `198447` box 0: `100` 0.513, `40` 0.387, `A0` 0.382; below_min_sim, short by 0.086; detector 0.97; read `0`, `52`; start list 0/52>10 0.25, 52 0.00 close call; pod black (yellow 0.000, aspect 1.4); colour Blue (Bl0.89); lever: no entry has number 0 or 52
- `198763` box 0: `103` 0.517, `98` 0.490, `64` 0.480; below_min_sim, short by 0.083; detector 0.94; read `883`; start list 883>808 -5.89, 83 -6.54 no list read; pod unclear (yellow 0.000, aspect 1.1); colour Black (Bk0.83 G0.06); lever: no entry has number 883
- `200477` box 0: `60` 0.522, `820` 0.503, `101` 0.462; below_min_sim, short by 0.078; detector 0.94; read `62`; start list 62>102 0.07, 62 0.00 close call; pod black (yellow 0.000, aspect 1.8); colour Brown (B0.62 Bk0.18 G0.07); lever: no entry has number 62
- … 129 more in report.json

## conflict (52)

- `202505` box 0: `66` 0.577, `87` 0.542, `69` 0.484; conflict; detector 0.95; read `7`; start list 7>86 10.09, 87 7.41; pod black (yellow 0.000, aspect 1.8); colour Black (Bk0.53 P0.17 B0.10 Bl0.06)
- `198289` box 0: `A0` 0.599, `121` 0.510, `94` 0.509; conflict; detector 0.95; read `2`; start list 2>20 2.87, 2 0.00 (burst of 3); pod black (yellow 0.000, aspect 1.6); colour Red (R0.73 P0.15)
- `205581` box 0: `66` 0.615, `60` 0.582, `75` 0.563; conflict; detector 0.95; read `7`; start list 7>87 7.01, 807 3.69; pod black (yellow 0.000, aspect 1.5); colour Purple (P0.72 Bl0.14)
- `198897` box 0: `35` 0.615, `813` 0.495, `112` 0.440; conflict; detector 0.94; ocr saw `287` 0.99 h0.07, `MAYNARD` 0.98 h0.06, `人` 0.92 h0.07; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.67 G0.11)
- `198903` box 0: `35` 0.619, `813` 0.518, `112` 0.463; conflict; detector 0.95; read `287`; start list 287>28 -7.17, 7 -14.65 no list read; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.62 G0.11 B0.07 M0.06)
- `198905` box 0: `35` 0.620, `813` 0.522, `112` 0.477; conflict; detector 0.95; read `287`; start list 287>28 -7.01, 7 -13.74 no list read; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.52 G0.22 B0.06 M0.05)
- `198899` box 0: `35` 0.622, `813` 0.505, `112` 0.450; conflict; detector 0.95; read `287`; start list 287>28 -6.90, 37 -13.48 no list read; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.65 G0.10 B0.05 M0.05)
- `199831` box 0: `78` 0.632, `105` 0.458, `67` 0.456; conflict; detector 0.97; ocr saw `024` 0.84 h0.04, `COBRA` 0.65 h0.03; pod black (yellow 0.000, aspect 1.5); colour unclear (W0.39 G0.37 B0.09 G0.05)
- `199833` box 0: `78` 0.633, `105` 0.503, `83` 0.484; conflict; detector 0.97; ocr saw `2024` 0.99 h0.10, `COBRA` 0.90 h0.05; pod black (yellow 0.000, aspect 1.5); colour White (W0.52 G0.21 B0.09)
- `198907` box 0: `35` 0.633, `813` 0.511, `78` 0.481; conflict; detector 0.95; read `287`; start list 287>28 -7.13, 7 -12.90 no list read; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.72 G0.07)
- `198291` box 0: `A0` 0.638, `95` 0.563, `94` 0.534; conflict; detector 0.96; read `2`; start list 2>20 2.87, 2 0.00 (burst of 3); pod black (yellow 0.000, aspect 1.7); colour Red (R0.64 P0.23)
- `198895` box 0: `35` 0.638, `813` 0.488, `112` 0.479; conflict; detector 0.94; read `287`; start list 287>28 -6.50, 7 -11.82 no list read; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.56 G0.14 P0.07 G0.06 B0.05 M0.05)
- `199835` box 0: `78` 0.638, `105` 0.477, `67` 0.455; conflict; detector 0.97; ocr saw `COBRA` 0.94 h0.04, `2024` 0.94 h0.10; pod black (yellow 0.000, aspect 1.5); colour White (W0.57 G0.18 B0.08)
- `198293` box 0: `A0` 0.640, `94` 0.557, `A2` 0.531; conflict; detector 0.96; read `2`; start list 2>20 2.87, 2 0.00 (burst of 3); pod black (yellow 0.000, aspect 1.6); colour Red (R0.73 P0.12 B0.05)
- `198367` box 0: `103` 0.645, `98` 0.562, `796` 0.529; conflict; detector 0.94; read `28`; start list 28>28 0.00, 8 -8.53; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.80)
- `204413` box 0: `122` 0.649, `A2` 0.640, `121` 0.640; conflict; detector 0.97; read `62`; start list 62>62 0.00, 2 -7.01; pod black (yellow 0.000, aspect 2.0); colour White (W0.41 M0.21 G0.18 P0.05)
- `198901` box 0: `35` 0.652, `813` 0.531, `112` 0.489; conflict; detector 0.95; ocr saw `287` 0.99 h0.07, `MAYNARD` 0.97 h0.07, `Lucas` 0.95 h0.06; pod unclear (yellow 0.000, aspect 1.1); colour Blue (Bl0.66 G0.12 P0.05)
- `204435` box 0: `25` 0.661, `47` 0.650, `732` 0.649; conflict; detector 0.97; read `62`; start list 62>62 0.00, 2 -6.34; pod black (yellow 0.000, aspect 2.5); colour White (W0.45 M0.24 G0.10 B0.05)
- `204443` box 0: `122` 0.665, `41` 0.663, `47` 0.607; conflict; detector 0.97; read `62`; start list 62>62 0.00, 6 -6.12; pod black (yellow 0.000, aspect 1.6); colour White (W0.51 G0.30 M0.07)
- `204747` box 0: `35` 0.674, `112` 0.631, `813` 0.577; conflict; detector 0.94; ocr saw `MAYNARD` 0.98 h0.06, `Lucas` 0.91 h0.05, `0-20` 0.91 h0.02; pod unclear (yellow 0.000, aspect 1.2); colour Blue (Bl0.58 G0.12 B0.09)
- … 32 more in report.json

## overlapped (868)

- `202613` box 1: `85` 0.182, `39` 0.173, `41` 0.167; overlapped; detector 0.24; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8)
- `200537` box 1: `35` 0.219, `78` 0.205, `39` 0.198; overlapped; detector 0.28; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7)
- `201361` box 1: `64` 0.225, `39` 0.224, `78` 0.223; overlapped; detector 0.21; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3)
- `204197` box 1: `78` 0.236, `44` 0.233, `101` 0.225; overlapped; detector 0.26; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1)
- `199897` box 2: `790` 0.242, `78` 0.233, `64` 0.215; overlapped; detector 0.93; ocr saw no text; pod black (yellow 0.000, aspect 2.0)
- `198931` box 1: `35` 0.256, `60` 0.246, `101` 0.235; overlapped; detector 0.30; ocr saw no text; pod unclear (yellow 0.000, aspect 1.0)
- `204211` box 2: `39` 0.256, `41` 0.231, `731` 0.215; overlapped; detector 0.34; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `204209` box 2: `39` 0.257, `87` 0.220, `790` 0.216; overlapped; detector 0.65; ocr saw no text; pod black (yellow 0.000, aspect 1.4)
- `199493` box 3: `87` 0.260, `41` 0.252, `39` 0.248; overlapped; detector 0.79; ocr saw no text; pod yellow (yellow 0.068, aspect 0.8)
- `202185` box 2: `41` 0.263, `731` 0.260, `39` 0.258; overlapped; detector 0.65; ocr saw no text; pod black (yellow 0.000, aspect 1.5)
- `203897` box 2: `60` 0.264, `790` 0.241, `85` 0.201; overlapped; detector 0.21; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3)
- `199249` box 1: `49` 0.266, `39` 0.251, `85` 0.249; overlapped; detector 0.24; ocr saw no text; pod unclear (yellow 0.000, aspect 0.3)
- `201709` box 1: `39` 0.268, `790` 0.229, `87` 0.220; overlapped; detector 0.38; ocr saw no text; pod black (yellow 0.000, aspect 5.6)
- `202087` box 1: `64` 0.269, `790` 0.268, `42` 0.248; overlapped; detector 0.75; ocr saw `福` 0.15 h0.45; pod black (yellow 0.000, aspect 2.4)
- `199951` box 1: `39` 0.271, `60` 0.258, `97` 0.253; overlapped; detector 0.34; ocr saw no text; pod unclear (yellow 0.000, aspect 0.4)
- `199707` box 3: `67` 0.271, `78` 0.247, `39` 0.230; overlapped; detector 0.43; ocr saw no text; pod unclear (yellow 0.000, aspect 1.0)
- `200751` box 2: `39` 0.274, `87` 0.232, `78` 0.210; overlapped; detector 0.21; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1)
- `205069` box 2: `790` 0.274, `39` 0.273, `41` 0.235; overlapped; detector 0.37; read `20`; pod black (yellow 0.000, aspect 4.0)
- `205513` box 1: `790` 0.279, `39` 0.274, `87` 0.233; overlapped; detector 0.22; ocr saw no text; pod black (yellow 0.000, aspect 12.6)
- `199581` box 1: `39` 0.279, `84` 0.268, `87` 0.254; overlapped; detector 0.32; ocr saw no text; pod black (yellow 0.000, aspect 4.0)
- … 848 more in report.json

## no-vehicle (251)

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
- … 231 more in report.json
