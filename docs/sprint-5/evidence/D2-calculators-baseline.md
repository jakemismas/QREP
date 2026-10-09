# D2 calculator conformance baseline

Generated on 2026-10-09 by:

```
.venv/Scripts/python scripts/eval/calculators/baseline.py --start-sha 3fa671e --work '<work>/.' --raw '<work>/raw.json' --raw '<work>/raw_retry.json' --shots scripts/eval/calculators/failures --out-json docs/sprint-5/evidence/D2-calculators-baseline.json --out-md docs/sprint-5/evidence/D2-calculators-baseline.md
```

| Item | Value |
| --- | --- |
| qrep imported from | C:\Users\Jake Mismas\qrep-wt\d2\qrep\__init__.py |
| git HEAD | 736f8b00a8c6d123b2f8a4499f0ad40cda83f8b2 |
| Start SHA | 3fa671ecc52f7939aa60bac11551bc68054faf6d (given as 3fa671e) |
| qrep tree at the start SHA | 59a4cc0314963b1422b74cde4f7303e9d21eb99e |
| OpenCV (cv2) | 5.0.0; decode path: not applicable (no images decoded) |
| Raw record files | <work>/raw.json (n = 270 records); <work>/raw_retry.json (n = 15 records) |
| Calculator runs (record timestamps) | 2026-10-09T00:54:55.685Z to 2026-10-09T06:01:28.876Z |
| Border size basis | dtq_border center, sewbecca_border center, qc_border center |

QREP values come from qrep.bridge.plan at the start SHA (calc_qrep.py), at the engine default (wof 336, 42 in) and configured at wof 320 (40 in). MATH.md vectors come from calc_vectors.py, transcribed from MATH.md section 4. Yards print as mixed fractions; V and H are vertical and horizontal seams; (n) after a yardage is its panel count; the first layout in a calculator cell is the one compared. Bracketed ids point to the labeled differences.

## Inputs

### Size matrix (n = 15, MATH.md 5.2)

| Row | Quilt | W x L (in) |
| --- | --- | --- |
| 36x52 | crib 36 x 52 | 36 x 52 |
| 50x65 | throw 50 x 65 | 50 x 65 |
| 60x72 | throw 60 x 72 | 60 x 72 |
| 70x90 | twin 70 x 90 | 70 x 90 |
| 84x90 | full 84 x 90 | 84 x 90 |
| 90x108 | queen 90 x 108 | 90 x 108 |
| 92.5x115 | queen 92 1/2 x 115 | 92 1/2 x 115 |
| 110x108 | king 110 x 108 | 110 x 108 |
| 75x90 | fixture 75 x 90 | 75 x 90 |
| 42x52 | 42 x 52 | 42 x 52 |
| 76x85 | 76 x 85 | 76 x 85 |
| 68x68 | 68 x 68 | 68 x 68 |
| 102.5x120 | 102 1/2 x 120 | 102 1/2 x 120 |
| 58x66 | 58 x 66 | 58 x 66 |
| 24x58 | 24 x 58 | 24 x 58 |

### Border rows (n = 18)

| Row | Label | Center (in) | Bands, outside last (in) | Finished (in) |
| --- | --- | --- | --- | --- |
| 36x52-b3.75 | crib 36 x 52: center 28 1/2 x 44 1/2, band 3 3/4 | 28 1/2 x 44 1/2 | 3 3/4 | 36 x 52 |
| 50x65-b3.75 | throw 50 x 65: center 42 1/2 x 57 1/2, band 3 3/4 | 42 1/2 x 57 1/2 | 3 3/4 | 50 x 65 |
| 60x72-b3.75 | throw 60 x 72: center 52 1/2 x 64 1/2, band 3 3/4 | 52 1/2 x 64 1/2 | 3 3/4 | 60 x 72 |
| 70x90-b3.75 | twin 70 x 90: center 62 1/2 x 82 1/2, band 3 3/4 | 62 1/2 x 82 1/2 | 3 3/4 | 70 x 90 |
| 84x90-b3.75 | full 84 x 90: center 76 1/2 x 82 1/2, band 3 3/4 | 76 1/2 x 82 1/2 | 3 3/4 | 84 x 90 |
| 90x108-b3.75 | queen 90 x 108: center 82 1/2 x 100 1/2, band 3 3/4 | 82 1/2 x 100 1/2 | 3 3/4 | 90 x 108 |
| 92.5x115-b3.75 | queen 92 1/2 x 115: center 85 x 107 1/2, band 3 3/4 | 85 x 107 1/2 | 3 3/4 | 92 1/2 x 115 |
| 110x108-b3.75 | king 110 x 108: center 102 1/2 x 100 1/2, band 3 3/4 | 102 1/2 x 100 1/2 | 3 3/4 | 110 x 108 |
| 75x90-b3.75 | fixture 75 x 90: center 67 1/2 x 82 1/2, band 3 3/4 | 67 1/2 x 82 1/2 | 3 3/4 | 75 x 90 |
| 42x52-b3.75 | 42 x 52: center 34 1/2 x 44 1/2, band 3 3/4 | 34 1/2 x 44 1/2 | 3 3/4 | 42 x 52 |
| 76x85-b3.75 | 76 x 85: center 68 1/2 x 77 1/2, band 3 3/4 | 68 1/2 x 77 1/2 | 3 3/4 | 76 x 85 |
| 68x68-b3.75 | 68 x 68: center 60 1/2 x 60 1/2, band 3 3/4 | 60 1/2 x 60 1/2 | 3 3/4 | 68 x 68 |
| 102.5x120-b3.75 | 102 1/2 x 120: center 95 x 112 1/2, band 3 3/4 | 95 x 112 1/2 | 3 3/4 | 102 1/2 x 120 |
| 58x66-b3.75 | 58 x 66: center 50 1/2 x 58 1/2, band 3 3/4 | 50 1/2 x 58 1/2 | 3 3/4 | 58 x 66 |
| 24x58-b3.75 | 24 x 58: center 16 1/2 x 50 1/2, band 3 3/4 | 16 1/2 x 50 1/2 | 3 3/4 | 24 x 58 |
| V-BORD-02 | crib: center 32 x 48, band 2 | 32 x 48 | 2 | 36 x 52 |
| V-BORD-03 | center 60 x 72, bands 2 then 5 | 60 x 72 | 2, 5 | 74 x 86 |
| V-BORD-04 | tiny: center 4 x 4, band 1 | 4 x 4 | 1 | 6 x 6 |

### Piece count spot checks (n = 3)

