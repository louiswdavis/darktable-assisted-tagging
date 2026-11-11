# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

966 vehicles/images, identified rate 20%

- identified: 190 (20%)
- team-obvious: 0 (0%)
- weak-match: 643 (67%)
- no-references: 0 (0%)
- number-unmatched: 37 (4%)
- conflict: 0 (0%)
- overlapped: 30 (3%)
- already-tagged: 0 (0%)
- no-vehicle: 66 (7%)
- median weak-match: top-1 0.598, margin 0.036

## detector score

- 0.00-0.30: 39 boxes, 1 identified
- 0.30-0.40: 17 boxes, 1 identified
- 0.40-0.50: 20 boxes, 2 identified
- 0.50-0.70: 66 boxes, 10 identified
- 0.70-1.00: 758 boxes, 176 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one tag prefix only; add under `rules.sponsor_keywords` after checking:
- `pyrofil` → `Sports|Hill Climb|Rallye Prescott|30`: 2 identified, would hint 1 unidentified
- `kitchen` → `Sports|Hill Climb|Rallye Prescott|44`: 2 identified, would hint 0 unidentified

## bursts (170 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×66, 1s ×92, 2s ×12
frames per burst: 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 10, 10, 10, 11, 12, 13, 14, 15, 23

closest to the next burst (possible split):
- burst 6: 6 frames, next burst starts 2s later
- burst 19: 9 frames, next burst starts 2s later
- burst 26: 5 frames, next burst starts 2s later
- burst 78: 6 frames, next burst starts 2s later
- burst 92: 13 frames, next burst starts 2s later
- burst 97: 7 frames, next burst starts 2s later
- burst 99: 6 frames, next burst starts 2s later
- burst 117: 2 frames, next burst starts 2s later
- burst 126: 3 frames, next burst starts 2s later
- burst 51: 4 frames, next burst starts 3s later
- burst 57: 6 frames, next burst starts 3s later
- burst 60: 2 frames, next burst starts 3s later
- burst 69: 10 frames, next burst starts 3s later
- burst 75: 6 frames, next burst starts 3s later
- burst 86: 4 frames, next burst starts 3s later
- burst 102: 4 frames, next burst starts 3s later
- burst 104: 5 frames, next burst starts 3s later
- burst 105: 3 frames, next burst starts 3s later
- burst 112: 4 frames, next burst starts 3s later
- burst 120: 3 frames, next burst starts 3s later

largest within-burst gap (possible merge):
- burst 16: 8 frames over 3s, largest gap 2s, 8 with vehicles, 0 without
- burst 36: 8 frames over 3s, largest gap 2s, 7 with vehicles, 1 without
- burst 46: 9 frames over 2s, largest gap 2s, 8 with vehicles, 1 without
- burst 63: 9 frames over 4s, largest gap 2s, 9 with vehicles, 0 without
- burst 66: 6 frames over 2s, largest gap 2s, 3 with vehicles, 3 without
- burst 98: 9 frames over 4s, largest gap 2s, 6 with vehicles, 3 without
- burst 99: 6 frames over 3s, largest gap 2s, 6 with vehicles, 0 without
- burst 101: 5 frames over 2s, largest gap 2s, 5 with vehicles, 0 without
- burst 108: 5 frames over 3s, largest gap 2s, 5 with vehicles, 0 without
- burst 115: 8 frames over 2s, largest gap 2s, 8 with vehicles, 0 without
- burst 116: 10 frames over 4s, largest gap 2s, 10 with vehicles, 0 without
- burst 147: 4 frames over 2s, largest gap 2s, 4 with vehicles, 0 without
- burst 1: 8 frames over 1s, largest gap 1s, 7 with vehicles, 1 without
- burst 2: 5 frames over 1s, largest gap 1s, 3 with vehicles, 2 without
- burst 4: 6 frames over 1s, largest gap 1s, 5 with vehicles, 1 without
- burst 6: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 7: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 9: 9 frames over 1s, largest gap 1s, 6 with vehicles, 3 without
- burst 10: 6 frames over 1s, largest gap 1s, 6 with vehicles, 0 without
- burst 12: 7 frames over 1s, largest gap 1s, 6 with vehicles, 1 without

