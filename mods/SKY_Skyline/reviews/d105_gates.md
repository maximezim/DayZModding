# D105 phone booth, bus stop, billboard: gates, review, before / after

These are the remaining street props from the D101 assessment. The booth and the shelter used the far-LOD `glassfar`
texture in Res0, so their glass looked black up close.

![Before](img/d105_before.png)
![After](img/d105_after.png)

## Changes

- **PhoneBooth** (`build_streetprops.py`):
  - round posts, rails, red kick panels as 16 mm sheets (the old back-to-back quads rendered black);
  - transparent `glass`, with shards left in the smashed side pane;
  - lofted roof cap carrying a TELEFON-AVTOMAT sign on three sides (`signs4` band 6, the spare "MOLOKO" band, which no
    model used);
  - steel back plate, coin phone with keypad, coin slot, cradle and display, handset on an armoured cord, shelf with a
    phone book.
- **BusStop**:
  - base plates;
  - open corrugation ridges;
  - rear gutter and downpipe;
  - transparent glass, with shards left in the smashed middle pane;
  - framed side panels;
  - rounded slats on two-piece cast brackets;
  - framed timetable;
  - capped route-sign pole;
  - lofted bin with a rim.
- **Billboard** (`build_kit.py`):
  - concrete footings, also in Geo and Fire;
  - X-bracing;
  - lofted lamp hoods with lenses;
  - base plates sit on the footings.

| Model | Res0 | Res1 | check_assets |
|---|---|---|---|
| PhoneBooth | 740 | 84 | PASS |
| BusStop | 884 | 96 | PASS |
| Billboard | 666 | 156 | PASS |

## Review

| Finding | Fix |
|---|---|
| sec M1: the smashed booth pane was the back one, so the phone plate, body and shelf had no Geo / Fire / View | a side pane is smashed now; the back pane, with its full Geo / Fire, stays behind the plate |
| sec M2: shelter Res2 kept an opaque back wall while View has none (one-way concealment at range, worse with clear Res0 glass) | Res2 box skips +y too |
| sec L3: Geo / Fire spanned the open middle shelter pane (an invisible wall) | per-pane Geo / Fire, middle pane open (12 components) |
| sec L4: booth kick panel opaque to 0.90 m, View to 0.85 m | View to 0.90 m |
| sec L5: thin Res0-only parts (downpipe, bracing, bracket lip) | accepted: 2-4 cm tubes |
| perf M: footing added a concrete section to the billboard's Res1 | Res1 footing uses rust |
| perf M: boxed roof ribs, 144 triangles, half buried | open ridges, 4 triangles each |
| perf L: sign rim hidden inside the disc, buried post caps, 16 bolt heads (about 320 triangles), 7 booth sections | removed; the phone book and display use metal (5 sections) |
| perf info: one alpha glass section per prop in Res0, none in Res1 | accepted |

## Gates

| Gate | Result |
|---|---|
| test_quality (3 models), test_kit (3), test_conceal (3), test_slits (3) | PASS |
| check_assets | 289 checked, 0 fail, 54 over budget (hypotheses; was 56: the booth and shelter overruns were fixed) |
| check_p3d_sync (build_kit, build_streetprops) | PASS, 29 models byte-identical |
| gen_configs / gen_manifest --check, texture refs | up to date, up to date, PASS (91) |

On Windows, `Build-SkyAssets.ps1` regenerates `sky_signs4_co` (now with the phone band) before packing. TESTING §61 TP-03.