| Row | Check | Expected pieces | Source |
| --- | --- | --- | --- |
| V-YIELD-01@40 | squares cut 2 1/2 in from one 40 x 2 1/2 in strip | 16 | MATH.md line 574: per = floor(40 / 2.5) = 16 (320 // 20) |
| V-YIELD-02@40 | rectangles cut 2 1/2 x 4 1/2 in from one 40 x 4 1/2 in strip | 16 | MATH.md line 589: 4 1/2 in strips, per = floor(40 / 2.5) = 16 |
| V-YIELD-02@42 | rectangles cut 2 1/2 x 4 1/2 in from one 42 x 4 1/2 in strip | 16 | MATH.md line 583: 4 1/2 in strips, per = floor(42 / 2.5) = 16 (336 // 20) |

### Calculators (n = 13)

| Key | Vendor and page | URL | Line types | MATH.md 5.2 list | Inputs typed | Set by the driver | Parser | Rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qp_backing | Quilter's Paradise: Backing and Batting | https://www.quiltersparadiseesc.com/Calculators/Backing%20and%20Batting%20Calculator.php | backing, batting | yes | @42: Fabric_Width 42, Width W, Length L, Overage 4; @40: Fabric_Width 40, Width W, Length L, Overage 4; @batting120: Fabric_Width 120, Width W, Length L, Overage 4 | batting rows: bolt 120 in, one width for every matrix size | calc_parse.parse_qp_backing | backing: qp; batting: qp (MATH.md 5.2 and the page script: 1 in per seam, no allowance, 1/8 yd with 1/3 steps) |
| qp_binding | Quilter's Paradise: Binding | https://www.quiltersparadiseesc.com/Calculators/Binding%20Calculator.php | binding | yes | @40: Fabric_Width 40, Width W, Length L, Strip_Width 2 1/2 | - | calc_parse.parse_qp_binding | binding: qp (MATH.md 5.2: same strip formula as F7, its own yard rounding) |
| qp_border | Quilter's Paradise: Border | https://www.quiltersparadiseesc.com/Calculators/Border%20Calculator.php | borders | yes | @40: Fabric_Width 40, Width W, Length L, Border1Width b1 | non-mitred corners, end-to-end joins (driver default) | calc_parse.parse_qp_border | borders: qp (MATH.md 5.2: pools all strips, adds 1/2 in to border widths) |
| mfqs_backing | My Favorite Quilt Store: Backing and Batting | https://myfavoritequiltstore.com/toolbox/backing-calculator | backing, batting | yes | @42: length L, width W, overage 4, fabric_width 42 | batting type Cotton (driver default) | calc_parse.parse_mfqs_backing | calc_rules.mfqs_backing (calc_rules.mfqs_backing, from the page script (MATH.md 5.2: record only)) |
| nqc | Nebraska Quilt Company: Backing and Binding | https://www.nebraskaquiltcompany.com/pages/backing-binding-calculator | backing, binding | yes | @40: width W, length L, fabricWidth 40; @108: width W, length L, fabricWidth 108; @118: width W, length L, fabricWidth 118 | - | calc_parse.parse_nqc | backing: nqc; binding: nqc; wide: nqc (backing: MATH.md 5.2 (+8 in, 1/2 in per seam, 1/4 yd, no allowance); binding: the page script (+12 in, strips over the full 40 in), not stated in MATH.md 5.2) |
| stitchdesk_backing | The Stitch Desk: Backing Calculator | https://thestitchdesk.com/calculators/backing-calculator | backing, batting | added | @42: w W, l L, oh 4, bo 4, fw 42, sa 1/2 | price left empty | calc_parse.parse_stitchdesk_backing | calc_rules.stitchdesk_backing (calc_rules.stitchdesk_backing, from the page script) |
| stitchdesk_binding | The Stitch Desk: Binding Calculator | https://thestitchdesk.com/calculators/binding-calculator | binding | added | @42: bqW W, bqL L, bsw 2.5, bfw 42 | straight grain (driver default), price left empty | calc_parse.parse_stitchdesk_binding | calc_rules.stitchdesk_binding (calc_rules.stitchdesk_binding, from the page script) |
| quiltkeeper_binding | QuiltKeeper Studio: Binding | https://quiltkeeperstudio.com/calculators/binding | binding | added | @40: quilt-width W, quilt-height L, strip-width 2.5, fabric-width 40, overage 10 | - | calc_parse.parse_quiltkeeper_binding | binding: quiltkeeper (calc_rules.BINDING_SETS['quiltkeeper'], from the page script: strips over the full fabric width, 1/8 yd) |
| omni_backing | Omni Calculator: Quilt Calculator | https://www.omnicalculator.com/everyday-life/quilt | backing, batting | added | @42: mode backing, width W, length L, fabric_width 42, overage 0; @42-batting: mode batting, width W, length L, fabric_width 42, overage 0 | non-directional fabric, additional overage 0 (the page adds 4 in per side); batting size = its displayed pieces side by side (pieces x piece size) | calc_parse.parse_omni_backing | calc_rules.omni_backing (calc_rules.omni_backing, from the page script) |
| dtq_border | Designed to Quilt: Quilt Border Calculator | https://designedtoquilt.com/quilt-border-calculator/ | borders | added | @40: number-1 W, number-2 L, number-4 40, number-5 b1 | center size; fabric width 40; straight joins compared, mitered recorded | calc_parse.parse_dtq_border | calc_rules.dtq_border (calc_rules.dtq_border, from the page's form formulas) |
| sewbecca_border | Sew Becca: Border Calculator | https://sewbecca.com/border-calc | borders | added | @40: quiltWidth W, quiltLength L, borderWidth b1, fabricWidth 40 | center size | calc_parse.parse_sewbecca_border | calc_rules.sewbecca_border (calc_rules.sewbecca_border, from the page script) |
| qc_border | Quilt Calculator: Border Calculator | https://quiltcalculator.com/border-calculator | borders | added | @40: width W, length L, fabric_width 40, border1_width b1 | center size; URL found from the site's home page link at run time; up to 3 bands | calc_parse.parse_qc_border | calc_rules.qc_border (calc_rules.qc_border, from the page script) |
| qp_piece_count | Quilter's Paradise: Piece Count | https://www.quiltersparadiseesc.com/Calculators/Piece%20Count%20Calculator.php | yield | yes | @40: piece_width 2.5, piece_length 2.5, large_piece_width 40, large_piece_length 2.5; @40: piece_width 2.5, piece_length 4.5, large_piece_width 40, large_piece_length 4.5; @42: piece_width 2.5, piece_length 4.5, large_piece_width 42, large_piece_length 4.5 | spot check of V-YIELD-01 and V-YIELD-02 (MATH.md 5.2 note); the typed orientation is compared, the turned one recorded | calc_parse.parse_qp_piece_count | calc_rules.qp_piece_count (calc_rules.qp_piece_count, from the page script) |

## Coverage

Rows that returned a parsed value, of rows tried (a record that was not a not-applicable skip); the planned row count follows when it differs.

| Calculator | Backing | Binding | Batting | Borders | Piece count |
| --- | --- | --- | --- | --- | --- |
| qp_backing | n = 28 of 30 | - | n = 14 of 15 | - | - |
| qp_binding | - | n = 14 of 15 | - | - | - |
| qp_border | - | - | - | n = 14 of 18 | - |
| mfqs_backing | n = 15 of 15 | - | n = 15 of 15 | - | - |
| nqc | n = 45 of 45 | n = 15 of 15 | - | - | - |
| stitchdesk_backing | n = 15 of 15 | - | n = 15 of 15 | - | - |
| stitchdesk_binding | - | n = 15 of 15 | - | - | - |
| quiltkeeper_binding | - | n = 15 of 15 | - | - | - |
| omni_backing | n = 15 of 15 | - | n = 15 of 15 | - | - |
| dtq_border | - | - | - | n = 16 of 17 | - |
| sewbecca_border | - | - | - | n = 17 of 17 | - |
| qc_border | - | - | - | n = 18 of 18 | - |
| qp_piece_count | - | - | - | - | n = 3 of 3 |

## Backing

### Pieced at 42 in

| Row | MATH.md vector (B 42) | QREP today (wof 336) | Quilter's Paradise 42 | My Favorite Quilt Store 42 (record only) | Stitch Desk 42 | Omni 42 |
| --- | --- | --- | --- | --- | --- | --- |
| 36x52 | V-BACK-03: H 2 3/4 (2) | V 3 1/2 (2) | H 2 1/2 (2); V 3 3/8 (2) [BK-1, BK-2] | H 2 1/2 (2) [BK-4, BK-5] | H 2 1/2 (2) [BK-7, BK-8] | H 2.45 (2) [BK-9, BK-10] |
| 50x65 | V-BACK-04: H 3 1/2 (2) | V 4 1/4 (2) | H 3 1/4 (2); V 4 1/8 (2) [BK-11, BK-12] | H 3 1/4 (2) [BK-14, BK-15] | H 3 1/4 (2) [BK-17, BK-18] | H 3.23 (2) [BK-19, BK-20] |
| 60x72 | V-BACK-02: H 4 1/4 (2) | V 4 1/2 (2) | H 3 7/8 (2); V 4 1/2 (2) [BK-21, BK-22] | H 3 7/8 (2) [BK-24, BK-25] | V 4 1/2 (2) [BK-27] | H 3.78 (2) [BK-28, BK-29] |
| 70x90 | V-BACK-05: V 5 3/4 (2) | V 5 1/2 (2) | V 5 1/2 (2); H 6 1/2 (3) [BK-30] | V 5 1/2 (2) [BK-31] | V 5 1/2 (2) [BK-32] | V 5.45 (2) [BK-33, BK-34] |
| 84x90 | V-BACK-06: H 8 (3) | V 8 1/4 (3) | H 7 2/3 (3); V 8 1/4 (3) [BK-35, BK-36] | H 7 3/4 (3) [BK-38, BK-39] | H 7 3/4 (3) [BK-41, BK-42] | H 7.67 (3) [BK-43, BK-44] |
| 90x108 | V-BACK-07: H 8 1/2 (3) | V 9 3/4 (3) | H 8 1/4 (3); V 9 3/4 (3) [BK-45, BK-46] | H 8 1/4 (3) [BK-48, BK-49] | H 8 1/4 (3) [BK-51, BK-52] | H 8.17 (3) [BK-53, BK-54] |
| 92.5x115 | V-BACK-01: H 8 3/4 (3) | V 10 1/4 (3) | H 8 3/8 (3); V 10 1/4 (3) [BK-55, BK-56] | H 8 3/8 (3) [BK-58, BK-59] | V 10 1/4 (3) [BK-61] | H 8.38 (3) [BK-62, BK-63] |
| 110x108 | V-BACK-08: V 10 (3) | V 9 3/4 (3) | V 9 3/4 (3); H 9 7/8 (3) [BK-64] | V 9 3/4 (3) [BK-65] | H 9 7/8 (3) [BK-66, BK-67] | V 9.67 (3) [BK-68, BK-69] |
| 75x90 | V-BACK-09: V 5 3/4 (2) | V 5 1/2 (2) | V 5 1/2 (2); H 7 (3) [BK-70] | H 7 (3) [BK-73, BK-74, BK-75, BK-76] | H 7 (3) [BK-79, BK-80, BK-81, BK-82] | V 5.45 (2) [BK-83, BK-84] |
| 42x52 | V-BACK-11: H 3 1/4 (2) | V 3 1/2 (2) | H 2 7/8 (2); V 3 3/8 (2) [BK-85, BK-86] | H 2 7/8 (2) [BK-88, BK-89] | H 2 7/8 (2) [BK-91, BK-92] | H 2.78 (2) [BK-93, BK-94] |
| 76x85 | V-BACK-10: H 7 1/4 (3) | V 5 1/4 (2) | H 7 (3); V 7 3/4 (3) [BK-95, BK-96, BK-97] | H 7 (3) [BK-99, BK-100, BK-101] | H 7 (3) [BK-103, BK-104, BK-105] | V 5.17 (2) [BK-106, BK-107, BK-108] |
| 68x68 | V-BACK-13: V 4 1/2 (2) | V 4 1/4 (2) | V 4 1/4 (2); H 4 1/4 (2) [BK-109] | H 4 1/4 (2) [BK-110] | V 4 1/4 (2) [BK-111] | H 4.23 (2) [BK-112, BK-113] |
| 102.5x120 | V-BACK-16: V 11 (3) | V 10 3/4 (3) | failed [F10] | V 10 3/4 (3) [BK-114] | V 10 3/4 (3) [BK-115] | V 10.67 (3) [BK-116, BK-117] |
| 58x66 | V-BACK-23: H 4 (2) | V 4 1/4 (2) | H 3 2/3 (2); V 4 1/8 (2) [BK-118, BK-119] | H 3 3/4 (2) [BK-121, BK-122] | H 3 3/4 (2) [BK-124, BK-125] | H 3.67 (2) [BK-126, BK-127] |
| 24x58 | V-BACK-14: V 2 (1) | V 2 (1) | V 1 7/8 (1); H 1 7/8 (2) [BK-128, BK-129] | 1 pc 1 7/8 (1) [BK-131, BK-132] | H 1 7/8 (2) [BK-133, BK-134, BK-135, BK-136] | 1 pc 1.84 (1) [BK-137, BK-138] |

### Pieced at 40 in

| Row | MATH.md vector (B 40) | QREP at wof 320 | Quilter's Paradise 40 | Nebraska 40 |
| --- | --- | --- | --- | --- |
| 36x52 | no vector | V 3 1/2 (2) | H 2 1/2 (2); V 3 3/8 (2) [BK-3] | H 2 1/2 (2); V 3 1/2 (2) [BK-6] |
| 50x65 | no vector | V 4 1/4 (2) | H 3 1/4 (2); V 4 1/8 (2) [BK-13] | H 3 1/4 (2); V 4 1/4 (2) [BK-16] |
| 60x72 | V-BACK-19: V 4 3/4 (2) | V 4 1/2 (2) | V 4 1/2 (2); H 5 2/3 (3) [BK-23] | V 4 1/2 (2); H 5 3/4 (3) [BK-26] |
| 70x90 | no vector | V 5 1/2 (2) | V 5 1/2 (2); H 6 1/2 (3) | V 5 1/2 (2); H 6 1/2 (3) |
| 84x90 | no vector | V 8 1/4 (3) | H 7 2/3 (3); V 8 1/4 (3) [BK-37] | H 7 3/4 (3); V 8 1/4 (3) [BK-40] |
| 90x108 | no vector | V 9 3/4 (3) | H 8 1/4 (3); V 9 3/4 (3) [BK-47] | H 8 1/4 (3); V 9 3/4 (3) [BK-50] |
| 92.5x115 | V-BACK-18: V 10 1/2 (3) | V 10 1/4 (3) | V 10 1/4 (3); H 11 1/4 (4) [BK-57] | V 10 1/4 (3); H 11 1/4 (4) [BK-60] |
| 110x108 | no vector | V 9 3/4 (3) | V 9 3/4 (3); H 9 7/8 (3) | V 9 3/4 (3); H 10 (3) |
| 75x90 | V-BACK-20: H 7 1/4 (3) | V 8 1/4 (3) | H 7 (3); V 8 1/4 (3) [BK-71, BK-72] | H 7 (3); V 8 1/4 (3) [BK-77, BK-78] |
| 42x52 | no vector | V 3 1/2 (2) | H 2 7/8 (2); V 3 3/8 (2) [BK-87] | H 3 (2); V 3 1/2 (2) [BK-90] |
| 76x85 | no vector | V 7 3/4 (3) | H 7 (3); V 7 3/4 (3) [BK-98] | H 7 (3); V 7 3/4 (3) [BK-102] |
| 68x68 | no vector | V 4 1/4 (2) | V 4 1/4 (2); H 4 1/4 (2) | V 4 1/4 (2); H 4 1/4 (2) |
| 102.5x120 | no vector | V 10 3/4 (3) | failed [F11] | V 10 3/4 (3); H 12 1/2 (4) |
| 58x66 | no vector | V 4 1/4 (2) | H 3 2/3 (2); V 4 1/8 (2) [BK-120] | H 3 3/4 (2); V 4 1/4 (2) [BK-123] |
| 24x58 | no vector | V 2 (1) | V 1 7/8 (1); H 1 7/8 (2) [BK-130] | V 2 (1); H 2 (2) |

### Wide-back

QREP today has no wide-back line (D-06). A 42 in calculator's cell shows the wide line it prints beside its pieced result.

| Row | MATH.md vector 108 | MATH.md vector 118 | Nebraska 108 | Nebraska 118 | Stitch Desk wide line | My Favorite Quilt Store wide line |
| --- | --- | --- | --- | --- | --- | --- |
| 36x52 | V-WIDE-10: 1 1/2 (44 in) | no vector | H 1 1/4 (1); V 1 3/4 (1) [WB-2] | H 1 1/4 (1); V 1 3/4 (1) (no vector at this width) | 108 in: 1 pc 1 1/4 [WB-3] | 108 in: 1 pc 1 1/4 (1) [WB-1] |
| 50x65 | V-WIDE-10: 1 3/4 (58 in) | no vector | H 1 3/4 (1); V 2 1/4 (1) | H 1 3/4 (1); V 2 1/4 (1) (no vector at this width) | 108 in: 1 pc 1 5/8 [WB-5] | 108 in: 1 pc 1 5/8 (1) [WB-4] |
| 60x72 | V-WIDE-02: 2 1/4 (68 in) | no vector | H 2 (1); V 2 1/4 (1) [WB-7] | H 2 (1); V 2 1/4 (1) (no vector at this width) | 108 in: 1 pc 2 [WB-8] | 108 in: 1 pc 2 (1) [WB-6] |
| 70x90 | V-WIDE-10: 2 1/2 (78 in) | no vector | H 2 1/4 (1); V 2 3/4 (1) [WB-10] | H 2 1/4 (1); V 2 3/4 (1) (no vector at this width) | 108 in: 1 pc 2 1/4 [WB-11] | 108 in: 1 pc 2 1/4 (1) [WB-9] |
| 84x90 | V-WIDE-10: 2 3/4 (92 in) | no vector | H 2 3/4 (1); V 2 3/4 (1) | H 2 3/4 (1); V 2 3/4 (1) (no vector at this width) | 108 in: 1 pc 2 5/8 [WB-13] | 108 in: 1 pc 2 5/8 (1) [WB-12] |
| 90x108 | V-WIDE-04: 3 1/2 (116 in) | no vector | V 3 1/4 (1); H 5 1/2 (2) [WB-15] | H 2 3/4 (1); V 3 1/4 (1) (no vector at this width) | 108 in: 1 pc 3 1/4 [WB-16] | 108 in: 1 pc 3 1/4 (1) [WB-14] |
| 92.5x115 | V-WIDE-01: 3 3/4 (123 in) | no vector | V 3 1/2 (1); H 5 3/4 (2) [WB-18] | V 3 1/2 (1); H 5 3/4 (2) (no vector at this width) | 108 in: 1 pc 3 1/2 [WB-19] | 108 in: 1 pc 3 1/2 (1) [WB-17] |
| 110x108 | V-WIDE-05: no 108 in line | V-WIDE-05: 3 1/2 (116 in) | V 6 1/2 (2); H 6 3/4 (2) (MATH.md prints no wide line at 108 in (V-WIDE-05)) | V 3 1/4 (1); H 3 1/2 (1) [WB-20] | 108 in: 1 pc 6 1/2 (MATH.md prints no wide line at 108 in (V-WIDE-05)) | 108 in: 1 pc 6 1/2 (2) (MATH.md prints no wide line at 108 in (V-WIDE-05)) |
| 75x90 | V-WIDE-08: 2 1/2 (83 in) | no vector | H 2 1/2 (1); V 2 3/4 (1) | H 2 1/2 (1); V 2 3/4 (1) (no vector at this width) | 108 in: 1 pc 2 3/8 [WB-22] | 108 in: 1 pc 2 3/8 (1) [WB-21] |
| 42x52 | V-WIDE-09: 1 3/4 (50 in) | no vector | H 1 1/2 (1); V 1 3/4 (1) [WB-24] | H 1 1/2 (1); V 1 3/4 (1) (no vector at this width) | 108 in: 1 pc 1 1/2 [WB-25] | 108 in: 1 pc 1 1/2 (1) [WB-23] |
| 76x85 | V-WIDE-03: 2 1/2 (84 in) | no vector | H 2 1/2 (1); V 2 3/4 (1) | H 2 1/2 (1); V 2 3/4 (1) (no vector at this width) | 108 in: 1 pc 2 3/8 [WB-27] | 108 in: 1 pc 2 3/8 (1) [WB-26] |
| 68x68 | no vector | no vector | V 2 1/4 (1); H 2 1/4 (1) (no vector at this width) | V 2 1/4 (1); H 2 1/4 (1) (no vector at this width) | 108 in: 1 pc 2 1/8 (no vector at this width) | 108 in: 1 pc 2 1/8 (1) (no vector at this width) |
| 102.5x120 | V-WIDE-06: no 108 in line | V-WIDE-06: 3 3/4 (128 in) | H 6 1/4 (2); V 7 1/4 (2) (MATH.md prints no wide line at 108 in (V-WIDE-06)) | V 3 3/4 (1); H 6 1/4 (2) | 108 in: 1 pc 6 1/4 (MATH.md prints no wide line at 108 in (V-WIDE-06)) | 108 in: 1 pc 6 1/4 (2) (MATH.md prints no wide line at 108 in (V-WIDE-06)) |
| 58x66 | no vector | no vector | H 2 (1); V 2 1/4 (1) (no vector at this width) | H 2 (1); V 2 1/4 (1) (no vector at this width) | 108 in: 1 pc 1 7/8 (no vector at this width) | 108 in: 1 pc 1 7/8 (1) (no vector at this width) |
| 24x58 | no vector | no vector | H 1 (1); V 2 (1) (no vector at this width) | H 1 (1); V 2 (1) (no vector at this width) | 108 in: 1 pc 1 (no vector at this width) | 108 in: 1 pc 1 (1) (no vector at this width) |

## Binding

Vectors at U = 40 (V-BIND-09 at U = 42 for the fixture, used for 42 in calculators). QREP today joins blind at 42 in (D-08).

| Row | MATH.md vector (strips, yd) | QREP today (wof 336) | Quilter's Paradise 40 | Nebraska 40 | Stitch Desk 42 | QuiltKeeper 40 |
| --- | --- | --- | --- | --- | --- | --- |
| 36x52 | V-BIND-11: 5, 1/2 | 5, 1/2 | 5 strips, 3/8 [BD-1, BD-2] | 5 strips, 1/2 | 6 strips, 1/2 [BD-3, BD-4] | 5 strips, 3/8 [BD-5, BD-6] |
| 50x65 | V-BIND-12: 7, 1/2 | 6, 1/2 | 7 strips, 1/2 [BD-7] | 7 strips, 1/2 [BD-8] | 7 strips, 1/2 [BD-9] | 6 strips, 1/2 [BD-10] |
| 60x72 | V-BIND-13: 8, 3/4 | 7, 1/2 | 8 strips, 5/8 [BD-11, BD-12, BD-13] | 7 strips, 1/2 [BD-14, BD-15] | 8 strips, 5/8 [BD-16, BD-17, BD-18] | 7 strips, 1/2 [BD-19, BD-20] |
| 70x90 | V-BIND-14: 9, 3/4 | 8, 3/4 | 9 strips, 5/8 [BD-21, BD-22, BD-23] | 9 strips, 3/4 [BD-24] | 10 strips, 3/4 [BD-25, BD-26] | 9 strips, 5/8 [BD-27, BD-28, BD-29] |
| 84x90 | V-BIND-15: 10, 3/4 | 9, 3/4 | 10 strips, 3/4 [BD-30] | 9 strips, 3/4 [BD-31] | 10 strips, 3/4 [BD-32] | 9 strips, 5/8 [BD-33, BD-34, BD-35] |
| 90x108 | V-BIND-16: 11, 1 | 10, 3/4 | 11 strips, 7/8 [BD-36, BD-37, BD-38] | 11 strips, 1 [BD-39, BD-40] | 12 strips, 7/8 [BD-41, BD-42, BD-43, BD-44] | 11 strips, 7/8 [BD-45, BD-46, BD-47] |
| 92.5x115 | V-BIND-05: 12, 1 | 11, 1 | 12 strips, 7/8 [BD-48, BD-49, BD-50] | 11 strips, 1 [BD-51] | 12 strips, 7/8 [BD-52, BD-53, BD-54] | 11 strips, 7/8 [BD-55, BD-56, BD-57] |
| 110x108 | V-BIND-17: 12, 1 | 11, 1 | 12 strips, 7/8 [BD-58, BD-59, BD-60] | 12 strips, 1 [BD-61] | 13 strips, 1 [BD-62, BD-63] | 12 strips, 7/8 [BD-64, BD-65, BD-66] |
| 75x90 | V-BIND-01: 10, 3/4; at 42 V-BIND-09: 9, 3/4 | 9, 3/4 | 10 strips, 3/4 [BD-67] | 9 strips, 3/4 [BD-68] | 10 strips, 3/4 [BD-69, BD-70] | 9 strips, 5/8 [BD-71, BD-72, BD-73] |
| 42x52 | V-BIND-10: 6, 1/2 | 5, 1/2 | 6 strips, 1/2 [BD-74] | 5 strips, 1/2 [BD-75] | 6 strips, 1/2 [BD-76] | 5 strips, 3/8 [BD-77, BD-78, BD-79] |
| 76x85 | V-BIND-02: 9, 3/4 | 8, 3/4 | 9 strips, 5/8 [BD-80, BD-81, BD-82] | 9 strips, 3/4 [BD-83] | 10 strips, 3/4 [BD-84, BD-85] | 9 strips, 5/8 [BD-86, BD-87, BD-88] |
| 68x68 | V-BIND-07: 8, 3/4 | 7, 1/2 | 8 strips, 5/8 [BD-89, BD-90, BD-91] | 8 strips, 3/4 [BD-92, BD-93] | 8 strips, 5/8 [BD-94, BD-95, BD-96] | 8 strips, 5/8 [BD-97, BD-98, BD-99] |
| 102.5x120 | V-BIND-06: 13, 1 | 11, 1 | failed [F15] | 12 strips, 1 [BD-100, BD-101] | 13 strips, 1 [BD-102] | 12 strips, 7/8 [BD-103, BD-104, BD-105, BD-106] |
| 58x66 | V-BIND-18: 7, 1/2 | 7, 1/2 | 7 strips, 1/2 | 7 strips, 1/2 | 8 strips, 5/8 [BD-107, BD-108, BD-109, BD-110] | 7 strips, 1/2 |
| 24x58 | no vector | 5, 1/2 | 5 strips, 3/8 [BD-111] | 5 strips, 1/2 | 5 strips, 3/8 [BD-112] | 5 strips, 3/8 [BD-113] |

## Batting

Quilter's Paradise sells batting as a roll length on a 120 in bolt; its implied length is set against the batting length.

| Row | MATH.md vector | QREP today | Quilter's Paradise roll 120 | My Favorite Quilt Store (record only) | Stitch Desk | Omni |
| --- | --- | --- | --- | --- | --- | --- |
| 36x52 | V-BATT-02: 44 x 60, crib | 44 x 60 | 1 3/4 yd = 63 in [BT-1, BT-2] | 44 x 60, Crib | 44 x 60, Crib | 44 x 52 [BT-3, BT-4] |
| 50x65 | V-BATT-04: 58 x 73, twin | 58 x 73 | 2 1/8 yd = 76 1/2 in [BT-5, BT-6] | 58 x 73, Twin | 58 x 73, Twin | 58 x 66 [BT-7, BT-8] |
| 60x72 | V-BATT-03: 68 x 80, twin | 68 x 80 | 2 1/4 yd = 81 in [BT-9, BT-10] | 68 x 80, Twin | 68 x 80, Twin | 68 x 76 [BT-11, BT-12] |
| 70x90 | V-BATT-05: 78 x 98, queen | 78 x 98 | 2 3/4 yd = 99 in [BT-13, BT-14] | 78 x 98, Queen | 78 x 98, Queen | 78 x 98 |
| 84x90 | V-BATT-06: 92 x 98, king | 92 x 98 | 2 3/4 yd = 99 in [BT-15, BT-16] | 92 x 98, King | 92 x 98, King | 92 x 100.2 [BT-17, BT-18] |
| 90x108 | V-BATT-07: 98 x 116, king | 98 x 116 | 3 1/4 yd = 117 in [BT-19, BT-20] | 98 x 116, King | 98 x 116, King | 98 x 106.2 [BT-21, BT-22] |
| 92.5x115 | V-BATT-08: 100 1/2 x 123, king | 100 1/2 x 123 | 3 1/2 yd = 126 in [BT-23, BT-24] | 100 1/2 x 123 [BT-25] | 100 1/2 x 123, off the roll [BT-26] | 100 1/2 x 108.6 [BT-27, BT-28] |
| 110x108 | V-BATT-09: 118 x 116, king | 118 x 116 | 3 1/4 yd = 117 in [BT-29, BT-30] | 118 x 116, King | 118 x 116, King | 118.2 x 116 [BT-31, BT-32] |
| 75x90 | V-BATT-01: 83 x 98, queen | 83 x 98 | 2 3/4 yd = 99 in [BT-33, BT-34] | 83 x 98, Queen | 83 x 98, Queen | 83 x 98 |
| 42x52 | V-BATT-13: 50 x 60, twin | 50 x 60 | 1 3/4 yd = 63 in [BT-35, BT-36] | 50 x 60, Twin | 50 x 60, Throw [BT-37] | 50 x 58 [BT-38, BT-39] |
| 76x85 | no vector | 84 x 93 | 2 5/8 yd = 94 1/2 in [BT-40] | 84 x 93, Queen | 84 x 93, Queen | 84 x 93 |
| 68x68 | V-BATT-11: 76 x 76, full | 76 x 76 | 2 1/8 yd = 76 1/2 in [BT-41, BT-42] | 76 x 76, Full | 76 x 76, Full | 76 x 84 [BT-43, BT-44] |
| 102.5x120 | V-BATT-10: 110 1/2 x 128, None | 110 1/2 x 128 | failed [F12] | 110 1/2 x 128 | 110 1/2 x 128, off the roll | 110.7 x 128 [BT-45, BT-46] |
| 58x66 | no vector | 66 x 74 | 2 1/8 yd = 76 1/2 in [BT-47] | 66 x 74, Twin | 66 x 74, Twin | 66 x 74 |
| 24x58 | no vector | 32 x 66 | 1 7/8 yd = 67 1/2 in [BT-48] | 32 x 66, Twin | 32 x 66, Twin | 32 x 66 |

## Borders

Vectors are F4 per piece at U = 40 (strips per band). QREP today cuts one piece per side and buys by area, with no strip count (D-11); its yards are shown at wof 320 and, in brackets, at the default wof 336.

| Row | MATH.md vector | QREP at wof 320 (wof 336) | Quilter's Paradise 40 | Designed to Quilt 40 | Designed to Quilt 40, finished size | Sew Becca 40 | Sew Becca 40, finished size | Quilt Calculator 40 | Quilt Calculator 40, finished size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 36x52-b3.75 | no vector | b1: 1/2 (1/2), 4 pieces | b1: 5 strips, 5/8 [BR-1] | failed [F24] | not run | b1: 4 strips, 3/8 [BR-2] | not run | b1: 5/8 [BR-3] | not run |
| 50x65-b3.75 | no vector | b1: 3/4 (3/4), 4 pieces | b1: 6 strips, 3/4 | b1: 6 strips, 3/4 | not run | b1: 6 strips, 5/8 [BR-4] | not run | b1: 3/4 | not run |
| 60x72-b3.75 | no vector | b1: 3/4 (3/4), 4 pieces | b1: 7 strips, 7/8 [BR-5] | b1: 7 strips, 7/8 [BR-6] | not run | b1: 7 strips, 3/4 | not run | b1: 7/8 [BR-7] | not run |
| 70x90-b3.75 | no vector | b1: 1 (1), 4 pieces | b1: 8 strips, 1 | b1: 8 strips, 1 | not run | b1: 8 strips, 3/4 [BR-8] | not run | b1: 1 1/8 [BR-9] | not run |
| 84x90-b3.75 | no vector | b1: 1 (1), 4 pieces | b1: 9 strips, 1 1/8 [BR-10] | b1: 9 strips, 1 1/8 [BR-11] | not run | b1: 9 strips, 7/8 [BR-12] | not run | b1: 1 1/8 [BR-13] | not run |
| 90x108-b3.75 | no vector | b1: 1 1/4 (1 1/4), 4 pieces | failed [F16] | b1: 10 strips, 1 1/4 | not run | b1: 10 strips, 1 [BR-14] | not run | b1: 1 1/4 | not run |
| 92.5x115-b3.75 | no vector | b1: 1 1/4 (1 1/4), 4 pieces | failed [F17] | b1: 11 strips, 1 3/8 [BR-15] | not run | b1: 10 strips, 1 [BR-16] | not run | b1: 1 3/8 [BR-17] | not run |
| 110x108-b3.75 | no vector | b1: 1 1/4 (1 1/4), 4 pieces | failed [F18] | b1: 11 strips, 1 3/8 [BR-18] | not run | b1: 11 strips, 1 1/8 [BR-19] | not run | b1: 1 3/8 [BR-20] | not run |
| 75x90-b3.75 | V-BORD-01: b1: 10 strips (42 1/2 in) | b1: 1 (1), 4 pieces | b1: 8 strips, 1 [BR-21] | b1: 9 strips, 1 1/8 [BR-22, BR-23] | not run | b1: 8 strips, 3/4 [BR-24, BR-25] | not run | b1: 1 1/8 [BR-26] | not run |
| 42x52-b3.75 | no vector | b1: 3/4 (1/2), 4 pieces | b1: 5 strips, 5/8 [BR-27] | b1: 5 strips, 5/8 [BR-28] | not run | b1: 5 strips, 1/2 [BR-29] | not run | b1: 5/8 [BR-30] | not run |
| 76x85-b3.75 | no vector | b1: 1 (1), 4 pieces | b1: 8 strips, 1 | b1: 8 strips, 1 | not run | b1: 8 strips, 3/4 [BR-31] | not run | b1: 1 1/8 [BR-32] | not run |
| 68x68-b3.75 | no vector | b1: 1 (3/4), 4 pieces | b1: 7 strips, 7/8 [BR-33] | b1: 7 strips, 7/8 [BR-34] | not run | b1: 7 strips, 3/4 [BR-35] | not run | b1: 7/8 [BR-36] | not run |
| 102.5x120-b3.75 | no vector | b1: 1 1/2 (1 1/4), 4 pieces | failed [F19] | b1: 12 strips, 1 1/2 | not run | b1: 11 strips, 1 1/8 [BR-37] | not run | b1: 1 1/2 | not run |
| 58x66-b3.75 | no vector | b1: 3/4 (3/4), 4 pieces | b1: 6 strips, 3/4 | b1: 7 strips, 7/8 [BR-38] | not run | b1: 6 strips, 5/8 [BR-39] | not run | b1: 7/8 [BR-40] | not run |
| 24x58-b3.75 | no vector | b1: 1/2 (1/2), 4 pieces | b1: 4 strips, 1/2 | b1: 4 strips, 1/2 | not run | b1: 4 strips, 3/8 [BR-41] | not run | b1: 5/8 [BR-42] | not run |
| V-BORD-02 | V-BORD-02: b1: 6 strips (15 in) | b1: 1/2 (1/2), 4 pieces | b1: 5 strips, 3/8 [BR-43, BR-44] | b1: 5 strips, 3/8 [BR-45, BR-46] | not run | b1: 5 strips, 1/4 [BR-47, BR-48] | not run | b1: 3/8 [BR-49] | not run |
| V-BORD-03 | V-BORD-03: b1: 8 strips (20 in); b2: 8 strips (44 in) | b1: 1/2 (1/2), 4 pieces; b2: 1 1/4 (1 1/4), 4 pieces | b1: 7 strips, 1/2; b2: 8 strips, 1 1/4 [BR-50] | n/a (one border field) | not run | n/a (one border field) | not run | b1: 5/8; b2: 1 1/4 [BR-51] | not run |
| V-BORD-04 | V-BORD-04: b1: 2 strips (3 in) | b1: 1/4 (1/4), 4 pieces | b1: 1 strips, 1/8 [BR-52, BR-53] | b1: 1 strips, 1/8 [BR-54, BR-55] | not run | b1: 1 strips, 1/8 [BR-56, BR-57] | not run | b1: 1/8 [BR-58] | not run |

## Piece count spot check

| Row | MATH.md vector | Quilter's Paradise |
| --- | --- | --- |
| V-YIELD-01@40 | 16 pieces (MATH.md line 574: per = floor(40 / 2.5) = 16 (320 // 20)) | 16 pieces (turned 16) |
| V-YIELD-02@40 | 16 pieces (MATH.md line 589: 4 1/2 in strips, per = floor(40 / 2.5) = 16) | 16 pieces (turned 8) |
| V-YIELD-02@42 | 16 pieces (MATH.md line 583: 4 1/2 in strips, per = floor(42 / 2.5) = 16 (336 // 20)) | 16 pieces (turned 9) |

## Labeled differences

Comparisons: n = 799; matches n = 415; differences n = 384 (explained n = 344, unexplained n = 0, record only n = 40).

A difference is explained only when the calculator's own rule (its MATH.md parameter set, or its page model in calc_rules) reproduces the shown value. Its labels name the parameters whose one-at-a-time switch from the reference set (MATH.md defaults against a vector, today's set against QREP) changes the value; 'jointly' marks parameters that only act together, named by switching each back from the calculator's set.

| ID | Row | Calculator | Value | Shown | Against | Target | Status | Labels | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BK-1 | 36x52 | qp_backing @42 | yards | 2 1/2 | V-BACK-03 | 2 3/4 | explained | allowance | - |
| BK-2 | 36x52 | qp_backing @42 | yards | 2 1/2 | QREP today | 3 1/2 | explained | orientation (D-01) | - |
| BK-3 | 36x52 | qp_backing @40 | yards | 2 1/2 | QREP at wof 320 | 3 1/2 | explained | orientation (D-01) | - |
| BK-4 | 36x52 | mfqs_backing @42 | yards | 2 1/2 | V-BACK-03 | 2 3/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-5 | 36x52 | mfqs_backing @42 | yards | 2 1/2 | QREP today | 3 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-6 | 36x52 | nqc @40 | yards | 2 1/2 | QREP at wof 320 | 3 1/2 | explained | orientation (D-01) | - |
| BK-7 | 36x52 | stitchdesk_backing @42 | yards | 2 1/2 | V-BACK-03 | 2 3/4 | explained | allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-8 | 36x52 | stitchdesk_backing @42 | yards | 2 1/2 | QREP today | 3 1/2 | explained | orientation (D-01), fabric width, rounding increment or thirds, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-9 | 36x52 | omni_backing @42 | yards | 2.45 | V-BACK-03 | 2 3/4 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-10 | 36x52 | omni_backing @42 | yards | 2.45 | QREP today | 3 1/2 | explained | orientation (D-01), rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-11 | 50x65 | qp_backing @42 | yards | 3 1/4 | V-BACK-04 | 3 1/2 | explained | allowance | - |
| BK-12 | 50x65 | qp_backing @42 | yards | 3 1/4 | QREP today | 4 1/4 | explained | orientation (D-01) | - |
| BK-13 | 50x65 | qp_backing @40 | yards | 3 1/4 | QREP at wof 320 | 4 1/4 | explained | orientation (D-01) | - |
| BK-14 | 50x65 | mfqs_backing @42 | yards | 3 1/4 | V-BACK-04 | 3 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-15 | 50x65 | mfqs_backing @42 | yards | 3 1/4 | QREP today | 4 1/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-16 | 50x65 | nqc @40 | yards | 3 1/4 | QREP at wof 320 | 4 1/4 | explained | orientation (D-01) | - |
| BK-17 | 50x65 | stitchdesk_backing @42 | yards | 3 1/4 | V-BACK-04 | 3 1/2 | explained | allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-18 | 50x65 | stitchdesk_backing @42 | yards | 3 1/4 | QREP today | 4 1/4 | explained | orientation (D-01), fabric width, rounding increment or thirds, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-19 | 50x65 | omni_backing @42 | yards | 3.23 | V-BACK-04 | 3 1/2 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-20 | 50x65 | omni_backing @42 | yards | 3.23 | QREP today | 4 1/4 | explained | orientation (D-01), rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-21 | 60x72 | qp_backing @42 | yards | 3 7/8 | V-BACK-02 | 4 1/4 | explained | allowance, rounding increment or thirds | - |
| BK-22 | 60x72 | qp_backing @42 | yards | 3 7/8 | QREP today | 4 1/2 | explained | orientation (D-01), rounding increment or thirds | - |
| BK-23 | 60x72 | qp_backing @40 | yards | 4 1/2 | V-BACK-19 | 4 3/4 | explained | allowance | - |
| BK-24 | 60x72 | mfqs_backing @42 | yards | 3 7/8 | V-BACK-02 | 4 1/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-25 | 60x72 | mfqs_backing @42 | yards | 3 7/8 | QREP today | 4 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-26 | 60x72 | nqc @40 | yards | 4 1/2 | V-BACK-19 | 4 3/4 | explained | allowance | - |
| BK-27 | 60x72 | stitchdesk_backing @42 | yards | 4 1/2 | V-BACK-02 | 4 1/4 | explained | orientation, allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-28 | 60x72 | omni_backing @42 | yards | 3.78 | V-BACK-02 | 4 1/4 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-29 | 60x72 | omni_backing @42 | yards | 3.78 | QREP today | 4 1/2 | explained | orientation (D-01), rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-30 | 70x90 | qp_backing @42 | yards | 5 1/2 | V-BACK-05 | 5 3/4 | explained | allowance | - |
| BK-31 | 70x90 | mfqs_backing @42 | yards | 5 1/2 | V-BACK-05 | 5 3/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-32 | 70x90 | stitchdesk_backing @42 | yards | 5 1/2 | V-BACK-05 | 5 3/4 | explained | allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-33 | 70x90 | omni_backing @42 | yards | 5.45 | V-BACK-05 | 5 3/4 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-34 | 70x90 | omni_backing @42 | yards | 5.45 | QREP today | 5 1/2 | explained | rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-35 | 84x90 | qp_backing @42 | yards | 7 2/3 | V-BACK-06 | 8 | explained | allowance, rounding increment or thirds | - |
| BK-36 | 84x90 | qp_backing @42 | yards | 7 2/3 | QREP today | 8 1/4 | explained | orientation (D-01), rounding increment or thirds | - |
| BK-37 | 84x90 | qp_backing @40 | yards | 7 2/3 | QREP at wof 320 | 8 1/4 | explained | orientation (D-01), rounding increment or thirds | - |
| BK-38 | 84x90 | mfqs_backing @42 | yards | 7 3/4 | V-BACK-06 | 8 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-39 | 84x90 | mfqs_backing @42 | yards | 7 3/4 | QREP today | 8 1/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-40 | 84x90 | nqc @40 | yards | 7 3/4 | QREP at wof 320 | 8 1/4 | explained | orientation (D-01) | - |
| BK-41 | 84x90 | stitchdesk_backing @42 | yards | 7 3/4 | V-BACK-06 | 8 | explained | allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-42 | 84x90 | stitchdesk_backing @42 | yards | 7 3/4 | QREP today | 8 1/4 | explained | orientation (D-01), fabric width, rounding increment or thirds, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-43 | 84x90 | omni_backing @42 | yards | 7.67 | V-BACK-06 | 8 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-44 | 84x90 | omni_backing @42 | yards | 7.67 | QREP today | 8 1/4 | explained | orientation (D-01), rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-45 | 90x108 | qp_backing @42 | yards | 8 1/4 | V-BACK-07 | 8 1/2 | explained | allowance | - |
| BK-46 | 90x108 | qp_backing @42 | yards | 8 1/4 | QREP today | 9 3/4 | explained | orientation (D-01) | - |
| BK-47 | 90x108 | qp_backing @40 | yards | 8 1/4 | QREP at wof 320 | 9 3/4 | explained | orientation (D-01) | - |
| BK-48 | 90x108 | mfqs_backing @42 | yards | 8 1/4 | V-BACK-07 | 8 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-49 | 90x108 | mfqs_backing @42 | yards | 8 1/4 | QREP today | 9 3/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-50 | 90x108 | nqc @40 | yards | 8 1/4 | QREP at wof 320 | 9 3/4 | explained | orientation (D-01) | - |
| BK-51 | 90x108 | stitchdesk_backing @42 | yards | 8 1/4 | V-BACK-07 | 8 1/2 | explained | allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-52 | 90x108 | stitchdesk_backing @42 | yards | 8 1/4 | QREP today | 9 3/4 | explained | orientation (D-01), fabric width, rounding increment or thirds, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-53 | 90x108 | omni_backing @42 | yards | 8.17 | V-BACK-07 | 8 1/2 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-54 | 90x108 | omni_backing @42 | yards | 8.17 | QREP today | 9 3/4 | explained | orientation (D-01), rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-55 | 92.5x115 | qp_backing @42 | yards | 8 3/8 | V-BACK-01 | 8 3/4 | explained | allowance, rounding increment or thirds | - |
| BK-56 | 92.5x115 | qp_backing @42 | yards | 8 3/8 | QREP today | 10 1/4 | explained | orientation (D-01), rounding increment or thirds | - |
| BK-57 | 92.5x115 | qp_backing @40 | yards | 10 1/4 | V-BACK-18 | 10 1/2 | explained | allowance | - |
| BK-58 | 92.5x115 | mfqs_backing @42 | yards | 8 3/8 | V-BACK-01 | 8 3/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-59 | 92.5x115 | mfqs_backing @42 | yards | 8 3/8 | QREP today | 10 1/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-60 | 92.5x115 | nqc @40 | yards | 10 1/4 | V-BACK-18 | 10 1/2 | explained | allowance | - |
| BK-61 | 92.5x115 | stitchdesk_backing @42 | yards | 10 1/4 | V-BACK-01 | 8 3/4 | explained | orientation, allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-62 | 92.5x115 | omni_backing @42 | yards | 8.38 | V-BACK-01 | 8 3/4 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-63 | 92.5x115 | omni_backing @42 | yards | 8.38 | QREP today | 10 1/4 | explained | orientation (D-01), rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-64 | 110x108 | qp_backing @42 | yards | 9 3/4 | V-BACK-08 | 10 | explained | allowance | - |
| BK-65 | 110x108 | mfqs_backing @42 | yards | 9 3/4 | V-BACK-08 | 10 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-66 | 110x108 | stitchdesk_backing @42 | yards | 9 7/8 | V-BACK-08 | 10 | explained | orientation, allowance, rounding increment or thirds | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-67 | 110x108 | stitchdesk_backing @42 | yards | 9 7/8 | QREP today | 9 3/4 | explained | orientation (D-01), rounding increment or thirds | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-68 | 110x108 | omni_backing @42 | yards | 9.67 | V-BACK-08 | 10 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-69 | 110x108 | omni_backing @42 | yards | 9.67 | QREP today | 9 3/4 | explained | rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-70 | 75x90 | qp_backing @42 | yards | 5 1/2 | V-BACK-09 | 5 3/4 | explained | allowance | - |
| BK-71 | 75x90 | qp_backing @40 | yards | 7 | V-BACK-20 | 7 1/4 | explained | allowance | - |
| BK-72 | 75x90 | qp_backing @40 | yards | 7 | QREP at wof 320 | 8 1/4 | explained | orientation (D-01) | - |
| BK-73 | 75x90 | mfqs_backing @42 | yards | 7 | V-BACK-09 | 5 3/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-74 | 75x90 | mfqs_backing @42 | yards | 7 | QREP today | 5 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-75 | 75x90 | mfqs_backing @42 | panels | 3 | V-BACK-09 | 2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-76 | 75x90 | mfqs_backing @42 | panels | 3 | QREP today | 2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-77 | 75x90 | nqc @40 | yards | 7 | V-BACK-20 | 7 1/4 | explained | allowance | - |
| BK-78 | 75x90 | nqc @40 | yards | 7 | QREP at wof 320 | 8 1/4 | explained | orientation (D-01) | - |
| BK-79 | 75x90 | stitchdesk_backing @42 | yards | 7 | V-BACK-09 | 5 3/4 | explained | orientation, allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-80 | 75x90 | stitchdesk_backing @42 | yards | 7 | QREP today | 5 1/2 | explained | orientation (D-01), fabric width, rounding increment or thirds, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-81 | 75x90 | stitchdesk_backing @42 | panels | 3 | V-BACK-09 | 2 | explained | orientation, fabric width, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-82 | 75x90 | stitchdesk_backing @42 | panels | 3 | QREP today | 2 | explained | orientation (D-01), fabric width, seam loss, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-83 | 75x90 | omni_backing @42 | yards | 5.45 | V-BACK-09 | 5 3/4 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-84 | 75x90 | omni_backing @42 | yards | 5.45 | QREP today | 5 1/2 | explained | rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-85 | 42x52 | qp_backing @42 | yards | 2 7/8 | V-BACK-11 | 3 1/4 | explained | allowance, rounding increment or thirds | - |
| BK-86 | 42x52 | qp_backing @42 | yards | 2 7/8 | QREP today | 3 1/2 | explained | orientation (D-01), rounding increment or thirds | - |
| BK-87 | 42x52 | qp_backing @40 | yards | 2 7/8 | QREP at wof 320 | 3 1/2 | explained | orientation (D-01), rounding increment or thirds | - |
| BK-88 | 42x52 | mfqs_backing @42 | yards | 2 7/8 | V-BACK-11 | 3 1/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-89 | 42x52 | mfqs_backing @42 | yards | 2 7/8 | QREP today | 3 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-90 | 42x52 | nqc @40 | yards | 3 | QREP at wof 320 | 3 1/2 | explained | orientation (D-01) | - |
| BK-91 | 42x52 | stitchdesk_backing @42 | yards | 2 7/8 | V-BACK-11 | 3 1/4 | explained | allowance, rounding increment or thirds | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-92 | 42x52 | stitchdesk_backing @42 | yards | 2 7/8 | QREP today | 3 1/2 | explained | orientation (D-01), rounding increment or thirds | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-93 | 42x52 | omni_backing @42 | yards | 2.78 | V-BACK-11 | 3 1/4 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-94 | 42x52 | omni_backing @42 | yards | 2.78 | QREP today | 3 1/2 | explained | orientation (D-01), rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-95 | 76x85 | qp_backing @42 | yards | 7 | V-BACK-10 | 7 1/4 | explained | allowance | - |
| BK-96 | 76x85 | qp_backing @42 | yards | 7 | QREP today | 5 1/4 | explained | orientation (D-01) | - |
| BK-97 | 76x85 | qp_backing @42 | panels | 3 | QREP today | 2 | explained | orientation (D-01) | - |
| BK-98 | 76x85 | qp_backing @40 | yards | 7 | QREP at wof 320 | 7 3/4 | explained | orientation (D-01) | - |
| BK-99 | 76x85 | mfqs_backing @42 | yards | 7 | V-BACK-10 | 7 1/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-100 | 76x85 | mfqs_backing @42 | yards | 7 | QREP today | 5 1/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-101 | 76x85 | mfqs_backing @42 | panels | 3 | QREP today | 2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-102 | 76x85 | nqc @40 | yards | 7 | QREP at wof 320 | 7 3/4 | explained | orientation (D-01) | - |
| BK-103 | 76x85 | stitchdesk_backing @42 | yards | 7 | V-BACK-10 | 7 1/4 | explained | allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-104 | 76x85 | stitchdesk_backing @42 | yards | 7 | QREP today | 5 1/4 | explained | orientation (D-01), fabric width, rounding increment or thirds, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-105 | 76x85 | stitchdesk_backing @42 | panels | 3 | QREP today | 2 | explained | orientation (D-01), fabric width, seam loss, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-106 | 76x85 | omni_backing @42 | yards | 5.17 | V-BACK-10 | 7 1/4 | explained | orientation, seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-107 | 76x85 | omni_backing @42 | yards | 5.17 | QREP today | 5 1/4 | explained | rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-108 | 76x85 | omni_backing @42 | panels | 2 | V-BACK-10 | 3 | explained | orientation, seam loss, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-109 | 68x68 | qp_backing @42 | yards | 4 1/4 | V-BACK-13 | 4 1/2 | explained | allowance | - |
| BK-110 | 68x68 | mfqs_backing @42 | yards | 4 1/4 | V-BACK-13 | 4 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-111 | 68x68 | stitchdesk_backing @42 | yards | 4 1/4 | V-BACK-13 | 4 1/2 | explained | allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-112 | 68x68 | omni_backing @42 | yards | 4.23 | V-BACK-13 | 4 1/2 | explained | orientation, seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-113 | 68x68 | omni_backing @42 | yards | 4.23 | QREP today | 4 1/4 | explained | orientation (D-01), rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-114 | 102.5x120 | mfqs_backing @42 | yards | 10 3/4 | V-BACK-16 | 11 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-115 | 102.5x120 | stitchdesk_backing @42 | yards | 10 3/4 | V-BACK-16 | 11 | explained | allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-116 | 102.5x120 | omni_backing @42 | yards | 10.67 | V-BACK-16 | 11 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-117 | 102.5x120 | omni_backing @42 | yards | 10.67 | QREP today | 10 3/4 | explained | rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-118 | 58x66 | qp_backing @42 | yards | 3 2/3 | V-BACK-23 | 4 | explained | allowance, rounding increment or thirds | - |
| BK-119 | 58x66 | qp_backing @42 | yards | 3 2/3 | QREP today | 4 1/4 | explained | orientation (D-01), rounding increment or thirds | - |
| BK-120 | 58x66 | qp_backing @40 | yards | 3 2/3 | QREP at wof 320 | 4 1/4 | explained | orientation (D-01), rounding increment or thirds | - |
| BK-121 | 58x66 | mfqs_backing @42 | yards | 3 3/4 | V-BACK-23 | 4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-122 | 58x66 | mfqs_backing @42 | yards | 3 3/4 | QREP today | 4 1/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-123 | 58x66 | nqc @40 | yards | 3 3/4 | QREP at wof 320 | 4 1/4 | explained | orientation (D-01) | - |
| BK-124 | 58x66 | stitchdesk_backing @42 | yards | 3 3/4 | V-BACK-23 | 4 | explained | allowance | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-125 | 58x66 | stitchdesk_backing @42 | yards | 3 3/4 | QREP today | 4 1/4 | explained | orientation (D-01), fabric width, rounding increment or thirds, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-126 | 58x66 | omni_backing @42 | yards | 3.67 | V-BACK-23 | 4 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-127 | 58x66 | omni_backing @42 | yards | 3.67 | QREP today | 4 1/4 | explained | orientation (D-01), rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-128 | 24x58 | qp_backing @42 | yards | 1 7/8 | V-BACK-14 | 2 | explained | rounding increment or thirds | - |
| BK-129 | 24x58 | qp_backing @42 | yards | 1 7/8 | QREP today | 2 | explained | rounding increment or thirds | - |
| BK-130 | 24x58 | qp_backing @40 | yards | 1 7/8 | QREP at wof 320 | 2 | explained | rounding increment or thirds | - |
| BK-131 | 24x58 | mfqs_backing @42 | yards | 1 7/8 | V-BACK-14 | 2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-132 | 24x58 | mfqs_backing @42 | yards | 1 7/8 | QREP today | 2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| BK-133 | 24x58 | stitchdesk_backing @42 | yards | 1 7/8 | V-BACK-14 | 2 | explained | orientation, allowance, rounding increment or thirds | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-134 | 24x58 | stitchdesk_backing @42 | yards | 1 7/8 | QREP today | 2 | explained | orientation (D-01), rounding increment or thirds | labels from the proxy set (proxy: B 40, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BK-135 | 24x58 | stitchdesk_backing @42 | panels | 2 | V-BACK-14 | 1 | explained | orientation, fabric width, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-136 | 24x58 | stitchdesk_backing @42 | panels | 2 | QREP today | 1 | explained | orientation (D-01), fabric width, seam loss, page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1)) | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BK-137 | 24x58 | omni_backing @42 | yards | 1.84 | V-BACK-14 | 2 | explained | seam loss, allowance, rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BK-138 | 24x58 | omni_backing @42 | yards | 1.84 | QREP today | 2 | explained | rounding increment or thirds, page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01 | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| WB-1 | 36x52 | mfqs_backing @42 | yards | 1 1/4 | V-WIDE-10 | 1 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| WB-2 | 36x52 | nqc @108 | yards | 1 1/4 | V-WIDE-10 | 1 1/2 | explained | allowance | - |
| WB-3 | 36x52 | stitchdesk_backing @42 | yards | 1 1/4 | V-WIDE-10 | 1 1/2 | explained | allowance, rounding increment or thirds | labels from the proxy set (proxy: B 106, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| WB-4 | 50x65 | mfqs_backing @42 | yards | 1 5/8 | V-WIDE-10 | 1 3/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| WB-5 | 50x65 | stitchdesk_backing @42 | yards | 1 5/8 | V-WIDE-10 | 1 3/4 | explained | allowance, rounding increment or thirds (jointly) | labels from the proxy set (proxy: B 106, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| WB-6 | 60x72 | mfqs_backing @42 | yards | 2 | V-WIDE-02 | 2 1/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| WB-7 | 60x72 | nqc @108 | yards | 2 | V-WIDE-02 | 2 1/4 | explained | allowance | - |
| WB-8 | 60x72 | stitchdesk_backing @42 | yards | 2 | V-WIDE-02 | 2 1/4 | explained | allowance, rounding increment or thirds | labels from the proxy set (proxy: B 106, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| WB-9 | 70x90 | mfqs_backing @42 | yards | 2 1/4 | V-WIDE-10 | 2 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| WB-10 | 70x90 | nqc @108 | yards | 2 1/4 | V-WIDE-10 | 2 1/2 | explained | allowance | - |
| WB-11 | 70x90 | stitchdesk_backing @42 | yards | 2 1/4 | V-WIDE-10 | 2 1/2 | explained | allowance, rounding increment or thirds | labels from the proxy set (proxy: B 106, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| WB-12 | 84x90 | mfqs_backing @42 | yards | 2 5/8 | V-WIDE-10 | 2 3/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| WB-13 | 84x90 | stitchdesk_backing @42 | yards | 2 5/8 | V-WIDE-10 | 2 3/4 | explained | allowance, rounding increment or thirds (jointly) | labels from the proxy set (proxy: B 106, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| WB-14 | 90x108 | mfqs_backing @42 | yards | 3 1/4 | V-WIDE-04 | 3 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| WB-15 | 90x108 | nqc @108 | yards | 3 1/4 | V-WIDE-04 | 3 1/2 | explained | allowance | - |
| WB-16 | 90x108 | stitchdesk_backing @42 | yards | 3 1/4 | V-WIDE-04 | 3 1/2 | explained | allowance, rounding increment or thirds | labels from the proxy set (proxy: B 106, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| WB-17 | 92.5x115 | mfqs_backing @42 | yards | 3 1/2 | V-WIDE-01 | 3 3/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| WB-18 | 92.5x115 | nqc @108 | yards | 3 1/2 | V-WIDE-01 | 3 3/4 | explained | allowance | - |
| WB-19 | 92.5x115 | stitchdesk_backing @42 | yards | 3 1/2 | V-WIDE-01 | 3 3/4 | explained | allowance, rounding increment or thirds | labels from the proxy set (proxy: B 106, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| WB-20 | 110x108 | nqc @118 | yards | 3 1/4 | V-WIDE-05 | 3 1/2 | explained | allowance | - |
| WB-21 | 75x90 | mfqs_backing @42 | yards | 2 3/8 | V-WIDE-08 | 2 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| WB-22 | 75x90 | stitchdesk_backing @42 | yards | 2 3/8 | V-WIDE-08 | 2 1/2 | explained | allowance, rounding increment or thirds (jointly) | labels from the proxy set (proxy: B 106, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| WB-23 | 42x52 | mfqs_backing @42 | yards | 1 1/2 | V-WIDE-09 | 1 3/4 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| WB-24 | 42x52 | nqc @108 | yards | 1 1/2 | V-WIDE-09 | 1 3/4 | explained | allowance | - |
| WB-25 | 42x52 | stitchdesk_backing @42 | yards | 1 1/2 | V-WIDE-09 | 1 3/4 | explained | allowance, rounding increment or thirds | labels from the proxy set (proxy: B 106, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| WB-26 | 76x85 | mfqs_backing @42 | yards | 2 3/8 | V-WIDE-03 | 2 1/2 | record only | - | calc_rules.mfqs_backing reproduces the shown value |
| WB-27 | 76x85 | stitchdesk_backing @42 | yards | 2 3/8 | V-WIDE-03 | 2 1/2 | explained | allowance, rounding increment or thirds (jointly) | labels from the proxy set (proxy: B 106, overhang_per_side 4, s 1, allowance_pieced 0, allowance_one 0, increment eighth, keep least_total), which gives the page model's value on this row |
| BD-1 | 36x52 | qp_binding @40 | yards | 3/8 | V-BIND-11 | 1/2 | explained | rounding increment or thirds | - |
| BD-2 | 36x52 | qp_binding @40 | yards | 3/8 | QREP today | 1/2 | explained | rounding increment or thirds | - |
| BD-3 | 36x52 | stitchdesk_binding @42 | strips | 6 | V-BIND-11 | 5 | explained | binding extra length | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-4 | 36x52 | stitchdesk_binding @42 | strips | 6 | QREP today | 5 | explained | fabric width, binding extra length, join loss (D-08) (jointly) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-5 | 36x52 | quiltkeeper_binding @40 | yards | 3/8 | V-BIND-11 | 1/2 | explained | rounding increment or thirds | - |
| BD-6 | 36x52 | quiltkeeper_binding @40 | yards | 3/8 | QREP today | 1/2 | explained | rounding increment or thirds | - |
| BD-7 | 50x65 | qp_binding @40 | strips | 7 | QREP today | 6 | explained | join loss (D-08) | - |
| BD-8 | 50x65 | nqc @40 | strips | 7 | QREP today | 6 | explained | fabric width, binding extra length (jointly) | - |
| BD-9 | 50x65 | stitchdesk_binding @42 | strips | 7 | QREP today | 6 | explained | join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-10 | 50x65 | quiltkeeper_binding @40 | strips | 6 | V-BIND-12 | 7 | explained | join loss | - |
| BD-11 | 60x72 | qp_binding @40 | strips | 8 | QREP today | 7 | explained | fabric width, join loss (D-08) (jointly) | - |
| BD-12 | 60x72 | qp_binding @40 | yards | 5/8 | V-BIND-13 | 3/4 | explained | rounding increment or thirds | - |
| BD-13 | 60x72 | qp_binding @40 | yards | 5/8 | QREP today | 1/2 | explained | fabric width, join loss (D-08), rounding increment or thirds (jointly) | - |
| BD-14 | 60x72 | nqc @40 | strips | 7 | V-BIND-13 | 8 | explained | join loss | - |
| BD-15 | 60x72 | nqc @40 | yards | 1/2 | V-BIND-13 | 3/4 | explained | join loss | - |
| BD-16 | 60x72 | stitchdesk_binding @42 | strips | 8 | QREP today | 7 | explained | binding extra length, join loss, page rule: 4 x strip width + 10 in extra, 1/2 in more per join, usable = fabric width - 2 | labels list the page rule's differences from the reference (calc_rules.stitchdesk_binding); no MATH.md parameter set reproduces this row |
| BD-17 | 60x72 | stitchdesk_binding @42 | yards | 5/8 | V-BIND-13 | 3/4 | explained | rounding increment or thirds | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-18 | 60x72 | stitchdesk_binding @42 | yards | 5/8 | QREP today | 1/2 | explained | rounding increment or thirds (jointly) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-19 | 60x72 | quiltkeeper_binding @40 | strips | 7 | V-BIND-13 | 8 | explained | join loss | - |
| BD-20 | 60x72 | quiltkeeper_binding @40 | yards | 1/2 | V-BIND-13 | 3/4 | explained | join loss, rounding increment or thirds | - |
| BD-21 | 70x90 | qp_binding @40 | strips | 9 | QREP today | 8 | explained | fabric width, join loss (D-08) | - |
| BD-22 | 70x90 | qp_binding @40 | yards | 5/8 | V-BIND-14 | 3/4 | explained | rounding increment or thirds | - |
| BD-23 | 70x90 | qp_binding @40 | yards | 5/8 | QREP today | 3/4 | explained | rounding increment or thirds | - |
| BD-24 | 70x90 | nqc @40 | strips | 9 | QREP today | 8 | explained | fabric width | - |
| BD-25 | 70x90 | stitchdesk_binding @42 | strips | 10 | V-BIND-14 | 9 | explained | binding extra length | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-26 | 70x90 | stitchdesk_binding @42 | strips | 10 | QREP today | 8 | explained | fabric width, binding extra length, join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-27 | 70x90 | quiltkeeper_binding @40 | strips | 9 | QREP today | 8 | explained | fabric width | - |
| BD-28 | 70x90 | quiltkeeper_binding @40 | yards | 5/8 | V-BIND-14 | 3/4 | explained | rounding increment or thirds | - |
| BD-29 | 70x90 | quiltkeeper_binding @40 | yards | 5/8 | QREP today | 3/4 | explained | rounding increment or thirds | - |
| BD-30 | 84x90 | qp_binding @40 | strips | 10 | QREP today | 9 | explained | join loss (D-08) | - |
| BD-31 | 84x90 | nqc @40 | strips | 9 | V-BIND-15 | 10 | explained | join loss | - |
| BD-32 | 84x90 | stitchdesk_binding @42 | strips | 10 | QREP today | 9 | explained | join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-33 | 84x90 | quiltkeeper_binding @40 | strips | 9 | V-BIND-15 | 10 | explained | join loss | - |
| BD-34 | 84x90 | quiltkeeper_binding @40 | yards | 5/8 | V-BIND-15 | 3/4 | explained | join loss, rounding increment or thirds (jointly) | - |
| BD-35 | 84x90 | quiltkeeper_binding @40 | yards | 5/8 | QREP today | 3/4 | explained | rounding increment or thirds | - |
| BD-36 | 90x108 | qp_binding @40 | strips | 11 | QREP today | 10 | explained | fabric width, join loss (D-08) | - |
| BD-37 | 90x108 | qp_binding @40 | yards | 7/8 | V-BIND-16 | 1 | explained | rounding increment or thirds | - |
| BD-38 | 90x108 | qp_binding @40 | yards | 7/8 | QREP today | 3/4 | explained | fabric width, join loss (D-08) | - |
| BD-39 | 90x108 | nqc @40 | strips | 11 | QREP today | 10 | explained | fabric width | - |
| BD-40 | 90x108 | nqc @40 | yards | 1 | QREP today | 3/4 | explained | fabric width | - |
| BD-41 | 90x108 | stitchdesk_binding @42 | strips | 12 | V-BIND-16 | 11 | explained | binding extra length | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-42 | 90x108 | stitchdesk_binding @42 | strips | 12 | QREP today | 10 | explained | fabric width, join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-43 | 90x108 | stitchdesk_binding @42 | yards | 7/8 | V-BIND-16 | 1 | explained | rounding increment or thirds | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-44 | 90x108 | stitchdesk_binding @42 | yards | 7/8 | QREP today | 3/4 | explained | fabric width, join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-45 | 90x108 | quiltkeeper_binding @40 | strips | 11 | QREP today | 10 | explained | fabric width | - |
| BD-46 | 90x108 | quiltkeeper_binding @40 | yards | 7/8 | V-BIND-16 | 1 | explained | rounding increment or thirds | - |
| BD-47 | 90x108 | quiltkeeper_binding @40 | yards | 7/8 | QREP today | 3/4 | explained | fabric width | - |
| BD-48 | 92.5x115 | qp_binding @40 | strips | 12 | QREP today | 11 | explained | fabric width, join loss (D-08) (jointly) | - |
| BD-49 | 92.5x115 | qp_binding @40 | yards | 7/8 | V-BIND-05 | 1 | explained | rounding increment or thirds | - |
| BD-50 | 92.5x115 | qp_binding @40 | yards | 7/8 | QREP today | 1 | explained | rounding increment or thirds | - |
| BD-51 | 92.5x115 | nqc @40 | strips | 11 | V-BIND-05 | 12 | explained | join loss | - |
| BD-52 | 92.5x115 | stitchdesk_binding @42 | strips | 12 | QREP today | 11 | explained | join loss (D-08) (jointly) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-53 | 92.5x115 | stitchdesk_binding @42 | yards | 7/8 | V-BIND-05 | 1 | explained | rounding increment or thirds | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-54 | 92.5x115 | stitchdesk_binding @42 | yards | 7/8 | QREP today | 1 | explained | rounding increment or thirds | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-55 | 92.5x115 | quiltkeeper_binding @40 | strips | 11 | V-BIND-05 | 12 | explained | join loss | - |
| BD-56 | 92.5x115 | quiltkeeper_binding @40 | yards | 7/8 | V-BIND-05 | 1 | explained | rounding increment or thirds | - |
| BD-57 | 92.5x115 | quiltkeeper_binding @40 | yards | 7/8 | QREP today | 1 | explained | rounding increment or thirds | - |
| BD-58 | 110x108 | qp_binding @40 | strips | 12 | QREP today | 11 | explained | fabric width, join loss (D-08) | - |
| BD-59 | 110x108 | qp_binding @40 | yards | 7/8 | V-BIND-17 | 1 | explained | rounding increment or thirds | - |
| BD-60 | 110x108 | qp_binding @40 | yards | 7/8 | QREP today | 1 | explained | rounding increment or thirds | - |
| BD-61 | 110x108 | nqc @40 | strips | 12 | QREP today | 11 | explained | fabric width | - |
| BD-62 | 110x108 | stitchdesk_binding @42 | strips | 13 | V-BIND-17 | 12 | explained | binding extra length | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-63 | 110x108 | stitchdesk_binding @42 | strips | 13 | QREP today | 11 | explained | fabric width, join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-64 | 110x108 | quiltkeeper_binding @40 | strips | 12 | QREP today | 11 | explained | fabric width | - |
| BD-65 | 110x108 | quiltkeeper_binding @40 | yards | 7/8 | V-BIND-17 | 1 | explained | rounding increment or thirds | - |
| BD-66 | 110x108 | quiltkeeper_binding @40 | yards | 7/8 | QREP today | 1 | explained | rounding increment or thirds | - |
| BD-67 | 75x90 | qp_binding @40 | strips | 10 | QREP today | 9 | explained | fabric width, join loss (D-08) (jointly) | - |
| BD-68 | 75x90 | nqc @40 | strips | 9 | V-BIND-01 | 10 | explained | join loss | - |
| BD-69 | 75x90 | stitchdesk_binding @42 | strips | 10 | V-BIND-09 | 9 | explained | fabric width | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-70 | 75x90 | stitchdesk_binding @42 | strips | 10 | QREP today | 9 | explained | fabric width, join loss (D-08) (jointly) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-71 | 75x90 | quiltkeeper_binding @40 | strips | 9 | V-BIND-01 | 10 | explained | join loss | - |
| BD-72 | 75x90 | quiltkeeper_binding @40 | yards | 5/8 | V-BIND-01 | 3/4 | explained | join loss, rounding increment or thirds (jointly) | - |
| BD-73 | 75x90 | quiltkeeper_binding @40 | yards | 5/8 | QREP today | 3/4 | explained | rounding increment or thirds | - |
| BD-74 | 42x52 | qp_binding @40 | strips | 6 | QREP today | 5 | explained | join loss (D-08) | - |
| BD-75 | 42x52 | nqc @40 | strips | 5 | V-BIND-10 | 6 | explained | join loss | - |
| BD-76 | 42x52 | stitchdesk_binding @42 | strips | 6 | QREP today | 5 | explained | join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-77 | 42x52 | quiltkeeper_binding @40 | strips | 5 | V-BIND-10 | 6 | explained | join loss | - |
| BD-78 | 42x52 | quiltkeeper_binding @40 | yards | 3/8 | V-BIND-10 | 1/2 | explained | join loss, rounding increment or thirds (jointly) | - |
| BD-79 | 42x52 | quiltkeeper_binding @40 | yards | 3/8 | QREP today | 1/2 | explained | rounding increment or thirds | - |
| BD-80 | 76x85 | qp_binding @40 | strips | 9 | QREP today | 8 | explained | fabric width, join loss (D-08) | - |
| BD-81 | 76x85 | qp_binding @40 | yards | 5/8 | V-BIND-02 | 3/4 | explained | rounding increment or thirds | - |
| BD-82 | 76x85 | qp_binding @40 | yards | 5/8 | QREP today | 3/4 | explained | rounding increment or thirds | - |
| BD-83 | 76x85 | nqc @40 | strips | 9 | QREP today | 8 | explained | fabric width | - |
| BD-84 | 76x85 | stitchdesk_binding @42 | strips | 10 | V-BIND-02 | 9 | explained | binding extra length | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-85 | 76x85 | stitchdesk_binding @42 | strips | 10 | QREP today | 8 | explained | fabric width, binding extra length, join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-86 | 76x85 | quiltkeeper_binding @40 | strips | 9 | QREP today | 8 | explained | fabric width | - |
| BD-87 | 76x85 | quiltkeeper_binding @40 | yards | 5/8 | V-BIND-02 | 3/4 | explained | rounding increment or thirds | - |
| BD-88 | 76x85 | quiltkeeper_binding @40 | yards | 5/8 | QREP today | 3/4 | explained | rounding increment or thirds | - |
| BD-89 | 68x68 | qp_binding @40 | strips | 8 | QREP today | 7 | explained | fabric width, join loss (D-08) | - |
| BD-90 | 68x68 | qp_binding @40 | yards | 5/8 | V-BIND-07 | 3/4 | explained | rounding increment or thirds | - |
| BD-91 | 68x68 | qp_binding @40 | yards | 5/8 | QREP today | 1/2 | explained | fabric width, join loss (D-08) | - |
| BD-92 | 68x68 | nqc @40 | strips | 8 | QREP today | 7 | explained | fabric width | - |
| BD-93 | 68x68 | nqc @40 | yards | 3/4 | QREP today | 1/2 | explained | fabric width | - |
| BD-94 | 68x68 | stitchdesk_binding @42 | strips | 8 | QREP today | 7 | explained | fabric width, join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-95 | 68x68 | stitchdesk_binding @42 | yards | 5/8 | V-BIND-07 | 3/4 | explained | rounding increment or thirds | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-96 | 68x68 | stitchdesk_binding @42 | yards | 5/8 | QREP today | 1/2 | explained | fabric width, join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-97 | 68x68 | quiltkeeper_binding @40 | strips | 8 | QREP today | 7 | explained | fabric width | - |
| BD-98 | 68x68 | quiltkeeper_binding @40 | yards | 5/8 | V-BIND-07 | 3/4 | explained | rounding increment or thirds | - |
| BD-99 | 68x68 | quiltkeeper_binding @40 | yards | 5/8 | QREP today | 1/2 | explained | fabric width | - |
| BD-100 | 102.5x120 | nqc @40 | strips | 12 | V-BIND-06 | 13 | explained | join loss | - |
| BD-101 | 102.5x120 | nqc @40 | strips | 12 | QREP today | 11 | explained | fabric width | - |
| BD-102 | 102.5x120 | stitchdesk_binding @42 | strips | 13 | QREP today | 11 | explained | fabric width, binding extra length, join loss (D-08) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-103 | 102.5x120 | quiltkeeper_binding @40 | strips | 12 | V-BIND-06 | 13 | explained | join loss | - |
| BD-104 | 102.5x120 | quiltkeeper_binding @40 | strips | 12 | QREP today | 11 | explained | fabric width | - |
| BD-105 | 102.5x120 | quiltkeeper_binding @40 | yards | 7/8 | V-BIND-06 | 1 | explained | join loss, rounding increment or thirds (jointly) | - |
| BD-106 | 102.5x120 | quiltkeeper_binding @40 | yards | 7/8 | QREP today | 1 | explained | rounding increment or thirds | - |
| BD-107 | 58x66 | stitchdesk_binding @42 | strips | 8 | V-BIND-18 | 7 | explained | binding extra length | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-108 | 58x66 | stitchdesk_binding @42 | strips | 8 | QREP today | 7 | explained | fabric width, binding extra length, join loss (D-08) (jointly) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-109 | 58x66 | stitchdesk_binding @42 | yards | 5/8 | V-BIND-18 | 1/2 | explained | binding extra length | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-110 | 58x66 | stitchdesk_binding @42 | yards | 5/8 | QREP today | 1/2 | explained | fabric width, binding extra length, join loss (D-08), rounding increment or thirds (jointly) | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-111 | 24x58 | qp_binding @40 | yards | 3/8 | QREP today | 1/2 | explained | rounding increment or thirds | - |
| BD-112 | 24x58 | stitchdesk_binding @42 | yards | 3/8 | QREP today | 1/2 | explained | rounding increment or thirds | labels from the proxy set (proxy: U 40, w 2 1/2, extra 20, join_aware True, increment eighth), which gives the page model's value on this row |
| BD-113 | 24x58 | quiltkeeper_binding @40 | yards | 3/8 | QREP today | 1/2 | explained | rounding increment or thirds | - |
| BT-1 | 36x52 | qp_backing @batting120 | roll length (in) | 63 | V-BATT-02 | 60 | explained | rounding increment or thirds | - |
| BT-2 | 36x52 | qp_backing @batting120 | roll length (in) | 63 | QREP today | 60 | explained | rounding increment or thirds | - |
| BT-3 | 36x52 | omni_backing @42-batting | size (in) | 44 x 52 | V-BATT-02 | 44 x 60 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-4 | 36x52 | omni_backing @42-batting | size (in) | 44 x 52 | QREP today | 44 x 60 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-5 | 50x65 | qp_backing @batting120 | roll length (in) | 76 1/2 | V-BATT-04 | 73 | explained | rounding increment or thirds | - |
| BT-6 | 50x65 | qp_backing @batting120 | roll length (in) | 76 1/2 | QREP today | 73 | explained | rounding increment or thirds | - |
| BT-7 | 50x65 | omni_backing @42-batting | size (in) | 58 x 66 | V-BATT-04 | 58 x 73 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-8 | 50x65 | omni_backing @42-batting | size (in) | 58 x 66 | QREP today | 58 x 73 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-9 | 60x72 | qp_backing @batting120 | roll length (in) | 81 | V-BATT-03 | 80 | explained | rounding increment or thirds | - |
| BT-10 | 60x72 | qp_backing @batting120 | roll length (in) | 81 | QREP today | 80 | explained | rounding increment or thirds | - |
| BT-11 | 60x72 | omni_backing @42-batting | size (in) | 68 x 76 | V-BATT-03 | 68 x 80 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-12 | 60x72 | omni_backing @42-batting | size (in) | 68 x 76 | QREP today | 68 x 80 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-13 | 70x90 | qp_backing @batting120 | roll length (in) | 99 | V-BATT-05 | 98 | explained | rounding increment or thirds | - |
| BT-14 | 70x90 | qp_backing @batting120 | roll length (in) | 99 | QREP today | 98 | explained | rounding increment or thirds | - |
| BT-15 | 84x90 | qp_backing @batting120 | roll length (in) | 99 | V-BATT-06 | 98 | explained | rounding increment or thirds | - |
| BT-16 | 84x90 | qp_backing @batting120 | roll length (in) | 99 | QREP today | 98 | explained | rounding increment or thirds | - |
| BT-17 | 84x90 | omni_backing @42-batting | size (in) | 92 x 100.2 | V-BATT-06 | 92 x 98 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-18 | 84x90 | omni_backing @42-batting | size (in) | 92 x 100.2 | QREP today | 92 x 98 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-19 | 90x108 | qp_backing @batting120 | roll length (in) | 117 | V-BATT-07 | 116 | explained | rounding increment or thirds | - |
| BT-20 | 90x108 | qp_backing @batting120 | roll length (in) | 117 | QREP today | 116 | explained | rounding increment or thirds | - |
| BT-21 | 90x108 | omni_backing @42-batting | size (in) | 98 x 106.2 | V-BATT-07 | 98 x 116 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-22 | 90x108 | omni_backing @42-batting | size (in) | 98 x 106.2 | QREP today | 98 x 116 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-23 | 92.5x115 | qp_backing @batting120 | roll length (in) | 126 | V-BATT-08 | 123 | explained | rounding increment or thirds | - |
| BT-24 | 92.5x115 | qp_backing @batting120 | roll length (in) | 126 | QREP today | 123 | explained | rounding increment or thirds | - |
| BT-25 | 92.5x115 | mfqs_backing @42 | package | - | V-BATT-08 | king | record only | - | - |
| BT-26 | 92.5x115 | stitchdesk_backing @42 | package | off the roll | V-BATT-08 | king | explained | page rule: its own precut table, Craft to King | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BT-27 | 92.5x115 | omni_backing @42-batting | size (in) | 100 1/2 x 108.6 | V-BATT-08 | 100 1/2 x 123 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-28 | 92.5x115 | omni_backing @42-batting | size (in) | 100 1/2 x 108.6 | QREP today | 100 1/2 x 123 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-29 | 110x108 | qp_backing @batting120 | roll length (in) | 117 | V-BATT-09 | 116 | explained | rounding increment or thirds | - |
| BT-30 | 110x108 | qp_backing @batting120 | roll length (in) | 117 | QREP today | 116 | explained | rounding increment or thirds | - |
| BT-31 | 110x108 | omni_backing @42-batting | size (in) | 118.2 x 116 | V-BATT-09 | 118 x 116 | explained | rounding increment or thirds, page rule: piece sizes round up to 0.1 in | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-32 | 110x108 | omni_backing @42-batting | size (in) | 118.2 x 116 | QREP today | 118 x 116 | explained | rounding increment or thirds, page rule: piece sizes round up to 0.1 in | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-33 | 75x90 | qp_backing @batting120 | roll length (in) | 99 | V-BATT-01 | 98 | explained | rounding increment or thirds | - |
| BT-34 | 75x90 | qp_backing @batting120 | roll length (in) | 99 | QREP today | 98 | explained | rounding increment or thirds | - |
| BT-35 | 42x52 | qp_backing @batting120 | roll length (in) | 63 | V-BATT-13 | 60 | explained | rounding increment or thirds | - |
| BT-36 | 42x52 | qp_backing @batting120 | roll length (in) | 63 | QREP today | 60 | explained | rounding increment or thirds | - |
| BT-37 | 42x52 | stitchdesk_backing @42 | package | Throw | V-BATT-13 | twin | explained | page rule: its own precut table, Craft to King | labels list the page rule's differences from the reference (calc_rules.stitchdesk_backing); no MATH.md parameter set reproduces this row |
| BT-38 | 42x52 | omni_backing @42-batting | size (in) | 50 x 58 | V-BATT-13 | 50 x 60 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-39 | 42x52 | omni_backing @42-batting | size (in) | 50 x 58 | QREP today | 50 x 60 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-40 | 76x85 | qp_backing @batting120 | roll length (in) | 94 1/2 | QREP today | 93 | explained | rounding increment or thirds | - |
| BT-41 | 68x68 | qp_backing @batting120 | roll length (in) | 76 1/2 | V-BATT-11 | 76 | explained | rounding increment or thirds | - |
| BT-42 | 68x68 | qp_backing @batting120 | roll length (in) | 76 1/2 | QREP today | 76 | explained | rounding increment or thirds | - |
| BT-43 | 68x68 | omni_backing @42-batting | size (in) | 76 x 84 | V-BATT-11 | 76 x 76 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-44 | 68x68 | omni_backing @42-batting | size (in) | 76 x 84 | QREP today | 76 x 76 | explained | page rule: in batting mode a piece is (piece length + 8) / k wide | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-45 | 102.5x120 | omni_backing @42-batting | size (in) | 110.7 x 128 | V-BATT-10 | 110 1/2 x 128 | explained | rounding increment or thirds, page rule: piece sizes round up to 0.1 in | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-46 | 102.5x120 | omni_backing @42-batting | size (in) | 110.7 x 128 | QREP today | 110 1/2 x 128 | explained | rounding increment or thirds, page rule: piece sizes round up to 0.1 in | labels list the page rule's differences from the reference (calc_rules.omni_backing); no MATH.md parameter set reproduces this row |
| BT-47 | 58x66 | qp_backing @batting120 | roll length (in) | 76 1/2 | QREP today | 74 | explained | rounding increment or thirds | - |
| BT-48 | 24x58 | qp_backing @batting120 | roll length (in) | 67 1/2 | QREP today | 66 | explained | rounding increment or thirds | - |
| BR-1 | 36x52-b3.75 | qp_border @40 | band 1 yards | 5/8 | QREP at wof 320 | 1/2 | explained | border area (D-11), rounding increment or thirds | - |
| BR-2 | 36x52-b3.75 | sewbecca_border @40 | band 1 yards | 3/8 | QREP at wof 320 | 1/2 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-3 | 36x52-b3.75 | qc_border @40 | band 1 yards | 5/8 | QREP at wof 320 | 1/2 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-4 | 50x65-b3.75 | sewbecca_border @40 | band 1 yards | 5/8 | QREP at wof 320 | 3/4 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-5 | 60x72-b3.75 | qp_border @40 | band 1 yards | 7/8 | QREP at wof 320 | 3/4 | explained | border area (D-11), rounding increment or thirds | - |
| BR-6 | 60x72-b3.75 | dtq_border @40 | band 1 yards | 7/8 | QREP at wof 320 | 3/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-7 | 60x72-b3.75 | qc_border @40 | band 1 yards | 7/8 | QREP at wof 320 | 3/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-8 | 70x90-b3.75 | sewbecca_border @40 | band 1 yards | 3/4 | QREP at wof 320 | 1 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-9 | 70x90-b3.75 | qc_border @40 | band 1 yards | 1 1/8 | QREP at wof 320 | 1 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-10 | 84x90-b3.75 | qp_border @40 | band 1 yards | 1 1/8 | QREP at wof 320 | 1 | explained | border area (D-11), rounding increment or thirds | - |
| BR-11 | 84x90-b3.75 | dtq_border @40 | band 1 yards | 1 1/8 | QREP at wof 320 | 1 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-12 | 84x90-b3.75 | sewbecca_border @40 | band 1 yards | 7/8 | QREP at wof 320 | 1 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-13 | 84x90-b3.75 | qc_border @40 | band 1 yards | 1 1/8 | QREP at wof 320 | 1 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-14 | 90x108-b3.75 | sewbecca_border @40 | band 1 yards | 1 | QREP at wof 320 | 1 1/4 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-15 | 92.5x115-b3.75 | dtq_border @40 | band 1 yards | 1 3/8 | QREP at wof 320 | 1 1/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-16 | 92.5x115-b3.75 | sewbecca_border @40 | band 1 yards | 1 | QREP at wof 320 | 1 1/4 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-17 | 92.5x115-b3.75 | qc_border @40 | band 1 yards | 1 3/8 | QREP at wof 320 | 1 1/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-18 | 110x108-b3.75 | dtq_border @40 | band 1 yards | 1 3/8 | QREP at wof 320 | 1 1/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-19 | 110x108-b3.75 | sewbecca_border @40 | band 1 yards | 1 1/8 | QREP at wof 320 | 1 1/4 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-20 | 110x108-b3.75 | qc_border @40 | band 1 yards | 1 3/8 | QREP at wof 320 | 1 1/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-21 | 75x90-b3.75 | qp_border @40 | band 1 strips | 8 | V-BORD-01 | 10 | explained | pooled border strips | - |
| BR-22 | 75x90-b3.75 | dtq_border @40 | band 1 strips | 9 | V-BORD-01 | 10 | explained | pooled border strips, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-23 | 75x90-b3.75 | dtq_border @40 | band 1 yards | 1 1/8 | QREP at wof 320 | 1 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-24 | 75x90-b3.75 | sewbecca_border @40 | band 1 strips | 8 | V-BORD-01 | 10 | explained | pooled border strips, page rule: strips = ceil(2 L / fw + 2 (W + b) / fw), no seam allowance and no join loss | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-25 | 75x90-b3.75 | sewbecca_border @40 | band 1 yards | 3/4 | QREP at wof 320 | 1 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-26 | 75x90-b3.75 | qc_border @40 | band 1 yards | 1 1/8 | QREP at wof 320 | 1 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-27 | 42x52-b3.75 | qp_border @40 | band 1 yards | 5/8 | QREP at wof 320 | 3/4 | explained | border area (D-11), rounding increment or thirds | - |
| BR-28 | 42x52-b3.75 | dtq_border @40 | band 1 yards | 5/8 | QREP at wof 320 | 3/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-29 | 42x52-b3.75 | sewbecca_border @40 | band 1 yards | 1/2 | QREP at wof 320 | 3/4 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-30 | 42x52-b3.75 | qc_border @40 | band 1 yards | 5/8 | QREP at wof 320 | 3/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-31 | 76x85-b3.75 | sewbecca_border @40 | band 1 yards | 3/4 | QREP at wof 320 | 1 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-32 | 76x85-b3.75 | qc_border @40 | band 1 yards | 1 1/8 | QREP at wof 320 | 1 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-33 | 68x68-b3.75 | qp_border @40 | band 1 yards | 7/8 | QREP at wof 320 | 1 | explained | border area (D-11), rounding increment or thirds | - |
| BR-34 | 68x68-b3.75 | dtq_border @40 | band 1 yards | 7/8 | QREP at wof 320 | 1 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-35 | 68x68-b3.75 | sewbecca_border @40 | band 1 yards | 3/4 | QREP at wof 320 | 1 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-36 | 68x68-b3.75 | qc_border @40 | band 1 yards | 7/8 | QREP at wof 320 | 1 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-37 | 102.5x120-b3.75 | sewbecca_border @40 | band 1 yards | 1 1/8 | QREP at wof 320 | 1 1/2 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-38 | 58x66-b3.75 | dtq_border @40 | band 1 yards | 7/8 | QREP at wof 320 | 3/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-39 | 58x66-b3.75 | sewbecca_border @40 | band 1 yards | 5/8 | QREP at wof 320 | 3/4 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-40 | 58x66-b3.75 | qc_border @40 | band 1 yards | 7/8 | QREP at wof 320 | 3/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-41 | 24x58-b3.75 | sewbecca_border @40 | band 1 yards | 3/8 | QREP at wof 320 | 1/2 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-42 | 24x58-b3.75 | qc_border @40 | band 1 yards | 5/8 | QREP at wof 320 | 1/2 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-43 | V-BORD-02 | qp_border @40 | band 1 strips | 5 | V-BORD-02 | 6 | explained | pooled border strips | - |
| BR-44 | V-BORD-02 | qp_border @40 | band 1 yards | 3/8 | QREP at wof 320 | 1/2 | explained | border area (D-11), rounding increment or thirds | - |
| BR-45 | V-BORD-02 | dtq_border @40 | band 1 strips | 5 | V-BORD-02 | 6 | explained | pooled border strips, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-46 | V-BORD-02 | dtq_border @40 | band 1 yards | 3/8 | QREP at wof 320 | 1/2 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-47 | V-BORD-02 | sewbecca_border @40 | band 1 strips | 5 | V-BORD-02 | 6 | explained | pooled border strips, page rule: strips = ceil(2 L / fw + 2 (W + b) / fw), no seam allowance and no join loss | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-48 | V-BORD-02 | sewbecca_border @40 | band 1 yards | 1/4 | QREP at wof 320 | 1/2 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-49 | V-BORD-02 | qc_border @40 | band 1 yards | 3/8 | QREP at wof 320 | 1/2 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-50 | V-BORD-03 | qp_border @40 | band 1 strips | 7 | V-BORD-03 | 8 | explained | pooled border strips | - |
| BR-51 | V-BORD-03 | qc_border @40 | band 1 yards | 5/8 | QREP at wof 320 | 1/2 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |
| BR-52 | V-BORD-04 | qp_border @40 | band 1 strips | 1 | V-BORD-04 | 2 | explained | pooled border strips | - |
| BR-53 | V-BORD-04 | qp_border @40 | band 1 yards | 1/8 | QREP at wof 320 | 1/4 | explained | border area (D-11), rounding increment or thirds | - |
| BR-54 | V-BORD-04 | dtq_border @40 | band 1 strips | 1 | V-BORD-04 | 2 | explained | pooled border strips, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-55 | V-BORD-04 | dtq_border @40 | band 1 yards | 1/8 | QREP at wof 320 | 1/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1) | labels list the page rule's differences from the reference (calc_rules.dtq_border); no MATH.md parameter set reproduces this row |
| BR-56 | V-BORD-04 | sewbecca_border @40 | band 1 strips | 1 | V-BORD-04 | 2 | explained | pooled border strips, page rule: strips = ceil(2 L / fw + 2 (W + b) / fw), no seam allowance and no join loss | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-57 | V-BORD-04 | sewbecca_border @40 | band 1 yards | 1/8 | QREP at wof 320 | 1/4 | explained | border area (D-11), page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd | labels list the page rule's differences from the reference (calc_rules.sewbecca_border); no MATH.md parameter set reproduces this row |
| BR-58 | V-BORD-04 | qc_border @40 | band 1 yards | 1/8 | QREP at wof 320 | 1/4 | explained | border area (D-11), pooled border strips, rounding increment or thirds, page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide | labels list the page rule's differences from the reference (calc_rules.qc_border); no MATH.md parameter set reproduces this row |

## Unexplained, for the A1 and A2 owners

n = 0. Each lead is the calculator's observed rule where one is recorded (searches.json, the registry and calc_rules); the vectors and parameter sets were not changed to match.

| ID | Row | Calculator | Value | Shown | Against | Target | Rule gives | Lead | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Calculators per line type (plan section 9, item 13)

A calculator counts for a line type when at least one of its rows returned a parsed value for it.

| Line type | MATH.md 5.2 list | Added | Total | Shortfall from four |
| --- | --- | --- | --- | --- |
| backing | n = 3: qp_backing, mfqs_backing, nqc | n = 2: stitchdesk_backing, omni_backing | n = 5 | n = 0 |
| binding | n = 2: qp_binding, nqc | n = 2: stitchdesk_binding, quiltkeeper_binding | n = 4 | n = 0 |
| batting | n = 2: qp_backing, mfqs_backing | n = 2: stitchdesk_backing, omni_backing | n = 4 | n = 0 |
| borders | n = 1: qp_border | n = 3: dtq_border, sewbecca_border, qc_border | n = 4 | n = 0 |

### Search summary (searches.json, searched on 2026-10-07)

Queries n = 10; qualified pages n = 9; rejected candidates n = 23.

| Line type | Queries | Results listed | Qualified | Added to the harness |
| --- | --- | --- | --- | --- |
| backing | n = 2 | n = 18 | n = 3: The Stitch Desk (thestitchdesk.com), Quilt Calculator (quiltcalculator.com), Omni Calculator | n = 2: stitchdesk_backing, omni_backing |
| binding | n = 3 | n = 27 | n = 3: The Stitch Desk (thestitchdesk.com), Quilt Calculator (quiltcalculator.com), QuiltKeeper Studio (quiltkeeperstudio.com) | n = 2: stitchdesk_binding, quiltkeeper_binding |
| batting | n = 2 | n = 20 | n = 3: The Stitch Desk (thestitchdesk.com), Quilt Calculator (quiltcalculator.com), Omni Calculator | n = 2: stitchdesk_backing, omni_backing |
| borders | n = 3 | n = 27 | n = 3: Quilt Calculator (quiltcalculator.com), Designed to Quilt (designedtoquilt.com), Sew Becca (sewbecca.com) | n = 3: dtq_border, sewbecca_border, qc_border |

Qualified but not driven (n = 2): Quilt Calculator (quiltcalculator.com) https://quiltcalculator.com/binding-calculator; Quilt Calculator (quiltcalculator.com) https://quiltcalculator.com/backing-calculator.

## Failures

n = 24. A failed record carries the driver's error and its screenshot; a parse error is a record the driver accepted but the parser refused.

| ID | Calculator | Row | Status | Error | Screenshot | Used in the tables |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | qp_backing | 36x52@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F2 | qp_backing | 50x65@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F3 | qp_backing | 70x90@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F4 | qp_backing | 84x90@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F5 | qp_backing | 90x108@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F6 | qp_backing | 110x108@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F7 | qp_backing | 42x52@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F8 | qp_backing | 76x85@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F9 | qp_backing | 68x68@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F10 | qp_backing | 102.5x120@42 | failed | input limit: Width held "102." for typed "102.5" (maxlength 4) | scripts/eval/calculators/failures/qp_backing__102.5x120_42.png | yes |
| F11 | qp_backing | 102.5x120@40 | failed | input limit: Width held "102." for typed "102.5" (maxlength 4); result unchanged after submit | scripts/eval/calculators/failures/qp_backing__102.5x120_40.png | yes |
| F12 | qp_backing | 102.5x120@batting120 | failed | input limit: Width held "102." for typed "102.5" (maxlength 4) | scripts/eval/calculators/failures/qp_backing__102.5x120_batting120.png | yes |
| F13 | qp_backing | 58x66@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F14 | qp_backing | 24x58@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F15 | qp_binding | 102.5x120@40 | failed | input limit: Width held "102." for typed "102.5" (maxlength 4) | scripts/eval/calculators/failures/qp_binding__102.5x120_40.png | yes |
| F16 | qp_border | 90x108-b3.75@40 | failed | input limit: Length held "100." for typed "100.5" (maxlength 4) | scripts/eval/calculators/failures/qp_border__90x108-b3.75_40.png | yes |
| F17 | qp_border | 92.5x115-b3.75@40 | failed | input limit: Length held "107." for typed "107.5" (maxlength 4) | scripts/eval/calculators/failures/qp_border__92.5x115-b3.75_40.png | yes |
| F18 | qp_border | 110x108-b3.75@40 | failed | input limit: Width held "102." for typed "102.5" (maxlength 4); input limit: Length held "100." for typed "100.5" (maxlength 4) | scripts/eval/calculators/failures/qp_border__110x108-b3.75_40.png | yes |
| F19 | qp_border | 102.5x120-b3.75@40 | failed | input limit: Length held "112." for typed "112.5" (maxlength 4) | scripts/eval/calculators/failures/qp_border__102.5x120-b3.75_40.png | yes |
| F20 | omni_backing | 92.5x115@42 | failed | held value differs: width held "925" for typed "92.5" | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F21 | omni_backing | 92.5x115@42-batting | failed | held value differs: width held "925" for typed "92.5" | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F22 | dtq_border | 36x52-b3.75@40 | failed | held value differs: number-1 held "0.502" for typed "28.5" | scripts/eval/calculators/failures/dtq_border__36x52-b3.75_40.png | no: a later record of this row is used (failed) |
| F23 | sewbecca_border | 92.5x115-b3.75@40 | failed | result unchanged after submit | not kept: a later record of this row returned values | no: a later record of this row is used (ok) |
| F24 | dtq_border | 36x52-b3.75@40 | failed | held value differs: number-1 held "0.502" for typed "28.5" | scripts/eval/calculators/failures/dtq_border__36x52-b3.75_40.png | yes |

## Not compared

| Reason | Records | Detail |
| --- | --- | --- |
| not applicable | n = 2 | dtq_border V-BORD-03@40; sewbecca_border V-BORD-03@40 |