## weak-match (643)

- `203149` box 0: `76` 0.304, `78` 0.279, `83` 0.273; below_min_sim, short by 0.296; detector 0.21; ocr saw no text; pod unclear (yellow 0.000, aspect 0.7); lever: weak match, add references from this angle
- `202595` box 0: `43` 0.309, `39` 0.305, `83` 0.297; below_min_sim, short by 0.291; detector 0.15; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1); lever: weak match, add references from this angle
- `204375` box 0: `56` 0.344, `40` 0.308, `30` 0.303; below_min_sim, short by 0.256; detector 0.90; ocr saw `ciatic` 0.88; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `203657` box 0: `26` 0.346, `58` 0.340, `82` 0.331; below_min_sim, short by 0.254; detector 0.88; read `445`; pod black (yellow 0.000, aspect 2.7); lever: weak match, add references from this angle
- `203799` box 0: `50` 0.351, `22` 0.346, `56` 0.331; below_min_sim, short by 0.249; detector 0.92; ocr saw no text; pod black (yellow 0.000, aspect 2.4); lever: weak match, add references from this angle
- `202589` box 0: `43` 0.353, `47` 0.337, `40` 0.328; below_min_sim, short by 0.247; detector 0.38; ocr saw `tim` 0.99, `thr` 0.24; pod unclear (yellow 0.000, aspect 1.0); lever: weak match, add references from this angle
- `204373` box 0: `46` 0.359, `39` 0.359, `3` 0.354; below_min_sim, short by 0.241; detector 0.89; ocr saw `d6` 0.59, `ciatic` 0.58; pod black (yellow 0.000, aspect 1.7); lever: weak match, add references from this angle
- `203683` box 1: `35` 0.362, `83` 0.340, `47` 0.337; below_min_sim, short by 0.238; detector 0.24; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); lever: weak match, add references from this angle
- `202591` box 0: `43` 0.362, `40` 0.337, `47` 0.312; below_min_sim, short by 0.238; detector 0.26; ocr saw `tim` 0.99, `for` 0.51; pod unclear (yellow 0.000, aspect 0.9); lever: weak match, add references from this angle
- `204209` box 0: `79` 0.366, `42` 0.347, `30` 0.307; below_min_sim, short by 0.234; detector 0.74; ocr saw `it` 0.98; pod black (yellow 0.000, aspect 1.6); lever: weak match, add references from this angle
- `202599` box 0: `83` 0.367, `35` 0.353, `39` 0.336; below_min_sim, short by 0.233; detector 0.21; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2); lever: weak match, add references from this angle
- `203147` box 0: `78` 0.371, `76` 0.351, `83` 0.283; below_min_sim, short by 0.229; detector 0.67; ocr saw no text; pod yellow (yellow 0.004, aspect 1.4); lever: weak match, add references from this angle
- `203143` box 0: `47` 0.373, `39` 0.335, `26` 0.328; below_min_sim, short by 0.227; detector 0.73; ocr saw no text; pod unclear (yellow 0.000, aspect 1.2); lever: weak match, add references from this angle
- `203141` box 0: `26` 0.377, `39` 0.371, `40` 0.370; below_min_sim, short by 0.223; detector 0.84; ocr saw no text; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- `202651` box 1: `39` 0.384, `35` 0.326, `83` 0.269; below_min_sim, short by 0.216; detector 0.24; ocr saw no text; pod unclear (yellow 0.000, aspect 1.0); lever: weak match, add references from this angle
- `203001` box 1: `83` 0.384, `35` 0.353, `43` 0.353; below_min_sim, short by 0.216; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); lever: weak match, add references from this angle
- `203897` box 0: `47` 0.387, `86` 0.377, `94` 0.370; below_min_sim, short by 0.213; detector 0.90; ocr saw `guest` 0.22, `a` 0.20, `cnenananim` 0.19; pod unclear (yellow 0.000, aspect 1.1); lever: weak match, add references from this angle
- `204379` box 0: `30` 0.389, `43` 0.376, `56` 0.354; below_min_sim, short by 0.211; detector 0.87; ocr saw `ci4tic` 0.52; pod black (yellow 0.000, aspect 2.0); lever: weak match, add references from this angle
- `203721` box 0: `35` 0.391, `55` 0.354, `47` 0.324; below_min_sim, short by 0.209; detector 0.25; ocr saw no text; pod yellow (yellow 0.001, aspect 2.9); lever: weak match, add references from this angle
- `203201` box 0: `30` 0.393, `58` 0.372, `79` 0.354; below_min_sim, short by 0.207; detector 0.93; ocr saw no text; pod black (yellow 0.000, aspect 2.3); lever: weak match, add references from this angle
- … 623 more in report.json

