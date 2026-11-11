# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

51 vehicles/images, identified rate 14%

- identified: 7 (14%)
- team-obvious: 0 (0%)
- weak-match: 37 (73%)
- no-references: 0 (0%)
- number-unmatched: 2 (4%)
- conflict: 0 (0%)
- overlapped: 2 (4%)
- already-tagged: 0 (0%)
- no-vehicle: 3 (6%)
- median weak-match: top-1 0.698, margin 0.026

## detector score

- 0.00-0.30: 2 boxes, 0 identified
- 0.30-0.40: 2 boxes, 0 identified
- 0.40-0.50: 1 boxes, 0 identified
- 0.50-0.70: 3 boxes, 0 identified
- 0.70-1.00: 40 boxes, 7 identified

## bursts (12 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×8, 1s ×3, 2s ×1
frames per burst: 1, 1, 2, 2, 2, 3, 3, 4, 5, 6, 8, 11

closest to the next burst (possible split):
- burst 8: 1 frames, next burst starts 10s later
- burst 6: 2 frames, next burst starts 12s later
- burst 4: 3 frames, next burst starts 18s later
- burst 1: 4 frames, next burst starts 19s later
- burst 11: 8 frames, next burst starts 28s later
- burst 3: 2 frames, next burst starts 36s later
- burst 7: 1 frames, next burst starts 36s later
- burst 2: 11 frames, next burst starts 39s later
- burst 9: 3 frames, next burst starts 44s later
- burst 5: 5 frames, next burst starts 64s later
- burst 10: 6 frames, next burst starts 117s later

largest within-burst gap (possible merge):
- burst 11: 8 frames over 3s, largest gap 2s, 7 with vehicles, 1 without
- burst 1: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 2: 11 frames over 1s, largest gap 1s, 11 with vehicles, 0 without
- burst 5: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 3: 2 frames over 0s, largest gap 0s, 2 with vehicles, 0 without
- burst 4: 3 frames over 0s, largest gap 0s, 3 with vehicles, 0 without
- burst 6: 2 frames over 0s, largest gap 0s, 2 with vehicles, 0 without
- burst 7: 1 frames over 0s, largest gap 0s, 0 with vehicles, 1 without
- burst 8: 1 frames over 0s, largest gap 0s, 0 with vehicles, 1 without
- burst 9: 3 frames over 0s, largest gap 0s, 3 with vehicles, 0 without
- burst 10: 6 frames over 0s, largest gap 0s, 6 with vehicles, 0 without
- burst 12: 2 frames over 0s, largest gap 0s, 2 with vehicles, 0 without

## weak-match (37)

