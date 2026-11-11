# Assisted Tagging report: `Rallye`

thresholds: min_sim 0.6, min_margin 0.1, reference_margin 0.1

## Summary

1516 vehicles/images, identified rate 22%

- identified: 330 (22%)
- team-obvious: 0 (0%)
- weak-match: 814 (54%)
- no-references: 0 (0%)
- number-unmatched: 22 (1%)
- conflict: 0 (0%)
- overlapped: 292 (19%)
- already-tagged: 0 (0%)
- no-vehicle: 58 (4%)
- median weak-match: top-1 0.527, margin 0.036

## detector score

- 0.00-0.30: 104 boxes, 3 identified
- 0.30-0.40: 85 boxes, 4 identified
- 0.40-0.50: 82 boxes, 4 identified
- 0.50-0.70: 157 boxes, 19 identified
- 0.70-1.00: 1030 boxes, 300 identified

## sponsor keyword suggestions

words OCR read on identified boxes of one tag prefix only; add under `rules.sponsor_keywords` after checking:
- `skoda` → `Sports|Hill Climb|Rallye Prescott|85`: 7 identified, would hint 27 unidentified
- `copper` → `Sports|Hill Climb|Rallye Prescott|40`: 3 identified, would hint 1 unidentified
- `maynard` → `Sports|Hill Climb|Rallye Prescott|22`: 10 identified, would hint 0 unidentified
- `ambulance` → `Sports|Hill Climb|Rallye Prescott|39`: 3 identified, would hint 0 unidentified
- `horse` → `Sports|Hill Climb|Rallye Prescott|40`: 3 identified, would hint 0 unidentified
- `abland` → `Sports|Hill Climb|Rallye Prescott|40`: 2 identified, would hint 0 unidentified
- `audisport` → `Sports|Hill Climb|Rallye Prescott|94`: 2 identified, would hint 0 unidentified
- `bilstein` → `Sports|Hill Climb|Rallye Prescott|94`: 2 identified, would hint 0 unidentified
- `ceramx` → `Sports|Hill Climb|Rallye Prescott|98`: 2 identified, would hint 0 unidentified
- `cooper` → `Sports|Hill Climb|Rallye Prescott|27`: 2 identified, would hint 0 unidentified
- `eans` → `Sports|Hill Climb|Rallye Prescott|37`: 2 identified, would hint 0 unidentified
- `ebenton` → `Sports|Hill Climb|Rallye Prescott|98`: 2 identified, would hint 0 unidentified
- `esel` → `Sports|Hill Climb|Rallye Prescott|37`: 2 identified, would hint 0 unidentified
- `llington` → `Sports|Hill Climb|Rallye Prescott|98`: 2 identified, would hint 0 unidentified
- `lucas` → `Sports|Hill Climb|Rallye Prescott|35`: 2 identified, would hint 0 unidentified

## bursts (218 timed, 0 without capture times)

within-burst largest gap (s) → bursts: 0s ×125, 1s ×80, 2s ×12, 541s ×1
frames per burst: 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 8, 8, 9, 9, 9, 9, 10, 10, 10, 10, 10, 10, 11, 11, 11, 12, 13, 13, 13, 13, 14, 15, 18, 22, 216

closest to the next burst (possible split):
- burst 86: 216 frames, next burst starts -1191s later
- burst 6: 5 frames, next burst starts 2s later
- burst 68: 5 frames, next burst starts 2s later
- burst 70: 2 frames, next burst starts 2s later
- burst 75: 2 frames, next burst starts 2s later
- burst 78: 2 frames, next burst starts 2s later
- burst 91: 1 frames, next burst starts 2s later
- burst 114: 5 frames, next burst starts 2s later
- burst 179: 2 frames, next burst starts 2s later
- burst 184: 2 frames, next burst starts 2s later
- burst 189: 1 frames, next burst starts 2s later
- burst 197: 1 frames, next burst starts 2s later
- burst 201: 2 frames, next burst starts 2s later
- burst 3: 3 frames, next burst starts 3s later
- burst 5: 5 frames, next burst starts 3s later
- burst 10: 3 frames, next burst starts 3s later
- burst 12: 3 frames, next burst starts 3s later
- burst 22: 10 frames, next burst starts 3s later
- burst 35: 5 frames, next burst starts 3s later
- burst 45: 4 frames, next burst starts 3s later