## number-unmatched (37)

- `202737` box 0: `39` 0.492, `63` 0.445, `60` 0.377; below_min_sim, short by 0.108; detector 0.90; read `768`; pod black (yellow 0.000, aspect 2.8); lever: no entry has number 768
- `202921` box 0: `54` 0.504, `60` 0.466, `86` 0.458; below_min_sim, short by 0.096; detector 0.93; read `193`; pod black (yellow 0.000, aspect 2.5); lever: no entry has number 193
- `202735` box 0: `60` 0.508, `63` 0.479, `80` 0.460; below_min_sim, short by 0.092; detector 0.89; read `768`; pod yellow (yellow 0.002, aspect 2.6); lever: no entry has number 768
- `203281` box 0: `58` 0.520, `22` 0.506, `55` 0.472; below_min_sim, short by 0.080; detector 0.86; read `103`; pod black (yellow 0.000, aspect 1.8); lever: no entry has number 103
- `203759` box 0: `54` 0.531, `40` 0.508, `86` 0.424; below_min_sim, short by 0.069; detector 0.81; read `107`; pod black (yellow 0.000, aspect 2.3); lever: no entry has number 107
- `203317` box 0: `45` 0.541, `98` 0.470, `64` 0.467; below_min_sim, short by 0.059; detector 0.68; read `104`; pod black (yellow 0.000, aspect 2.5); lever: no entry has number 104
- `203665` box 0: `44` 0.555, `50` 0.402, `64` 0.367; below_min_sim, short by 0.044; detector 0.72; read `115`; pod black (yellow 0.000, aspect 2.6); lever: no entry has number 115
- `203655` box 0: `44` 0.571, `79` 0.468, `22` 0.409; below_min_sim, short by 0.029; detector 0.92; read `115`; pod black (yellow 0.000, aspect 2.5); lever: no entry has number 115
- `203319` box 0: `45` 0.578, `42` 0.425, `44` 0.383; below_min_sim, short by 0.022; detector 0.80; read `104`; pod black (yellow 0.000, aspect 2.7); lever: no entry has number 104
- `202733` box 0: `80` 0.587, `60` 0.512, `63` 0.463; below_min_sim, short by 0.013; detector 0.93; read `768`; pod yellow (yellow 0.002, aspect 2.5); lever: no entry has number 768
- `203543` box 0: `40` 0.588, `30` 0.550, `55` 0.511; below_min_sim, short by 0.012; detector 0.74; read `112`; pod black (yellow 0.000, aspect 2.0); lever: no entry has number 112
- `203787` box 0: `44` 0.589, `50` 0.557, `26` 0.455; below_min_sim, short by 0.011; detector 0.89; read `120`; pod black (yellow 0.000, aspect 2.7); lever: no entry has number 120
- `203669` box 0: `44` 0.591, `50` 0.492, `98` 0.381; below_min_sim, short by 0.009; detector 0.84; read `115`; pod black (yellow 0.000, aspect 2.6); lever: no entry has number 115
- `202471` box 0: `80` 0.601, `60` 0.558, `26` 0.502; margin_too_small, short by 0.058; detector 0.91; read `760`; pod black (yellow 0.000, aspect 2.1); lever: no entry has number 760
- `202469` box 0: `80` 0.605, `66` 0.540, `26` 0.539; margin_too_small, short by 0.036; detector 0.92; read `760`; pod black (yellow 0.000, aspect 2.0); lever: no entry has number 760
- `203879` box 0: `62` 0.607, `8` 0.559, `94` 0.523; margin_too_small, short by 0.051; detector 0.91; read `121`; pod yellow (yellow 0.004, aspect 2.2); lever: no entry has number 121
- `203545` box 0: `55` 0.616, `35` 0.605, `22` 0.601; margin_too_small, short by 0.089; detector 0.46; read `112`; pod black (yellow 0.000, aspect 1.6); lever: no entry has number 112
- `202473` box 0: `80` 0.622, `60` 0.570, `26` 0.540; margin_too_small, short by 0.048; detector 0.92; read `760`; pod black (yellow 0.000, aspect 2.3); lever: no entry has number 760
- `202475` box 0: `80` 0.631, `60` 0.601, `66` 0.514; margin_too_small, short by 0.070; detector 0.90; read `760`; pod black (yellow 0.000, aspect 2.3); lever: no entry has number 760
- `203273` box 0: `98` 0.649, `44` 0.609, `22` 0.534; margin_too_small, short by 0.061; detector 0.81; read `103`; pod black (yellow 0.000, aspect 2.0); lever: no entry has number 103
- … 17 more in report.json

