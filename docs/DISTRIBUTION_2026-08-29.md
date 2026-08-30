# Distribution & install friction — 2026-08-29

Answering two questions: **should Cairn be a Homebrew package?** and **how do we reduce the
friction of installing and using it?**

Claims about PyPI names, action versions, and Homebrew rules below were verified live on
2026-08-29 (`curl`, `gh api`, and the linked docs). Items I could not verify are marked
**UNVERIFIED** rather than smoothed over.

---

## The blocker nobody has hit yet: the name `cairn` is taken on PyPI

```
$ curl -s -o /dev/null -w "%{http_code}" https://pypi.org/pypi/cairn/json
200
```

It belongs to `cairn 0.2.3`, *"Tools and utilities for managing project versions"* by Ed
FitzGerald, last released **2019-06-27**. This matters because **every distribution channel below
depends on the PyPI name** — Homebrew formulae for Python CLIs pull their tarball from PyPI, and
`pipx`/`uv tool install` resolve by PyPI name.

Verified availability (404 = free): `cairn-maps` ✅ · `caltopo-cairn` ✅ · `cairnmap` ✅ ·
`cairn-cli` ❌ (also taken).

**The command the user types does not have to change.** `[project.scripts]` controls that, so
`pipx install cairn-maps` still installs a binary called `cairn`. Only the distribution name moves.