largest within-burst gap (possible merge):
- burst 86: 216 frames over 1711s, largest gap 541s, 216 with vehicles, 0 without
- burst 6: 5 frames over 2s, largest gap 2s, 4 with vehicles, 1 without
- burst 37: 6 frames over 2s, largest gap 2s, 6 with vehicles, 0 without
- burst 49: 10 frames over 2s, largest gap 2s, 10 with vehicles, 0 without
- burst 52: 10 frames over 2s, largest gap 2s, 10 with vehicles, 0 without
- burst 67: 13 frames over 5s, largest gap 2s, 10 with vehicles, 3 without
- burst 72: 11 frames over 2s, largest gap 2s, 8 with vehicles, 3 without
- burst 73: 15 frames over 6s, largest gap 2s, 13 with vehicles, 2 without
- burst 96: 22 frames over 7s, largest gap 2s, 20 with vehicles, 2 without
- burst 134: 5 frames over 3s, largest gap 2s, 5 with vehicles, 0 without
- burst 135: 2 frames over 2s, largest gap 2s, 2 with vehicles, 0 without
- burst 171: 4 frames over 2s, largest gap 2s, 3 with vehicles, 1 without
- burst 173: 3 frames over 2s, largest gap 2s, 3 with vehicles, 0 without
- burst 2: 4 frames over 1s, largest gap 1s, 4 with vehicles, 0 without
- burst 3: 3 frames over 1s, largest gap 1s, 3 with vehicles, 0 without
- burst 4: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 5: 5 frames over 1s, largest gap 1s, 5 with vehicles, 0 without
- burst 14: 6 frames over 1s, largest gap 1s, 5 with vehicles, 1 without
- burst 15: 3 frames over 1s, largest gap 1s, 1 with vehicles, 2 without
- burst 16: 6 frames over 1s, largest gap 1s, 5 with vehicles, 1 without

## weak-match (814)

- `198339` box 1: `39` 0.259, `85` 0.219, `35` 0.212; below_min_sim, short by 0.341; detector 0.70; ocr saw no text; pod unclear (yellow 0.000, aspect 0.3); lever: weak match, add references from this angle
- `199489` box 2: `85` 0.276, `76` 0.275, `50` 0.269; below_min_sim, short by 0.324; detector 0.53; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8); lever: weak match, add references from this angle
- `205335` box 0: `39` 0.286, `76` 0.240, `47` 0.228; below_min_sim, short by 0.314; detector 0.23; ocr saw no text; pod black (yellow 0.000, aspect 11.9); lever: weak match, add references from this angle
- `199487` box 2: `55` 0.294, `39` 0.288, `47` 0.280; below_min_sim, short by 0.306; detector 0.24; ocr saw no text; pod yellow (yellow 0.002, aspect 0.7); lever: weak match, add references from this angle
- `199529` box 2: `85` 0.304, `39` 0.289, `83` 0.270; below_min_sim, short by 0.296; detector 0.33; ocr saw no text; pod black (yellow 0.000, aspect 2.7); lever: weak match, add references from this angle
- `199709` box 0: `83` 0.308, `39` 0.302, `60` 0.284; below_min_sim, short by 0.292; detector 0.20; ocr saw `castrol` 1.00; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- `205457` box 1: `39` 0.308, `83` 0.278, `76` 0.261; below_min_sim, short by 0.291; detector 0.26; ocr saw no text; pod unclear (yellow 0.000, aspect 0.8); lever: weak match, add references from this angle
- `199541` box 2: `39` 0.309, `35` 0.284, `87` 0.216; below_min_sim, short by 0.291; detector 0.43; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3); lever: weak match, add references from this angle
- `205233` box 0: `35` 0.313, `47` 0.269, `39` 0.216; below_min_sim, short by 0.287; detector 0.49; ocr saw no text; pod unclear (yellow 0.000, aspect 0.9); lever: weak match, add references from this angle
- `199765` box 0: `27` 0.320, `58` 0.309, `85` 0.307; below_min_sim, short by 0.280; detector 0.84; read `5`; pod black (yellow 0.000, aspect 1.9); lever: weak match, add references from this angle
- `205435` box 0: `39` 0.331, `42` 0.325, `35` 0.312; below_min_sim, short by 0.269; detector 0.80; ocr saw no text; pod unclear (yellow 0.001, aspect 1.1); lever: weak match, add references from this angle
- `199741` box 0: `39` 0.333, `42` 0.326, `22` 0.322; below_min_sim, short by 0.267; detector 0.28; read `5`; pod black (yellow 0.000, aspect 1.5); lever: weak match, add references from this angle
- `205493` box 1: `55` 0.334, `83` 0.284, `35` 0.261; below_min_sim, short by 0.267; detector 0.32; ocr saw no text; pod black (yellow 0.000, aspect 2.6); lever: weak match, add references from this angle
- `198199` box 1: `39` 0.334, `35` 0.307, `60` 0.217; below_min_sim, short by 0.266; detector 0.23; ocr saw no text; pod black (yellow 0.000, aspect 6.1); lever: weak match, add references from this angle
- `199813` box 0: `50` 0.334, `42` 0.312, `63` 0.297; below_min_sim, short by 0.266; detector 0.89; ocr saw `aswmc` 0.95, `timferler` 0.40, `idv` 0.26; pod black (yellow 0.000, aspect 1.8); lever: weak match, add references from this angle
- `199485` box 1: `39` 0.337, `3` 0.332, `83` 0.312; below_min_sim, short by 0.263; detector 0.81; ocr saw no text; pod unclear (yellow 0.000, aspect 0.3); lever: weak match, add references from this angle
- `199485` box 2: `39` 0.337, `85` 0.302, `50` 0.297; below_min_sim, short by 0.263; detector 0.37; ocr saw no text; pod yellow (yellow 0.012, aspect 1.2); lever: weak match, add references from this angle
- `199761` box 3: `39` 0.340, `83` 0.339, `47` 0.257; below_min_sim, short by 0.260; detector 0.75; ocr saw no text; pod unclear (yellow 0.000, aspect 1.0); lever: weak match, add references from this angle
- `198245` box 1: `35` 0.341, `47` 0.276, `39` 0.275; below_min_sim, short by 0.259; detector 0.90; ocr saw no text; pod unclear (yellow 0.000, aspect 0.5); lever: weak match, add references from this angle
- `199553` box 2: `39` 0.341, `35` 0.280, `47` 0.273; below_min_sim, short by 0.259; detector 0.34; ocr saw no text; pod black (yellow 0.000, aspect 1.7); lever: weak match, add references from this angle
- … 794 more in report.json