## overlapped (30)

- `203895` box 1: `39` 0.310, `83` 0.249, `47` 0.238; overlapped; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `203691` box 1: `55` 0.389, `44` 0.334, `22` 0.278; overlapped; detector 0.30; ocr saw no text; pod unclear (yellow 0.000, aspect 0.5)
- `202633` box 1: `40` 0.389, `21` 0.358, `85` 0.352; overlapped; detector 0.72; ocr saw `k13` 0.57; pod unclear (yellow 0.000, aspect 1.2)
- `204359` box 1: `62` 0.404, `51` 0.380, `85` 0.347; overlapped; detector 0.80; ocr saw no text; pod unclear (yellow 0.000, aspect 0.5)
- `204211` box 1: `22` 0.442, `76` 0.353, `98` 0.301; overlapped; detector 0.56; ocr saw `upers` 0.56; pod unclear (yellow 0.000, aspect 0.8)
- `203153` box 1: `40` 0.442, `22` 0.417, `55` 0.361; overlapped; detector 0.38; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `202469` box 1: `60` 0.454, `39` 0.325, `76` 0.295; overlapped; detector 0.47; ocr saw no text; pod black (yellow 0.000, aspect 2.2)
- `202633` box 2: `39` 0.466, `25` 0.444, `49` 0.400; overlapped; detector 0.45; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `203039` box 1: `26` 0.468, `63` 0.461, `60` 0.423; overlapped; detector 0.89; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- `202629` box 1: `63` 0.479, `39` 0.410, `25` 0.382; overlapped; detector 0.41; ocr saw `sex` 0.80; pod unclear (yellow 0.000, aspect 1.3)
- `203939` box 1: `63` 0.493, `26` 0.462, `58` 0.422; overlapped; detector 0.74; ocr saw `castral` 0.63; pod black (yellow 0.000, aspect 1.9)
- `203037` box 1: `26` 0.505, `63` 0.363, `62` 0.356; overlapped; detector 0.90; ocr saw `lans` 0.18; pod black (yellow 0.000, aspect 1.6)
- `202935` box 1: `86` 0.507, `83` 0.500, `94` 0.499; overlapped; detector 0.22; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1)
- `202809` box 0: `82` 0.515, `60` 0.461, `63` 0.441; overlapped; detector 0.27; read `39`; pod black (yellow 0.000, aspect 2.3)
- `203051` box 1: `83` 0.515, `47` 0.466, `82` 0.456; overlapped; detector 0.26; ocr saw no text; pod black (yellow 0.000, aspect 1.5)
- `203783` box 1: `22` 0.523, `39` 0.515, `35` 0.459; overlapped; detector 0.28; ocr saw no text; pod black (yellow 0.000, aspect 2.3)
- `203757` box 1: `40` 0.527, `54` 0.509, `63` 0.410; overlapped; detector 0.82; ocr saw no text; pod black (yellow 0.000, aspect 2.6)
- `202743` box 1: `62` 0.528, `66` 0.508, `30` 0.455; overlapped; detector 0.94; ocr saw `a` 0.60; pod black (yellow 0.000, aspect 1.9)
- `202509` box 2: `39` 0.528, `60` 0.522, `82` 0.393; overlapped; detector 0.20; ocr saw no text; pod unclear (yellow 0.000, aspect 1.1)
- `203937` box 1: `63` 0.535, `83` 0.513, `39` 0.445; overlapped; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 1.7)
- … 10 more in report.json