The alternative is a [PEP 541](https://peps.python.org/pep-0541/) name request — the project
plausibly qualifies as abandoned (no release in 7 years), but PEP 541 requires *all* of: owner
unreachable, no releases in 12 months, no activity on the project's home page. You must contact
the owner first, then file at [pypa/pypi-support](https://github.com/pypa/pypi-support/issues).
Expect weeks. **Recommendation: take `cairn-maps` and move on.**

---

## Should this be a Homebrew package?

**Short answer: eventually yes as your own tap, but it is third in line, not first — and it is
not the thing that unblocks your actual users.**

Three reasons, in order of decisiveness:

**1. homebrew-core will reject it today, and the bar for *you specifically* is triple.**
Homebrew's Package Acceptance Policy requires a new package to "demonstrate public interest
beyond its author," normally met by **"at least 30 forks, 30 watchers or 75 stars"** — but
**"at least 90 forks, 90 watchers or 225 stars for a self-submission by the repository owner."**
It also notes "A code repository less than 30 days old is normally not eligible."
([Package-Acceptance-Policy.md](https://github.com/Homebrew/brew/blob/master/docs/Package-Acceptance-Policy.md#notability),
fetched 2026-08-29.) Since you would be submitting your own project, **225 stars** is the number
that applies. A solo project with no stars and no releases is not close. So the realistic option is
**your own tap** (`moltude/homebrew-cairn`), which users install with
`brew install moltude/cairn/cairn`. That works, and it is a genuinely nice install experience.

**2. It needs PyPI first anyway.** A Homebrew formula for a Python CLI points its `url` at a
PyPI sdist. So publishing to PyPI is a prerequisite for the tap, not an alternative to it.

**3. The maintenance burden is real and recurring.** Homebrew requires that *every* transitive
Python dependency be declared as a `resource` block with its own url + sha256
([docs.brew.sh/Language-Specific-Formulae](https://docs.brew.sh/Language-Specific-Formulae)).
Cairn's five direct deps (typer, rich, pyyaml, prompt-toolkit, textual) expand to a substantial
tree. `brew update-python-resources --ignore-errors` regenerates them (the `--ignore-errors`
flag exists specifically for third-party taps), but it needs re-running every release.

Worth knowing: the popular auto-bump action `mislav/bump-homebrew-formula-action` explicitly
**cannot** handle this shape — its README lists "Cannot bump Python-based formulae which declare
their PyPI dependencies as additional `resource` blocks" under known limitations. So the tap
either gets a hand-rolled bump job or `dawidd6/action-homebrew-bump-formula@v8` (which works but
requires a *classic* PAT with write access to every public repo you own — a wide blast radius for
one formula).

### The uncomfortable part

`brew install` is a **developer** on-ramp. Homebrew itself requires the Xcode Command Line Tools.
A hiker who has never opened Terminal.app is not one `brew install` away from using Cairn — they
are one Homebrew install, one Xcode CLT download, and one terminal tutorial away.

So: ship the tap because it's cheap once PyPI exists and it delights the technical slice of your
audience. Do not expect it to move the adoption needle for the audience the README is written for.

---

## The options, scored for a NON-developer user

| Option | End-user friction | Maintainer burden | Platforms | Suits a hiker? |
|---|---|---|---|---|
| **Today: git clone + uv sync** | **Blocking** — install uv, clone, sync, `uv run` | none | all | ❌ No |
| `uvx cairn-maps` / `pipx install` | Medium — still needs uv or pipx installed first | **Very low** | all | ⚠️ Only if they already code |
| **Standalone binary** (GitHub Release) | **Low** — download, `chmod +x`, run. No Python at all | Medium (CI matrix; macOS signing) | mac/linux/win | ✅ Best terminal option |
| Homebrew tap | Low *if* they have brew | Medium-high (resource blocks) | mac/linux | ⚠️ Developer-adjacent |
| Windows: Scoop/winget | Low | Medium | win | ⚠️ |
| Docker | High (Docker Desktop + volume mounts for file I/O) | Low | all | ❌ No |
| **Hosted web version** | **Lowest** — click a link, drag a file | High (hosting, uploads, privacy) | all | ✅✅ Only real mass-market answer |

### macOS binaries have a signing tax

An unsigned binary downloaded via a browser gets quarantined by Gatekeeper: *"cannot be opened
because the developer cannot be verified."* The workaround (right-click → Open, or
`xattr -d com.apple.quarantine`) is exactly the kind of instruction that loses non-technical
users. Proper fix is an Apple Developer ID ($99/yr) plus notarization. **A binary downloaded with
`curl` rather than a browser does not get the quarantine attribute** — so a one-line
`curl | sh` installer sidesteps this for terminal users. UNVERIFIED: I did not test PyInstaller
against this app; Textual's CSS assets and `cairn/data/*.yaml` will need explicit
`--collect-all` / `--add-data` handling.

---

## Recommended rollout

**Phase 1 — publish to PyPI (a few hours, do this first).**
Rename the distribution to `cairn-maps`, keeping the `cairn` command. Set up Trusted Publishing
(OIDC, no API tokens) at [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/)
with a *pending publisher*, then tag `v1.0.1`. Install collapses to:

```bash
uv tool install cairn-maps     # or: pipx install cairn-maps
cairn tui
```

That deletes four of the five steps in the current README. Biggest friction win per hour spent.

Two things to fix in the same change: `pyproject.toml` hardcodes `version = "1.0.0"` with no
git tags, and **PyPI filenames are immutable** — publish a wrong version once and it is permanent.
Guard it in CI by asserting the tag matches the pyproject version before building. Also note PEP
740 attestations are now generated **by default** by `pypa/gh-action-pypi-publish` (≥v1.11.0)
when using Trusted Publishing — no extra config.

**Phase 2 — standalone binaries on GitHub Releases (about a day).**
This is the one that actually reaches a non-developer who is willing to open a terminal: no
Python, no uv, no pipx. Build with PyInstaller across a matrix and attach to the release. Note
`macos-13` runners no longer exist — use `macos-latest` (arm64) and `macos-15-intel` (x86_64);
`ubuntu-24.04-arm` is free on public repos.

**Phase 3 — Homebrew tap (about a day, plus recurring upkeep).**
`moltude/homebrew-cairn`, `virtualenv_install_with_resources`, resource blocks generated by
`brew update-python-resources --ignore-errors`. Bump from CI with a fine-grained PAT scoped to
the tap repo only (`Contents: Read and write` + `Metadata: Read`) — not a classic PAT.

**Phase 4 — decide whether the terminal is the product.**
Textual ships `textual serve`, which runs a Textual app in a browser. That is a tempting shortcut
to a web version, but it is designed for demos and internal tools; exposing it publicly means
handling uploads, sessions, and per-user isolation. **UNVERIFIED** — I did not assess its
production-readiness. The honest framing: Phases 1–3 serve people who already use a terminal.
If the goal is every CalTopo user, a drag-and-drop web page is a different product, and worth
scoping deliberately rather than drifting into via `textual serve`.

---

## Friction *after* install (cheap, high-value, independent of packaging)

These matter as much as the install and cost far less:

1. **`cairn` with no arguments prints a help screen listing subcommands.** For this audience it
   should launch the TUI — already on the backlog ("make `tui` the default").
2. **`--no-interactive` prompts anyway and then aborts** (verified). Cairn currently cannot be
   scripted or run in CI. See `TODO.md`.
3. **The output path is the last thing a user needs and it wraps mid-character** in the success
   message (verified). Print the full path unwrapped.
4. **Configurable default map directory** (e.g. `~/maps`) so the file browser opens somewhere
   useful instead of `$HOME`.
5. **Shell completion** — Typer already provides `--install-completion`; it is listed but never
   mentioned in the README.
6. **Invalid input should re-prompt, not abort** — a missing directory or one with no map files
   currently exits.
7. **NO_COLOR is not respected** (known since Dec 2025).

---

## Corrections to the CI workflow added earlier today

The research pass caught three errors in my first draft of `.github/workflows/ci.yml`, now fixed:

| Was | Problem | Now |
|---|---|---|
| `astral-sh/setup-uv@v5` | Current is v10.0.1, and **no floating `v10` tag exists** (`commits/v10` → 422) | pinned to SHA `20cfd1bf…` # v10.0.1 |
| `actions/checkout@v4` | Current is v7.0.1 | pinned to SHA `3d3c42e5…` # v7.0.1 |
| `env: COLUMNS/LINES` | **No-op.** Textual's `run_test()` is headless and forces `size=(80, 24)`; nothing in the repo reads these | removed, with a comment explaining why |
| matrix `["3.10","3.13"]` | Omitted 3.14, the current stable and this project's documented baseline | `["3.10","3.11","3.12","3.13","3.14"]` |

Also added a `build-check` job (`uv build` + `cairn --help` from the built wheel) — verified to
exit 0 locally, and cheap insurance before Phase 1.

**Worth doing soon:** move `dev` deps from `[project.optional-dependencies]` to PEP 735
`[dependency-groups]`. uv installs the `dev` group **by default**, which permanently removes the
`uv sync --all-extras` trap documented in `AGENTS.md` — and PEP 735 groups are excluded from built
distributions, so the `dev` extra stops shipping in the wheel metadata once you publish. It must
land atomically with a regenerated `uv.lock`.