## number-unmatched (22)

- `199677` box 0: `62` 0.407, `42` 0.400, `43` 0.362; below_min_sim, short by 0.193; detector 0.65; read `86`, `3`; pod black (yellow 0.000, aspect 1.6); lever: no entry has number 86 or 3
- `199683` box 1: `39` 0.439, `83` 0.312, `35` 0.285; below_min_sim, short by 0.161; detector 0.47; read `175`; pod black (yellow 0.000, aspect 4.0); lever: no entry has number 175
- `199861` box 0: `56` 0.462, `44` 0.436, `58` 0.404; below_min_sim, short by 0.138; detector 0.51; read `104`, `1`; pod black (yellow 0.000, aspect 1.6); lever: no entry has number 104
- `199909` box 0: `30` 0.475, `3` 0.467, `58` 0.429; below_min_sim, short by 0.125; detector 0.86; read `205`; pod yellow (yellow 0.009, aspect 1.2); lever: no entry has number 205
- `199855` box 0: `56` 0.476, `44` 0.410, `58` 0.362; below_min_sim, short by 0.124; detector 0.55; read `104`; pod black (yellow 0.000, aspect 1.6); lever: no entry has number 104
- `199859` box 0: `56` 0.484, `58` 0.437, `44` 0.425; below_min_sim, short by 0.116; detector 0.66; read `104`; pod black (yellow 0.000, aspect 1.6); lever: no entry has number 104
- `199857` box 0: `56` 0.485, `44` 0.432, `98` 0.370; below_min_sim, short by 0.115; detector 0.55; read `104`; pod black (yellow 0.000, aspect 1.6); lever: no entry has number 104
- `199745` box 0: `85` 0.499, `39` 0.437, `42` 0.393; below_min_sim, short by 0.101; detector 0.70; read `5`; pod black (yellow 0.000, aspect 1.6); lever: no entry has number 5
- `199913` box 0: `30` 0.511, `3` 0.488, `58` 0.463; below_min_sim, short by 0.089; detector 0.91; read `205`; pod yellow (yellow 0.009, aspect 1.2); lever: no entry has number 205
- `199235` box 0: `30` 0.526, `42` 0.509, `52` 0.497; below_min_sim, short by 0.074; detector 0.65; read `732`; pod black (yellow 0.000, aspect 2.2); lever: no entry has number 732
- `198397` box 0: `26` 0.528, `97` 0.518, `80` 0.419; below_min_sim, short by 0.072; detector 0.90; read `5`; pod black (yellow 0.000, aspect 2.6); lever: no entry has number 5
- `205263` box 0: `27` 0.552, `42` 0.539, `30` 0.530; below_min_sim, short by 0.048; detector 0.93; read `106`; pod unclear (yellow 0.000, aspect 1.3); lever: no entry has number 106
- `205493` box 0: `66` 0.553, `63` 0.493, `26` 0.413; below_min_sim, short by 0.047; detector 0.93; read `768`; pod black (yellow 0.000, aspect 2.5); lever: no entry has number 768
- `199321` box 0: `55` 0.561, `35` 0.475, `50` 0.468; below_min_sim, short by 0.039; detector 0.85; read `734`; pod black (yellow 0.000, aspect 1.4); lever: no entry has number 734
- `205207` box 0: `86` 0.568, `42` 0.546, `30` 0.537; below_min_sim, short by 0.032; detector 0.92; read `733`; pod black (yellow 0.000, aspect 2.6); lever: no entry has number 733
- `199311` box 0: `55` 0.597, `44` 0.461, `65` 0.449; below_min_sim, short by 0.003; detector 0.84; read `734`; pod black (yellow 0.000, aspect 2.1); lever: no entry has number 734
- `199225` box 0: `51` 0.610, `47` 0.600, `52` 0.519; margin_too_small, short by 0.089; detector 0.73; read `732`; pod black (yellow 0.000, aspect 2.3); lever: no entry has number 732
- `199331` box 0: `55` 0.611, `22` 0.607, `44` 0.566; margin_too_small, short by 0.096; detector 0.91; read `734`; pod black (yellow 0.000, aspect 2.1); lever: no entry has number 734
- `199319` box 0: `65` 0.613, `55` 0.593, `26` 0.486; margin_too_small, short by 0.080; detector 0.81; read `134`; pod black (yellow 0.000, aspect 2.3); lever: no entry has number 134
- `199273` box 0: `47` 0.632, `52` 0.596, `62` 0.558; margin_too_small, short by 0.064; detector 0.79; read `733`; pod yellow (yellow 0.007, aspect 1.7); lever: no entry has number 733
- … 2 more in report.json

