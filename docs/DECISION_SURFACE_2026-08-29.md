# How many decisions does Cairn actually ask for?

Measured against `tests/fixtures/bitterroots/Bitterroots__Complete_.json` — a real 10-folder
CalTopo map — using the shipped config, i.e. the same path the CLI takes.

**Method note:** an earlier pass called `map_icon(title, desc, symbol)` without a config and got
46%. That is wrong. `cairn/core/mapper.py:map_icon` documents its own priority order as
"1. CalTopo marker-symbol **(if config provided)**" — with `config=None` the symbol argument is
ignored entirely and only keyword matching runs. Every number below passes `load_config()`.

## The map

| | |
|---|---|
| Folders | 10 |
| Waypoints | 68 |
| Tracks / routes | 92 |
| Shapes | 17 |

The wizard loops `Routes → Waypoints` once per folder, so a full pass is **10 iterations** of the
same two screens.

## Icon resolution, measured

```
   26  Location  (the generic pin)          42/68 = 62% get a meaningful icon
   10  Parking                              26/68 = 38% fall back
    9  Climbing
    5  Summit          Of the 26 fallbacks:
    4  Cabin             3  carry a real CalTopo symbol Cairn cannot map (flag-1 x3)
    4  Water Source     23  carry CalTopo's OWN generic pin ("point")
    3  Camp
    3  Hazard
    1  XC Skiing, Waterfall, Snowboarder, Water Crossing
```

## What this means

**The decision surface is not 68. It is about 24.**

| Class | Count | Who can answer |
|---|---|---|
| Already resolved | 42 | Nobody needs to — the symbol or a keyword carried the intent |
| Unmapped symbol | 3 | **One standing decision** (`flag-1 → ?`) fixes all three, and every future map |
| CalTopo generic pin | 23 | **Only the user.** No intent was ever recorded to recover |

That last row is the honest floor. These are waypoints the user dropped in CalTopo as plain pins
and named things like `Chute1`, `Sick bowl brah`, `Gash knob`, `Cairn`, `skinny log`,
`Shoshone Spire`, `NT1`, `COL`. That is personal shorthand. No mapping table, keyword list, or
model recovers it — and pretending otherwise would produce confidently wrong icons, which is worse
than a neutral pin.

**So the design problem is not "automate the 68." It is "stop making the user walk 68 things to
answer 24 questions."** The current wizard shows every folder, every route, and every waypoint at
equal weight, with no signal about which ones actually need attention. The 42 that resolved
cleanly and the 23 that genuinely need a human look identical on screen.

## Two smaller findings

**Name-against-vocabulary matching is a real but small win.** onX has 95 icons including
`Waterfall`, `Rappel`, `Footbridge`, `Cornice`. Matching a waypoint's *name* against that
vocabulary (whole-word, case-insensitive) recovers only **4 more** of the fallbacks —
`Waterfall`, `possible waterfall?`, `Rappel anchor`, `Good looking climbing`. Worth doing; not
transformative. Naive substring matching is actively dangerous here: it turns
"Main Wall - Lost **horse** canyon" into `Horseback` and "Cool **ridge** line traverse" into
`Footbridge`.

**Tracks and shapes are 109 of the 177 objects and get far less attention than waypoints.** The
wizard gives Routes its own step per folder, but the editable surface there is thinner (no icon),
and shapes get no step at all — they pass through to KML untouched.

## The question this poses for design

Every proposal should answer: **how does the user get to the 24 without walking the 68?** Options
that fall out of the numbers:

- Sort or filter by "needs attention" so the 23 generic pins surface first
- Batch the 23 by folder or by name pattern, since a user who drops 23 plain pins usually means
  several distinct things by them ("all my climbing approach markers")
- Ask the one standing question (`flag-1`) once, up front, and remember it — the project's backlog
  already asks for the unmapped-symbol warning to move to the *start* of the process
- Let the 42 that resolved cleanly stay collapsed and out of the way

---

## A bug found while measuring: Cairn ships an icon onX does not accept

`Cabin` is not in onX's 95-icon vocabulary. `normalize_onx_icon_name("Cabin")` returns `None`.
But `DEFAULT_SYMBOL_MAP` maps three CalTopo symbols to it — `cabin`, `hut`, `yurt` — and it also
appears as a key in `DEFAULT_KEYWORD_MAP` and `ICON_COLOR_MAP` (`cairn/core/config.py`).

Verified end to end on the real Bitterroots map:

```
$ grep -o '<onx:icon>[^<]*' <exported>_Waypoints.gpx | sort | uniq -c
     10 Parking      9 Climbing      6 Summit       4 Water Source
      4 Cabin   <-- not a valid onX icon
      3 Hazard       3 Camp    ...
  INVALID icons shipped to onX: ['Cabin']
```

Those 4 waypoints arrive in onX as the **default pin** — a silent loss of exactly the judgement
layer the tool exists to preserve, and invisible to the user because Cairn's own preview happily
shows "Cabin".

The sharpest part: **Cairn already has the validation to catch this and does not apply it to its
own defaults.** `save_user_mapping()` rejects any icon failing `normalize_onx_icon_name()`, so a
*user* is forbidden from writing `hut: Cabin` by hand — while the shipped default does exactly
that.

Audit of the full default tables (all three, `.values()` checked against the canonical list):
**exactly one** invalid name, `Cabin`. So this is a one-line data fix — `House` and `Shelter` are
both valid, and `Shelter` is the better fit for a backcountry hut or yurt — plus a guard test
asserting every icon reachable from the shipped defaults is in the canonical vocabulary.

Two related self-inconsistencies in the same file, confirmed by AST inspection:
`ICON_COLOR_MAP` defines the key `"Camp"` **twice** (32 literal keys, one duplicate), and
`DEFAULT_KEYWORD_MAP` defines `"Camp"` **twice** as well. Python keeps the last definition
silently, so one entry in each is dead and nobody would notice.