- `202743` box 0: `98` 0.403, `11` 0.394, `25` 0.384; below_min_sim, short by 0.197; detector 0.33; ocr saw no text; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `202841` box 0: `85` 0.477, `83` 0.448, `94` 0.427; below_min_sim, short by 0.123; detector 0.85; ocr saw no text; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `202897` box 1: `115` 0.493, `74` 0.452, `113` 0.438; below_min_sim, short by 0.107; detector 0.40; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8); lever: weak match, add references from this angle
- `202807` box 0: `85` 0.509, `3` 0.502, `24` 0.471; below_min_sim, short by 0.091; detector 0.93; ocr saw `NN53RVL` 0.74 h0.10; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `202915` box 0: `39` 0.537, `46` 0.530, `21` 0.494; below_min_sim, short by 0.063; detector 0.93; ocr saw `Sr` 0.33 h0.08; pod unclear (yellow 0.000, aspect 1.4); lever: weak match, add references from this angle
- `202913` box 0: `21` 0.551, `39` 0.545, `46` 0.529; below_min_sim, short by 0.049; detector 0.95; ocr saw `U` 0.84 h0.13; pod black (yellow 0.000, aspect 1.4); lever: weak match, add references from this angle
- `202849` box 0: `85` 0.585, `80` 0.578, `82` 0.573; below_min_sim, short by 0.015; detector 0.87; ocr saw no text; pod black (yellow 0.000, aspect 1.9); lever: weak match, add references from this angle
- `202717` box 0: `76` 0.587, `50` 0.450, `55` 0.443; below_min_sim, short by 0.013; detector 0.91; ocr saw no text; pod black (yellow 0.000, aspect 2.4); lever: weak match, add references from this angle
- `202747` box 0: `80` 0.615, `3` 0.535, `62` 0.521; margin_too_small, short by 0.020; detector 0.41; ocr saw no text; pod black (yellow 0.000, aspect 1.5)
- `202901` box 0: `98` 0.618, `121` 0.611, `94` 0.551; margin_too_small, short by 0.094; detector 0.76; ocr saw no text; pod black (yellow 0.000, aspect 1.5)
- `202843` box 0: `3` 0.625, `94` 0.606, `58` 0.581; margin_too_small, short by 0.080; detector 0.80; ocr saw `ILI` 0.35 h0.04; pod black (yellow 0.000, aspect 1.6)
- `202845` box 0: `94` 0.649, `3` 0.611, `5` 0.601; margin_too_small, short by 0.061; detector 0.94; ocr saw no text; pod black (yellow 0.000, aspect 1.5)
- `202909` box 0: `121` 0.653, `98` 0.650, `79` 0.604; margin_too_small, short by 0.097; detector 0.74; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2)
- `202899` box 0: `121` 0.667, `98` 0.595, `58` 0.587; margin_too_small, short by 0.028; detector 0.74; ocr saw no text; pod black (yellow 0.000, aspect 1.4)
- `202907` box 0: `98` 0.669, `121` 0.666, `58` 0.624; margin_too_small, short by 0.097; detector 0.66; read `2`; pod unclear (yellow 0.000, aspect 1.2)
- `202811` box 0: `85` 0.676, `80` 0.656, `82` 0.653; margin_too_small, short by 0.080; detector 0.82; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- `202905` box 0: `121` 0.682, `98` 0.639, `58` 0.604; margin_too_small, short by 0.057; detector 0.62; ocr saw no text; pod unclear (yellow 0.000, aspect 1.4)
- `202897` box 0: `121` 0.696, `58` 0.627, `98` 0.595; margin_too_small, short by 0.031; detector 0.84; ocr saw no text; pod unclear (yellow 0.000, aspect 1.4)
- `202739` box 0: `80` 0.698, `21` 0.687, `66` 0.614; margin_too_small, short by 0.089; detector 0.95; ocr saw `'68` 0.55 h0.21, `-` 0.22 h0.07; pod black (yellow 0.000, aspect 1.9)
- `202779` box 0: `82` 0.700, `85` 0.616, `60` 0.601; margin_too_small, short by 0.016; detector 0.72; ocr saw no text; pod black (yellow 0.000, aspect 3.1)
- … 17 more in report.json

## number-unmatched (2)

- `202737` box 0: `68` 0.583, `39` 0.499, `63` 0.449; below_min_sim, short by 0.017; detector 0.90; read `768`; pod black (yellow 0.000, aspect 2.8); lever: no entry has number 768
- `202733` box 0: `68` 0.672, `80` 0.609, `75` 0.565; margin_too_small, short by 0.036; detector 0.93; read `768`; pod yellow (yellow 0.002, aspect 2.5); lever: no entry has number 768

## overlapped (2)

- `202743` box 1: `80` 0.677, `3` 0.611, `5` 0.560; overlapped; detector 0.94; ocr saw `SS` 0.55 h0.33; pod black (yellow 0.000, aspect 1.9)
- `202747` box 1: `80` 0.713, `3` 0.577, `83` 0.568; overlapped; detector 0.90; ocr saw no text; pod black (yellow 0.000, aspect 2.2)

## no-vehicle (3)

- `202791` burst 7: no vehicle at 0.2: strongest train 0.23 (1.00x0.55 of frame), strongest vehicle car 0.15 (1.00x0.58 of frame)
- `202805` burst 8: no vehicle at 0.2: strongest person 0.31 (0.23x0.28 of frame), strongest vehicle car 0.04 (0.22x0.19 of frame)
- `202911` burst 11: no vehicle at 0.2: strongest class 62 0.21 (0.99x0.95 of frame), strongest vehicle car 0.05 (1.00x0.76 of frame)