## overlapped (292)

- `199523` box 1: `76` 0.295, `83` 0.292, `22` 0.291; overlapped; detector 0.56; ocr saw no text; pod black (yellow 0.000, aspect 1.6)
- `199683` box 2: `83` 0.305, `39` 0.298, `62` 0.260; overlapped; detector 0.69; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- `199489` box 1: `22` 0.308, `63` 0.284, `42` 0.277; overlapped; detector 0.39; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3)
- `199685` box 2: `83` 0.313, `39` 0.308, `62` 0.271; overlapped; detector 0.70; ocr saw no text; pod black (yellow 0.000, aspect 1.9)
- `199901` box 3: `22` 0.319, `50` 0.307, `40` 0.286; overlapped; detector 0.34; ocr saw `championship` 0.67, `msalz` 0.19; pod yellow (yellow 0.026, aspect 1.5)
- `199531` box 3: `83` 0.323, `87` 0.320, `39` 0.309; overlapped; detector 0.83; ocr saw no text; pod black (yellow 0.000, aspect 1.7)
- `205243` box 2: `39` 0.328, `83` 0.319, `35` 0.316; overlapped; detector 0.75; ocr saw no text; pod unclear (yellow 0.000, aspect 0.3)
- `199921` box 1: `98` 0.332, `76` 0.331, `78` 0.307; overlapped; detector 0.24; ocr saw `e` 0.24; pod unclear (yellow 0.000, aspect 1.1)
- `199875` box 1: `98` 0.332, `87` 0.319, `60` 0.296; overlapped; detector 0.52; read `1`; pod black (yellow 0.000, aspect 2.4)
- `199491` box 1: `22` 0.333, `56` 0.280, `39` 0.280; overlapped; detector 0.40; ocr saw no text; pod unclear (yellow 0.000, aspect 1.3)
- `199763` box 1: `39` 0.334, `83` 0.314, `35` 0.291; overlapped; detector 0.27; ocr saw no text; pod black (yellow 0.000, aspect 2.7)
- `199653` box 1: `39` 0.338, `50` 0.333, `22` 0.312; overlapped; detector 0.23; ocr saw no text; pod black (yellow 0.000, aspect 1.5)
- `205493` box 2: `55` 0.344, `83` 0.337, `35` 0.276; overlapped; detector 0.38; ocr saw no text; pod black (yellow 0.000, aspect 2.6)
- `205247` box 2: `35` 0.346, `39` 0.314, `83` 0.285; overlapped; detector 0.67; ocr saw no text; pod unclear (yellow 0.000, aspect 0.3)
- `199525` box 2: `85` 0.347, `39` 0.337, `60` 0.331; overlapped; detector 0.54; ocr saw no text; pod black (yellow 0.000, aspect 2.3)
- `199277` box 2: `39` 0.348, `47` 0.310, `87` 0.254; overlapped; detector 0.38; ocr saw no text; pod yellow (yellow 0.003, aspect 0.7)
- `205245` box 2: `35` 0.351, `39` 0.339, `83` 0.315; overlapped; detector 0.77; ocr saw no text; pod unclear (yellow 0.000, aspect 0.3)
- `199781` box 2: `39` 0.352, `56` 0.347, `43` 0.320; overlapped; detector 0.21; ocr saw no text; pod black (yellow 0.000, aspect 1.7)
- `199791` box 1: `22` 0.353, `39` 0.338, `83` 0.324; overlapped; detector 0.56; ocr saw no text; pod unclear (yellow 0.000, aspect 1.0)
- `199605` box 2: `39` 0.353, `83` 0.291, `76` 0.273; overlapped; detector 0.20; ocr saw `isuzt` 0.53; pod black (yellow 0.000, aspect 1.4)
- … 272 more in report.json

