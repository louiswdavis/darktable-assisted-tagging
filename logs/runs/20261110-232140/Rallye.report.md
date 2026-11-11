# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

171 vehicles/images, identified rate 33%

- identified: 57 (33%)
- team-obvious: 0 (0%)
- weak-match: 102 (60%)
- no-references: 0 (0%)
- number-unmatched: 5 (3%)
- conflict: 0 (0%)
- overlapped: 2 (1%)
- already-tagged: 0 (0%)
- no-vehicle: 5 (3%)
- median weak-match: top-1 0.694, margin 0.031

## detector score

- 0.00-0.30: 4 boxes, 0 identified
- 0.30-0.40: 1 boxes, 0 identified
- 0.50-0.70: 10 boxes, 4 identified
- 0.70-1.00: 151 boxes, 53 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one tag prefix only; add under `rules.sponsor_keywords` after checking:
- `castrol` → `Sports|Hill Climb|Rallye Prescott|122`: 3 identified, would hint 6 unidentified
- `perodua` → `Sports|Hill Climb|Rallye Prescott|122`: 2 identified, would hint 3 unidentified
- `motorsport` → `Sports|Hill Climb|Rallye Prescott|104`: 2 identified, would hint 0 unidentified

## bursts (32 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×15, 1s ×14, 2s ×3
frames per burst: 1, 2, 2, 2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 7, 7, 8, 8, 10, 15

closest to the next burst (possible split):
- burst 7: 6 frames, next burst starts 2s later
- burst 22: 2 frames, next burst starts 2s later
- burst 4: 6 frames, next burst starts 3s later
- burst 14: 4 frames, next burst starts 3s later
- burst 17: 4 frames, next burst starts 3s later
- burst 25: 3 frames, next burst starts 3s later
- burst 9: 8 frames, next burst starts 4s later
- burst 11: 4 frames, next burst starts 4s later
- burst 10: 2 frames, next burst starts 8s later
- burst 3: 15 frames, next burst starts 11s later
- burst 20: 8 frames, next burst starts 11s later
- burst 13: 5 frames, next burst starts 12s later
- burst 6: 4 frames, next burst starts 13s later
- burst 16: 4 frames, next burst starts 13s later
- burst 26: 4 frames, next burst starts 14s later
- burst 1: 3 frames, next burst starts 16s later
- burst 28: 7 frames, next burst starts 16s later
- burst 30: 5 frames, next burst starts 17s later
- burst 23: 2 frames, next burst starts 18s later
- burst 19: 5 frames, next burst starts 26s later

largest within-burst gap (possible merge):
- burst 13: 5 frames over 2s, largest gap 2s, 5 with vehicles, 0 without
- burst 20: 8 frames over 2s, largest gap 2s, 8 with vehicles, 0 without
- burst 21: 10 frames over 4s, largest gap 2s, 10 with vehicles, 0 without
- burst 3: 15 frames over 2s, largest gap 1s, 15 with vehicles, 0 without
- burst 7: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 9: 8 frames over 1s, largest gap 1s, 8 with vehicles, 0 without
- burst 12: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 15: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 17: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 18: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 25: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 26: 4 frames over 1s, largest gap 1s, 3 with vehicles, 1 without
- burst 27: 7 frames over 1s, largest gap 1s, 7 with vehicles, 0 without
- burst 28: 7 frames over 1s, largest gap 1s, 7 with vehicles, 0 without
- burst 30: 5 frames over 2s, largest gap 1s, 5 with vehicles, 0 without
- burst 31: 5 frames over 1s, largest gap 1s, 4 with vehicles, 1 without
- burst 32: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 1: 3 frames over 0s, largest gap 0s, 3 with vehicles, 0 without
- burst 2: 6 frames over 0s, largest gap 0s, 5 with vehicles, 1 without
- burst 4: 6 frames over 0s, largest gap 0s, 6 with vehicles, 0 without

## weak-match (102)

