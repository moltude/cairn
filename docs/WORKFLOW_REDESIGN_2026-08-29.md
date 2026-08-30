# Workflow redesign — three proposals, and what the numbers say

Three designers investigated Cairn's interaction model from deliberately different theses. This
document reconciles them against a measurement (`DECISION_SURFACE_2026-08-29.md`) and says what
to build.

**The finding that reframes everything:** on a real 68-waypoint map, the tool makes the user walk
68 items to answer about **24 questions**. 42 waypoints resolve automatically and correctly; the
user reviews them anyway, at the same visual weight as the ones that need them.

---

## The three theses

| | Thesis | Attacks |
|---|---|---|
| **A** | "The best decision is the one the user never has to make." Trust the machinery; escalate only genuine ambiguity. | The **42 already-resolved** — stop asking about them |
| **B** | "Stop asking questions. Show them the map and let them touch it." Replace the wizard with a persistent workspace. | The **23 irreducible** — make answering them fast |
| **C** | "The user's intent is a rule, not a click." Standing preferences stated once, reused forever. | The **3 standing** — and every future map |

**They are not competitors.** Each addresses a different slice of the same measured surface, and
the slices don't overlap. The synthesis below sequences them rather than picking one.

---

## What each investigation found (verified independently)

I checked every load-bearing claim rather than relaying it. Results:

### CONFIRMED — a user's saved rules silently vanish depending on where they run the tool

`load_config()` resolves `Path("cairn_config.yaml")` relative to the **current working
directory** (`cairn/core/config.py:877, 906`), and the TUI passes `load_config(None)` with no
override path at all (`cairn/tui/app.py:189, 1566`), so `--config` exists only on the legacy CLI.

Proved by running the same code from two directories:

```
from repo root : symbol_mappings loaded = 152
from elsewhere : symbol_mappings loaded = 144
```

**Eight user-saved mappings disappear.** No warning, no "no config found" message. A user maps
`climbing-2 → Climbing` while sitting in `~/maps/bitterroots`, then next weekend opens the GPX a
friend emailed them from `~/Downloads` and every rule they taught the tool is gone. This voids
the entire premise of Thesis C until fixed, and it is a bug on its own terms today.

### CONFIRMED — Cairn ships an icon onX does not accept

`Cabin` is not in onX's 95-icon vocabulary; `normalize_onx_icon_name("Cabin")` returns `None`.
Yet `DEFAULT_SYMBOL_MAP` maps `cabin`, `hut`, and `yurt` to it. Verified in a real export: 4
waypoints carry `<onx:icon>Cabin</onx:icon>`, and they will land in onX as the default pin.

The sharp part: **Cairn already has the validation and doesn't apply it to itself.**
`save_user_mapping()` rejects icons failing `normalize_onx_icon_name()`, so a *user* is forbidden
from writing `hut: Cabin` by hand while the shipped default does exactly that. A full audit of all
three default tables found **exactly one** such name, so this is a one-line data fix
(`Shelter` fits a backcountry hut) plus a guard test.

### CONFIRMED — numbered waypoints are structurally invisible to keyword matching

`_TOKEN_RE = re.compile(r"[a-z0-9]+")` (`cairn/core/icon_resolver.py:35`) merges trailing digits
into the token:

```
'Chute1'  -> ['chute1']     never matches keyword 'chute'
'Camp2'   -> ['camp2']      never matches keyword 'camp'
'Water 1' -> ['water','1']  matches fine
```

So `Camp 2` resolves and `Camp2` doesn't. Numbering waypoints is an extremely common habit, and
this silently defeats it. Stripping trailing digits before tokenizing is a few lines and recovers
the whole class.

### CONFIRMED — two dead entries in the shipped config

AST inspection: `ICON_COLOR_MAP` defines the key `"Camp"` twice, and `DEFAULT_KEYWORD_MAP`
defines `"Camp"` twice. Python keeps the last silently; one entry in each is dead code nobody
would notice.

### CORRECTED — the Shapes gap is real but ~6x smaller than claimed

Thesis B reported that Shapes are "109 of 177 items — 61.6% of the map" with no editing step.
That conflates CalTopo's taxonomy with Cairn's. CalTopo's `class=Shape` holds **92 LineStrings
(which are tracks/routes, and *do* have a Routes step) and 17 Polygons**:

```
by CalTopo class : {'Folder': 9, 'Marker': 68, 'Shape': 109, 'ConfiguredLayer': 3}
by geometry type : {'Point': 68, 'LineString': 92, 'Polygon': 17, None: 12}
```

