# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

136 vehicles/images, identified rate 16%

- identified: 22 (16%)
- team-obvious: 0 (0%)
- weak-match: 98 (72%)
- no-references: 0 (0%)
- number-unmatched: 1 (1%)
- conflict: 0 (0%)
- overlapped: 9 (7%)
- already-tagged: 0 (0%)
- no-vehicle: 6 (4%)
- median weak-match: top-1 0.627, margin 0.043

## detector score

- 0.00-0.30: 8 boxes, 2 identified
- 0.30-0.40: 4 boxes, 0 identified
- 0.40-0.50: 5 boxes, 0 identified
- 0.50-0.70: 11 boxes, 4 identified
- 0.70-1.00: 102 boxes, 16 identified

## bursts (24 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×11, 1s ×11, 2s ×2
frames per burst: 1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 5, 5, 5, 5, 6, 8, 8, 9, 9, 10, 11

closest to the next burst (possible split):
- burst 7: 9 frames, next burst starts 2s later
- burst 1: 9 frames, next burst starts 8s later
- burst 4: 8 frames, next burst starts 9s later
- burst 8: 10 frames, next burst starts 10s later
- burst 17: 1 frames, next burst starts 10s later
- burst 6: 3 frames, next burst starts 11s later
- burst 15: 2 frames, next burst starts 11s later
- burst 23: 4 frames, next burst starts 13s later
- burst 3: 5 frames, next burst starts 14s later
- burst 2: 4 frames, next burst starts 16s later
- burst 13: 3 frames, next burst starts 18s later
- burst 10: 4 frames, next burst starts 19s later
- burst 20: 8 frames, next burst starts 28s later
- burst 9: 5 frames, next burst starts 29s later
- burst 12: 2 frames, next burst starts 36s later
- burst 16: 3 frames, next burst starts 36s later
- burst 11: 11 frames, next burst starts 39s later
- burst 21: 2 frames, next burst starts 43s later
- burst 18: 4 frames, next burst starts 44s later
- burst 5: 3 frames, next burst starts 45s later

largest within-burst gap (possible merge):
- burst 4: 8 frames over 3s, largest gap 2s, 8 with vehicles, 0 without
- burst 20: 8 frames over 3s, largest gap 2s, 7 with vehicles, 1 without
- burst 1: 9 frames over 1s, largest gap 1s, 9 with vehicles, 0 without
- burst 3: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 7: 9 frames over 1s, largest gap 1s, 9 with vehicles, 0 without
- burst 8: 10 frames over 2s, largest gap 1s, 9 with vehicles, 1 without
- burst 9: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 10: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 11: 11 frames over 1s, largest gap 1s, 11 with vehicles, 0 without
- burst 14: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 16: 3 frames over 1s, largest gap 1s, 2 with vehicles, 1 without
- burst 22: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 24: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 2: 4 frames over 0s, largest gap 0s, 4 with vehicles, 0 without
- burst 5: 3 frames over 0s, largest gap 0s, 3 with vehicles, 0 without
- burst 6: 3 frames over 0s, largest gap 0s, 1 with vehicles, 2 without
- burst 12: 2 frames over 0s, largest gap 0s, 2 with vehicles, 0 without
- burst 13: 3 frames over 0s, largest gap 0s, 3 with vehicles, 0 without
- burst 15: 2 frames over 0s, largest gap 0s, 2 with vehicles, 0 without
- burst 17: 1 frames over 0s, largest gap 0s, 0 with vehicles, 1 without

## weak-match (98)