## no-vehicle (66)

- `202325` burst 1: no vehicle at 0.2: strongest person 0.33 (0.06x0.05 of frame), strongest vehicle truck 0.02 (0.10x0.15 of frame)
- `202347` burst 2: no vehicle at 0.2: strongest class 13 0.17 (0.14x0.06 of frame), strongest vehicle car 0.00 (0.02x0.02 of frame)
- `202349` burst 2: no vehicle at 0.2: strongest class 13 0.15 (0.14x0.06 of frame), strongest vehicle car 0.01 (0.02x0.02 of frame)
- `202371` burst 4: no vehicle at 0.2: strongest person 0.43 (0.25x0.98 of frame), strongest vehicle car 0.17 (0.17x0.21 of frame)
- `202479` burst 9: no vehicle at 0.2: strongest car 0.69 (0.10x0.04 of frame), strongest vehicle car 0.69 (0.10x0.04 of frame)
- `202481` burst 9: no vehicle at 0.2: strongest car 0.65 (0.10x0.04 of frame), strongest vehicle car 0.65 (0.10x0.04 of frame)
- `202483` burst 9: no vehicle at 0.2: strongest car 0.85 (0.10x0.05 of frame), strongest vehicle car 0.85 (0.10x0.05 of frame)
- `202531` burst 12: no vehicle at 0.2: strongest class 13 0.64 (1.00x0.40 of frame), strongest vehicle car 0.21 (0.04x0.06 of frame)
- `202593` burst 18: no vehicle at 0.2: strongest car 0.48 (0.10x0.05 of frame), strongest vehicle car 0.48 (0.10x0.05 of frame)
- `202645` burst 20: no vehicle at 0.2: strongest person 0.85 (0.17x0.52 of frame), strongest vehicle motorcycle 0.13 (0.48x0.32 of frame)
- `202791` burst 31: no vehicle at 0.2: strongest train 0.23 (1.00x0.55 of frame), strongest vehicle car 0.15 (1.00x0.58 of frame)
- `202805` burst 32: no vehicle at 0.2: strongest person 0.31 (0.23x0.28 of frame), strongest vehicle car 0.04 (0.22x0.19 of frame)
- `202911` burst 36: no vehicle at 0.2: strongest class 62 0.21 (0.99x0.95 of frame), strongest vehicle car 0.05 (1.00x0.76 of frame)
- `202995` burst 43: no vehicle at 0.2: strongest car 0.13 (0.24x0.28 of frame), strongest vehicle car 0.13 (0.24x0.28 of frame)
- `202997` burst 43: no vehicle at 0.2: strongest class 13 0.17 (0.98x1.01 of frame), strongest vehicle car 0.02 (0.95x1.06 of frame)
- `202999` burst 43: no vehicle at 0.2: strongest class 62 0.17 (0.54x0.99 of frame), strongest vehicle car 0.01 (1.05x1.01 of frame)
- `203041` burst 46: no vehicle at 0.2: strongest class 13 0.30 (1.00x1.00 of frame), strongest vehicle car 0.14 (0.47x0.33 of frame)
- `203049` burst 47: no vehicle at 0.2: strongest class 28 0.17 (0.34x0.26 of frame), strongest vehicle car 0.03 (0.10x0.05 of frame)
- `203075` burst 49: no vehicle at 0.2: strongest person 0.91 (0.18x0.42 of frame), strongest vehicle motorcycle 0.02 (0.04x0.07 of frame)
- `203077` burst 49: no vehicle at 0.2: strongest person 0.92 (0.18x0.43 of frame), strongest vehicle truck 0.01 (0.14x0.76 of frame)
- … 46 more in report.json