## no-vehicle (58)

- `205227` burst 6: no vehicle at 0.2: strongest class 13 0.16 (0.84x0.98 of frame), strongest vehicle car 0.04 (0.86x0.99 of frame)
- `205265` burst 14: no vehicle at 0.2: strongest class 13 0.64 (0.99x0.34 of frame), strongest vehicle car 0.01 (0.08x0.03 of frame)
- `205277` burst 15: no vehicle at 0.2: strongest car 0.92 (0.09x0.05 of frame), strongest vehicle car 0.92 (0.09x0.05 of frame)
- `205279` burst 15: no vehicle at 0.2: strongest car 0.89 (0.09x0.05 of frame), strongest vehicle car 0.89 (0.09x0.05 of frame)
- `205293` burst 16: no vehicle at 0.2: strongest car 0.67 (0.03x0.17 of frame), strongest vehicle car 0.67 (0.03x0.17 of frame)
- `205295` burst 17: no vehicle at 0.2: strongest car 0.90 (0.06x0.06 of frame), strongest vehicle car 0.90 (0.06x0.06 of frame)
- `205307` burst 18: no vehicle at 0.2: strongest person 0.60 (0.02x0.06 of frame), strongest vehicle car 0.06 (0.07x0.06 of frame)
- `205309` burst 18: no vehicle at 0.2: strongest person 0.56 (0.02x0.07 of frame), strongest vehicle car 0.03 (0.04x0.04 of frame)
- `205311` burst 18: no vehicle at 0.2: strongest car 0.64 (0.08x0.06 of frame), strongest vehicle car 0.64 (0.08x0.06 of frame)
- `205313` burst 18: no vehicle at 0.2: strongest car 0.88 (0.08x0.06 of frame), strongest vehicle car 0.88 (0.08x0.06 of frame)
- `205315` burst 18: no vehicle at 0.2: strongest car 0.93 (0.07x0.06 of frame), strongest vehicle car 0.93 (0.07x0.06 of frame)
- `205343` burst 22: no vehicle at 0.2: strongest car 0.91 (0.06x0.06 of frame), strongest vehicle car 0.91 (0.06x0.06 of frame)
- `205345` burst 22: no vehicle at 0.2: strongest car 0.88 (0.05x0.06 of frame), strongest vehicle car 0.88 (0.05x0.06 of frame)
- `205347` burst 22: no vehicle at 0.2: strongest car 0.88 (0.05x0.07 of frame), strongest vehicle car 0.88 (0.05x0.07 of frame)
- `205349` burst 22: no vehicle at 0.2: strongest car 0.88 (0.06x0.07 of frame), strongest vehicle car 0.88 (0.06x0.07 of frame)
- `205351` burst 22: no vehicle at 0.2: strongest car 0.91 (0.07x0.07 of frame), strongest vehicle car 0.91 (0.07x0.07 of frame)
- `205385` burst 25: no vehicle at 0.2: strongest car 0.87 (0.06x0.05 of frame), strongest vehicle car 0.87 (0.06x0.05 of frame)
- `205387` burst 26: no vehicle at 0.2: strongest car 0.83 (0.07x0.06 of frame), strongest vehicle car 0.83 (0.07x0.06 of frame)
- `205389` burst 26: no vehicle at 0.2: strongest car 0.83 (0.08x0.06 of frame), strongest vehicle car 0.83 (0.08x0.06 of frame)
- `205391` burst 26: no vehicle at 0.2: strongest person 0.52 (0.02x0.06 of frame), strongest vehicle car 0.17 (0.06x0.05 of frame)
- … 38 more in report.json
