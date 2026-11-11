# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

8 vehicles/images, identified rate 12%

- identified: 1 (12%)
- team-obvious: 0 (0%)
- weak-match: 7 (88%)
- no-references: 0 (0%)
- number-unmatched: 0 (0%)
- conflict: 0 (0%)
- overlapped: 0 (0%)
- already-tagged: 0 (0%)
- no-vehicle: 0 (0%)
- median weak-match: top-1 0.520, margin 0.050

## detector score

- 0.50-0.70: 2 boxes, 0 identified
- 0.70-1.00: 6 boxes, 1 identified

## bursts (2 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×1, 1s ×1
frames per burst: 2, 6

closest to the next burst (possible split):
- burst 1: 2 frames, next burst starts 2s later

largest within-burst gap (possible merge):
- burst 1: 2 frames over 1s, largest gap 1s, 2 with vehicles, 0 without
- burst 2: 6 frames over 0s, largest gap 0s, 6 with vehicles, 0 without

## weak-match (7)

- `198461` box 0: `56` 0.415, `26` 0.389, `67` 0.387; below_min_sim, short by 0.185; detector 0.70; read `101`; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `198463` box 0: `26` 0.467, `67` 0.463, `70` 0.416; below_min_sim, short by 0.133; detector 0.81; read `101`; pod black (yellow 0.000, aspect 2.1); lever: weak match, add references from this angle
- `198457` box 0: `26` 0.515, `50` 0.465, `27` 0.429; below_min_sim, short by 0.085; detector 0.75; read `101`; pod black (yellow 0.000, aspect 2.0); lever: weak match, add references from this angle
- `198459` box 0: `26` 0.520, `50` 0.463, `67` 0.440; below_min_sim, short by 0.080; detector 0.69; read `101`; pod black (yellow 0.000, aspect 2.1); lever: weak match, add references from this angle
- `198455` box 0: `27` 0.547, `35` 0.519, `74` 0.508; below_min_sim, short by 0.053; detector 0.67; read `101`; pod black (yellow 0.000, aspect 2.0); lever: weak match, add references from this angle
- `198449` box 0: `26` 0.592, `54` 0.532, `63` 0.469; below_min_sim, short by 0.008; detector 0.90; read `6`; pod black (yellow 0.000, aspect 2.5); lever: weak match, add references from this angle
- `198453` box 0: `27` 0.597, `26` 0.531, `35` 0.528; below_min_sim, short by 0.003; detector 0.87; read `101`; pod black (yellow 0.000, aspect 2.1); lever: weak match, add references from this angle