- `202809` box 1: `26` 0.328, `39` 0.322, `85` 0.306; below_min_sim, short by 0.272; detector 0.94; ocr saw `82t` 0.39, `ie` 0.27; pod black (yellow 0.000, aspect 1.7); lever: weak match, add references from this angle
- `202589` box 0: `43` 0.357, `74` 0.356, `47` 0.348; below_min_sim, short by 0.243; detector 0.38; ocr saw `tim` 0.99, `thr` 0.24; pod unclear (yellow 0.000, aspect 1.0); lever: weak match, add references from this angle
- `202743` box 0: `35` 0.363, `39` 0.346, `74` 0.329; below_min_sim, short by 0.237; detector 0.33; ocr saw no text; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `202591` box 0: `43` 0.365, `81` 0.347, `40` 0.343; below_min_sim, short by 0.235; detector 0.26; ocr saw `tim` 0.99, `for` 0.51; pod unclear (yellow 0.000, aspect 0.9); lever: weak match, add references from this angle
- `202629` box 0: `83` 0.391, `27` 0.371, `39` 0.362; below_min_sim, short by 0.209; detector 0.88; ocr saw no text; pod black (yellow 0.000, aspect 2.6); lever: weak match, add references from this angle
- `202557` box 0: `43` 0.396, `40` 0.375, `74` 0.358; below_min_sim, short by 0.204; detector 0.28; ocr saw `tim` 0.99; pod unclear (yellow 0.000, aspect 1.0); lever: weak match, add references from this angle
- `202631` box 1: `60` 0.414, `83` 0.405, `39` 0.393; below_min_sim, short by 0.186; detector 0.46; ocr saw no text; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `202587` box 0: `74` 0.417, `43` 0.403, `56` 0.370; below_min_sim, short by 0.183; detector 0.52; ocr saw `tim` 0.99, `te` 0.52, `at` 0.19; pod unclear (yellow 0.000, aspect 1.2); lever: weak match, add references from this angle
- `202613` box 0: `8` 0.464, `3` 0.443, `60` 0.410; below_min_sim, short by 0.136; detector 0.80; read `175`; pod black (yellow 0.000, aspect 2.0); lever: weak match, add references from this angle
- `202747` box 0: `82` 0.471, `63` 0.452, `85` 0.443; below_min_sim, short by 0.129; detector 0.41; ocr saw no text; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- `202897` box 1: `74` 0.473, `35` 0.394, `83` 0.373; below_min_sim, short by 0.127; detector 0.40; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8); lever: weak match, add references from this angle
- `202841` box 0: `85` 0.475, `83` 0.447, `58` 0.397; below_min_sim, short by 0.125; detector 0.85; ocr saw no text; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `202941` box 0: `83` 0.482, `26` 0.448, `63` 0.446; below_min_sim, short by 0.118; detector 0.55; ocr saw no text; pod black (yellow 0.000, aspect 2.1); lever: weak match, add references from this angle
- `202617` box 0: `80` 0.485, `63` 0.448, `54` 0.447; below_min_sim, short by 0.115; detector 0.84; read `175`; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `202555` box 0: `85` 0.489, `76` 0.470, `83` 0.405; below_min_sim, short by 0.111; detector 0.89; ocr saw `daotzbe` 0.75, `acecanes` 0.12, `tensaaaes` 0.11; pod unclear (yellow 0.001, aspect 1.5); lever: weak match, add references from this angle
- `202611` box 0: `66` 0.489, `80` 0.476, `3` 0.442; below_min_sim, short by 0.111; detector 0.92; ocr saw `a7` 0.18; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `202643` box 0: `83` 0.489, `63` 0.389, `39` 0.353; below_min_sim, short by 0.111; detector 0.31; ocr saw no text; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `202637` box 0: `27` 0.497, `85` 0.496, `76` 0.488; below_min_sim, short by 0.103; detector 0.71; ocr saw `ki3ving` 0.51; pod unclear (yellow 0.000, aspect 1.3); lever: weak match, add references from this angle
- `202923` box 0: `40` 0.503, `54` 0.502, `86` 0.478; below_min_sim, short by 0.097; detector 0.94; read `790`; pod black (yellow 0.000, aspect 2.6); lever: weak match, add references from this angle
- `202947` box 0: `83` 0.505, `86` 0.493, `30` 0.463; below_min_sim, short by 0.095; detector 0.46; ocr saw no text; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- … 78 more in report.json

## number-unmatched (1)

- `202921` box 0: `54` 0.526, `60` 0.482, `86` 0.480; below_min_sim, short by 0.074; detector 0.93; read `193`; pod black (yellow 0.000, aspect 2.5); lever: no entry has number 193

## overlapped (9)

- `202633` box 1: `40` 0.382, `21` 0.345, `85` 0.344; overlapped; detector 0.72; ocr saw `k13` 0.57; pod unclear (yellow 0.000, aspect 1.2)
- `202633` box 2: `39` 0.467, `25` 0.458, `49` 0.416; overlapped; detector 0.45; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `202629` box 1: `63` 0.485, `83` 0.423, `67` 0.419; overlapped; detector 0.41; ocr saw `sex` 0.80; pod unclear (yellow 0.000, aspect 1.3)
- `202809` box 0: `82` 0.523, `80` 0.505, `60` 0.467; overlapped; detector 0.27; read `39`; pod black (yellow 0.000, aspect 2.3)
- `202747` box 1: `83` 0.578, `62` 0.568, `82` 0.492; overlapped; detector 0.90; ocr saw no text; pod black (yellow 0.000, aspect 2.2)
- `202947` box 1: `83` 0.616, `86` 0.598, `34` 0.569; overlapped; detector 0.84; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1)
- `202941` box 1: `83` 0.619, `94` 0.607, `86` 0.560; overlapped; detector 0.26; ocr saw no text; pod black (yellow 0.000, aspect 2.1)
- `202643` box 1: `83` 0.681, `39` 0.536, `43` 0.498; overlapped; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2)
- `202743` box 1: `80` 0.684, `62` 0.557, `66` 0.512; overlapped; detector 0.94; ocr saw `a` 0.60; pod black (yellow 0.000, aspect 1.9)

## no-vehicle (6)

- `202593` burst 6: no vehicle at 0.2: strongest car 0.48 (0.10x0.05 of frame), strongest vehicle car 0.48 (0.10x0.05 of frame)
- `202595` burst 6: no vehicle at 0.2: strongest car 0.85 (0.10x0.05 of frame), strongest vehicle car 0.85 (0.10x0.05 of frame)
- `202645` burst 8: no vehicle at 0.2: strongest person 0.85 (0.17x0.52 of frame), strongest vehicle motorcycle 0.13 (0.48x0.32 of frame)
- `202791` burst 16: no vehicle at 0.2: strongest train 0.23 (1.00x0.55 of frame), strongest vehicle car 0.15 (1.00x0.58 of frame)
- `202805` burst 17: no vehicle at 0.2: strongest person 0.31 (0.23x0.28 of frame), strongest vehicle car 0.04 (0.22x0.19 of frame)
- `202911` burst 20: no vehicle at 0.2: strongest class 62 0.21 (0.99x0.95 of frame), strongest vehicle car 0.05 (1.00x0.76 of frame)
