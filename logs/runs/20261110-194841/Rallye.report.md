# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

30 vehicles/images, identified rate 10%

- identified: 3 (10%)
- team-obvious: 0 (0%)
- weak-match: 22 (73%)
- no-references: 0 (0%)
- number-unmatched: 0 (0%)
- conflict: 0 (0%)
- overlapped: 4 (13%)
- already-tagged: 0 (0%)
- no-vehicle: 1 (3%)
- median weak-match: top-1 0.520, margin 0.034

## detector score

- 0.00-0.30: 2 boxes, 0 identified
- 0.30-0.40: 1 boxes, 0 identified
- 0.40-0.50: 3 boxes, 0 identified
- 0.50-0.70: 2 boxes, 0 identified
- 0.70-1.00: 21 boxes, 3 identified

## bursts (3 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 1s ×3
frames per burst: 5, 9, 10

closest to the next burst (possible split):
- burst 1: 9 frames, next burst starts 2s later
- burst 2: 10 frames, next burst starts 10s later

largest within-burst gap (possible merge):
- burst 1: 9 frames over 1s, largest gap 1s, 9 with vehicles, 0 without
- burst 2: 10 frames over 2s, largest gap 1s, 9 with vehicles, 1 without
- burst 3: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without

## weak-match (22)

- `202629` box 0: `83` 0.391, `27` 0.371, `39` 0.362; below_min_sim, short by 0.209; detector 0.88; ocr saw no text; pod black (yellow 0.000, aspect 2.6); lever: weak match, add references from this angle
- `202631` box 1: `60` 0.414, `83` 0.405, `39` 0.393; below_min_sim, short by 0.186; detector 0.46; ocr saw no text; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `202613` box 0: `8` 0.464, `3` 0.443, `60` 0.410; below_min_sim, short by 0.136; detector 0.80; read `175`; pod black (yellow 0.000, aspect 2.0); lever: weak match, add references from this angle
- `202617` box 0: `80` 0.485, `63` 0.448, `54` 0.447; below_min_sim, short by 0.115; detector 0.84; read `175`; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `202611` box 0: `66` 0.489, `80` 0.476, `3` 0.442; below_min_sim, short by 0.111; detector 0.92; ocr saw `a7` 0.18; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `202643` box 0: `83` 0.489, `63` 0.389, `39` 0.353; below_min_sim, short by 0.111; detector 0.31; ocr saw no text; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `202637` box 0: `27` 0.497, `85` 0.496, `76` 0.488; below_min_sim, short by 0.103; detector 0.71; ocr saw `ki3ving` 0.51; pod unclear (yellow 0.000, aspect 1.3); lever: weak match, add references from this angle
- `202635` box 0: `83` 0.509, `82` 0.478, `27` 0.473; below_min_sim, short by 0.091; detector 0.93; ocr saw `27b` 0.19; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `202615` box 0: `43` 0.511, `25` 0.501, `41` 0.494; below_min_sim, short by 0.089; detector 0.88; ocr saw `f75` 0.11; pod black (yellow 0.000, aspect 2.2); lever: weak match, add references from this angle
- `202633` box 0: `83` 0.512, `81` 0.447, `74` 0.436; below_min_sim, short by 0.088; detector 0.65; ocr saw `t` 0.23; pod black (yellow 0.000, aspect 2.8); lever: weak match, add references from this angle
- `202639` box 0: `60` 0.515, `63` 0.512, `40` 0.465; below_min_sim, short by 0.085; detector 0.63; ocr saw `a` 0.41, `tot` 0.14, `f` 0.10; pod unclear (yellow 0.000, aspect 1.3); lever: weak match, add references from this angle
- `202631` box 0: `85` 0.525, `83` 0.412, `60` 0.384; below_min_sim, short by 0.075; detector 0.82; ocr saw `rw` 0.26; pod unclear (yellow 0.000, aspect 1.2); lever: weak match, add references from this angle
- `202627` box 0: `80` 0.545, `60` 0.496, `63` 0.486; below_min_sim, short by 0.055; detector 0.94; read `175`; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- `202641` box 0: `83` 0.555, `86` 0.523, `27` 0.511; below_min_sim, short by 0.045; detector 0.92; ocr saw no text; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `202609` box 0: `66` 0.579, `3` 0.509, `80` 0.480; below_min_sim, short by 0.021; detector 0.93; ocr saw `sa` 0.19; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `202651` box 1: `74` 0.584, `39` 0.377, `35` 0.321; below_min_sim, short by 0.016; detector 0.24; ocr saw no text; pod unclear (yellow 0.000, aspect 1.0); lever: weak match, add references from this angle
- `202607` box 0: `66` 0.632, `80` 0.575, `3` 0.540; margin_too_small, short by 0.042; detector 0.90; ocr saw `1d` 0.14; pod black (yellow 0.000, aspect 1.6)
- `202649` box 0: `63` 0.682, `21` 0.665, `40` 0.650; margin_too_small, short by 0.084; detector 0.93; ocr saw `c` 0.57, `a` 0.35, `i` 0.33; pod unclear (yellow 0.000, aspect 1.3)
- `202647` box 0: `21` 0.683, `63` 0.671, `39` 0.640; margin_too_small, short by 0.088; detector 0.93; ocr saw `a` 0.26, `ee` 0.11; pod unclear (yellow 0.000, aspect 1.3)
- `202655` box 0: `21` 0.716, `66` 0.662, `40` 0.659; margin_too_small, short by 0.046; detector 0.93; ocr saw `a` 0.59, `od` 0.24; pod black (yellow 0.000, aspect 1.5)
- … 2 more in report.json

## overlapped (4)

- `202633` box 1: `40` 0.382, `21` 0.345, `85` 0.344; overlapped; detector 0.72; ocr saw `k13` 0.57; pod unclear (yellow 0.000, aspect 1.2)
- `202633` box 2: `39` 0.467, `25` 0.458, `49` 0.416; overlapped; detector 0.45; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `202629` box 1: `63` 0.485, `83` 0.423, `67` 0.419; overlapped; detector 0.41; ocr saw `sex` 0.80; pod unclear (yellow 0.000, aspect 1.3)
- `202643` box 1: `83` 0.681, `39` 0.536, `43` 0.498; overlapped; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2)

## no-vehicle (1)

- `202645` burst 2: no vehicle at 0.2: strongest person 0.85 (0.17x0.52 of frame), strongest vehicle motorcycle 0.13 (0.48x0.32 of frame)