The uneditable surface is **17 of 177 = 9.6%**, not 61.6%. But the underlying finding stands and
is worth acting on: polygons pass through the TUI completely untouched — there is no
`_selected_shape_keys` anywhere in the codebase, so they cannot be selected, renamed, or
recolored. And B's *architectural* argument survives the correction intact: a wizard needs a named
step per kind of thing, so adding shape editing means a seventh step, while a tree with a Kind
column needs one more row type.

### CORRECTED — two audit findings were already fixed this session

B flagged Esc-quits-after-export and silent-overwrite as live bugs. Both were fixed earlier today;
B was reading a working tree that already contained the fixes. Worth noting because it means
`app.py` is now 3841 lines, not the 3698 the earlier audit recorded.

---

## Where the proposals genuinely disagree

**On automation confidence.** A wants to auto-apply fuzzy icon matches at ≥0.9 confidence,
flipping the explicit policy at `icon_registry.py:258` ("This is advisory only (we do not
auto-map)"). C wants the user to bless a rule once and then auto-apply forever. These are
different trust models: A trusts the *algorithm*, C trusts the *user's prior decision*. C's is
safer and more explainable — "because you told me to" beats "because I scored it 0.91" when a
user asks why a waypoint became a Campground.

**On where the editor lives.** A makes the full review an opt-in escape hatch (`--review`). B
makes it the permanent home. Both can't be the default. The measurement favors A's default for
clean maps and B's for messy ones — which argues for the escalation ladder deciding, not a
fixed choice.

**On confirmation.** All three independently flagged that the risk model is backwards: renaming
2 items prompts, re-iconing 500 doesn't. Confirmations should scale with blast radius, not field
type. This is the one point of unanimous agreement.

---

## What the numbers say to build

Ordered by value per unit of effort, and by how little each depends on the others.

### Tier 1 — data and logic fixes, no UI change, no test-suite entanglement

These raise the auto-resolution rate directly. None touch the step machine or the keystroke-order
tests that block the bigger work.

1. **Fix `Cabin`** → `Shelter`, plus a guard test asserting every icon reachable from the shipped
   defaults is in the canonical vocabulary. Silent data loss today.
2. **Fix config discovery** — `--config` → `$CAIRN_CONFIG` → `~/.config/cairn/config.yaml` →
   directory-local `cairn_config.yaml`, merged; print which file loaded. Without this, nothing
   "remembered" is reliably found again.
3. **Strip trailing digits in the tokenizer** — recovers `Camp2`/`Chute1`/`WP3`.
4. **Add missing forward mappings** — `circle-p` (9 occurrences in the fixture alone),
   `scrambling`, `automobile`, `repair-streamcrossing`. Several exist as reverse-map targets with
   no forward entry.
5. **De-duplicate `"Camp"`** in `ICON_COLOR_MAP` and `DEFAULT_KEYWORD_MAP`, and validate on load.

### Tier 2 — the escalation ladder (Thesis A's core, CLI-only)

Replace "review all 68" with a summary plus a two-tier split: *worth a look* (resolved but
uncertain — ties, keyword-only matches) and *needs you* (zero signal). This lives in
`migrate_cmd.py` and `preview.py`, touches no TUI step machine, and is where `--no-interactive`
finally gets to mean something real.

Also here: **surface `IconDecision.reasons`.** The explanation strings already exist
(`icon_resolver.py:24-32`) and are discarded. "Why did this become a Campground" is a field
away from being answerable.

### Tier 3 — remember decisions (Thesis C, gated on Tier 1.2)

Generalize the "remember this?" prompt that already exists for symbols
(`app.py:1606-1616`, `migrate_cmd.py:1241-1257`) to color and name decisions — with the two things
it's missing: a visible diff before writing, and a "just this once" option. Do **not** build a
YAML rule DSL up front; ship the generalized prompt and see what users actually ask to remember.

### Tier 4 — the workspace (Thesis B, gated on test work)

The cheapest subset first, without deleting the wizard:

1. **Stop clearing selection at folder transitions.** Row keys are already stable global feature
   ids, so cross-folder selection is safe at the data layer today — the app just actively wipes it
   at multiple call sites. Removing that turns "loop 10 folders with no memory" into "select
   across folders, act once." Highest value per line touched in the entire investigation.
2. **A persistent selection tray**, mounted on the existing steps.
3. **Give polygons a selection/edit path**, reusing the existing overlays — closes the 9.6% gap.

Only then the full tree/workspace conversion — and only after the keystroke-order tests are
replaced with state-keyed ones. `state.py:162-168` says a step is never skipped *because tests
depend on it*; that suite is not a safety net for this refactor, it's the thing holding the wrong
shape in place.

---

## The one-line version

**Tiers 1 and 2 remove most of the work without redesigning anything.** The wizard's real sin
isn't its shape — it's that it presents 42 settled questions and 23 open ones at identical weight.
Fix the resolution rate, then triage what's left, then remember the answers, and only then argue
about panes.
