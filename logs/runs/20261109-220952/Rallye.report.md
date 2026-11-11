# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

7 vehicles/images, identified rate 0%

- identified: 0 (0%)
- team-obvious: 0 (0%)
- weak-match: 6 (86%)
- no-references: 0 (0%)
- number-unmatched: 0 (0%)
- conflict: 0 (0%)
- overlapped: 0 (0%)
- already-tagged: 0 (0%)
- no-vehicle: 1 (14%)
- median weak-match: top-1 0.629, margin 0.041

## detector score

- 0.70-1.00: 6 boxes, 0 identified

## bursts (1 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 1s ×1
frames per burst: 7

closest to the next burst (possible split):

largest within-burst gap (possible merge):
- burst 1: 7 frames over 1s, largest gap 1s, 6 with vehicles, 1 without

## weak-match (6)

- `204015` box 0: `62` 0.602, `30` 0.566, `58` 0.395; margin_too_small, short by 0.063; detector 0.94; ocr saw no text; pod black (yellow 0.000, aspect 1.8)
- `204013` box 0: `62` 0.606, `58` 0.585, `3` 0.542; margin_too_small, short by 0.079; detector 0.92; read `5`; pod black (yellow 0.000, aspect 1.7)
- `204011` box 0: `58` 0.607, `62` 0.604, `3` 0.576; margin_too_small, short by 0.097; detector 0.94; ocr saw no text; pod black (yellow 0.000, aspect 1.7)
- `204007` box 0: `3` 0.651, `58` 0.586, `30` 0.585; margin_too_small, short by 0.035; detector 0.91; ocr saw `pizwec` 0.45; pod black (yellow 0.000, aspect 1.7)
- `204005` box 0: `3` 0.673, `27` 0.583, `58` 0.576; margin_too_small, short by 0.009; detector 0.91; ocr saw `pi2wat` 0.37; pod black (yellow 0.000, aspect 1.8)
- `204009` box 0: `3` 0.689, `58` 0.644, `27` 0.593; margin_too_small, short by 0.056; detector 0.95; ocr saw `tworko` 0.63, `1` 0.19, `ms` 0.17; pod black (yellow 0.000, aspect 1.8)

## no-vehicle (1)

- `204017` burst 1: no vehicle at 0.2: strongest boat 0.48 (0.24x0.54 of frame), strongest vehicle car 0.11 (0.23x0.55 of frame)