- `203757` box 0: `112` 0.375, `113` 0.365, `98` 0.349; below_min_sim, short by 0.225; detector 0.33; ocr saw no text; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `203783` box 0: `98` 0.391, `3` 0.381, `25` 0.380; below_min_sim, short by 0.209; detector 0.22; ocr saw no text; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- `203785` box 0: `115` 0.449, `101` 0.444, `44` 0.401; below_min_sim, short by 0.151; detector 0.73; ocr saw no text; pod black (yellow 0.000, aspect 2.6); lever: weak match, add references from this angle
- `203411` box 0: `30` 0.464, `98` 0.441, `40` 0.432; below_min_sim, short by 0.136; detector 0.88; ocr saw no text; pod yellow (yellow 0.004, aspect 2.1); lever: weak match, add references from this angle
- `203721` box 0: `121` 0.473, `5` 0.463, `74` 0.425; below_min_sim, short by 0.127; detector 0.25; ocr saw no text; pod yellow (yellow 0.001, aspect 2.9); lever: weak match, add references from this angle
- `204023` box 0: `62` 0.485, `3` 0.465, `24` 0.457; below_min_sim, short by 0.115; detector 0.92; ocr saw `MITSUBISHI` 0.91 h0.09, `RALI` 0.78 h0.04, `RALLI ART` 0.57 h0.04; pod black (yellow 0.000, aspect 2.0); lever: weak match, add references from this angle
- `203799` box 0: `98` 0.492, `80` 0.482, `101` 0.454; below_min_sim, short by 0.107; detector 0.92; ocr saw no text; pod black (yellow 0.000, aspect 2.4); lever: weak match, add references from this angle
- `204021` box 0: `30` 0.505, `100` 0.478, `94` 0.465; below_min_sim, short by 0.095; detector 0.92; ocr saw `MITSUBISHI` 0.90 h0.09, `RALI` 0.62 h0.03, `A` 0.39 h0.02; pod black (yellow 0.000, aspect 2.2); lever: weak match, add references from this angle
- `204025` box 0: `5` 0.516, `62` 0.516, `3` 0.511; below_min_sim, short by 0.084; detector 0.93; ocr saw `MITSUBISHI` 0.96 h0.09; pod black (yellow 0.000, aspect 1.9); lever: weak match, add references from this angle
- `204019` box 0: `58` 0.517, `62` 0.511, `3` 0.461; below_min_sim, short by 0.083; detector 0.93; ocr saw `ART` 0.90 h0.03, `AMITSU` 0.84 h0.07, `RALLI` 0.62 h0.04; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `203735` box 0: `94` 0.518, `3` 0.516, `30` 0.510; below_min_sim, short by 0.082; detector 0.92; ocr saw no text; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `203431` box 0: `121` 0.522, `31` 0.505, `86` 0.483; below_min_sim, short by 0.078; detector 0.65; ocr saw no text; pod black (yellow 0.000, aspect 2.2); lever: weak match, add references from this angle
- `203733` box 0: `98` 0.551, `94` 0.547, `30` 0.522; below_min_sim, short by 0.049; detector 0.93; ocr saw no text; pod yellow (yellow 0.002, aspect 1.7); lever: weak match, add references from this angle
- `203355` box 0: `98` 0.564, `104` 0.561, `45` 0.546; below_min_sim, short by 0.036; detector 0.84; ocr saw no text; pod yellow (yellow 0.001, aspect 2.6); lever: weak match, add references from this angle
- `203763` box 0: `31` 0.566, `40` 0.539, `51` 0.504; below_min_sim, short by 0.034; detector 0.81; ocr saw `GE` 0.85 h0.03; pod unclear (yellow 0.000, aspect 1.2); lever: weak match, add references from this angle
- `203787` box 0: `44` 0.570, `70` 0.532, `50` 0.525; below_min_sim, short by 0.030; detector 0.89; read `120`; pod black (yellow 0.000, aspect 2.7); lever: weak match, add references from this angle
- `203353` box 0: `121` 0.572, `104` 0.530, `42` 0.525; below_min_sim, short by 0.028; detector 0.87; ocr saw no text; pod unclear (yellow 0.001, aspect 2.6); lever: weak match, add references from this angle
- `203737` box 0: `62` 0.579, `85` 0.523, `39` 0.516; below_min_sim, short by 0.021; detector 0.65; ocr saw no text; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `203451` box 0: `113` 0.580, `121` 0.565, `31` 0.552; below_min_sim, short by 0.020; detector 0.93; ocr saw no text; pod black (yellow 0.000, aspect 1.4); lever: weak match, add references from this angle
- `203747` box 0: `98` 0.583, `116` 0.528, `101` 0.519; below_min_sim, short by 0.018; detector 0.94; ocr saw no text; pod yellow (yellow 0.001, aspect 1.9); lever: weak match, add references from this angle
- … 82 more in report.json

## number-unmatched (5)

- `203633` box 0: `28` 0.693, `116` 0.603, `115` 0.587; margin_too_small, short by 0.010; detector 0.83; read `14`; pod black (yellow 0.000, aspect 2.7); lever: no entry has number 14
- `203359` box 0: `98` 0.694, `86` 0.620, `94` 0.573; margin_too_small, short by 0.026; detector 0.92; read `796`, `53`; pod unclear (yellow 0.001, aspect 2.5); lever: no entry has number 796
- `203335` box 0: `58` 0.716, `30` 0.628, `103` 0.623; margin_too_small, short by 0.012; detector 0.86; read `28`; pod unclear (yellow 0.000, aspect 1.2); lever: no entry has number 28
- `203343` box 0: `98` 0.725, `104` 0.648, `103` 0.637; margin_too_small, short by 0.023; detector 0.78; read `28`, `796`; pod yellow (yellow 0.001, aspect 1.8); lever: no entry has number 28
- `203341` box 0: `98` 0.738, `103` 0.713, `104` 0.608; margin_too_small, short by 0.075; detector 0.79; read `28`; pod yellow (yellow 0.001, aspect 1.5); lever: no entry has number 28

## overlapped (2)

- `203757` box 1: `40` 0.552, `54` 0.541, `31` 0.516; overlapped; detector 0.82; ocr saw no text; pod black (yellow 0.000, aspect 2.6)
- `203783` box 1: `62` 0.569, `3` 0.554, `98` 0.522; overlapped; detector 0.28; ocr saw no text; pod black (yellow 0.000, aspect 2.3)

## no-vehicle (5)

- `203331` burst 2: no vehicle at 0.2: strongest class 62 0.45 (0.55x0.99 of frame), strongest vehicle car 0.01 (1.07x1.02 of frame)
- `203383` burst 5: no vehicle at 0.2: strongest class 63 0.29 (0.35x0.99 of frame), strongest vehicle car 0.03 (0.35x0.40 of frame)
- `203385` burst 5: no vehicle at 0.2: strongest class 63 0.57 (0.94x1.35 of frame), strongest vehicle car 0.00 (0.75x0.78 of frame)
- `203807` burst 26: no vehicle at 0.2: strongest person 0.00 (0.20x1.23 of frame), strongest vehicle truck 0.00 (0.10x0.94 of frame)
- `203933` burst 31: no vehicle at 0.2: strongest class 13 0.78 (1.01x0.92 of frame), strongest vehicle car 0.00 (1.00x1.03 of frame)
