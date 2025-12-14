[https://github.com/moltude/cairn/tree/main/docs](https://github.com/moltude/cairn/tree/main/docs)

I am at my wits end trying to only work from CalTopo into OnX. There are some really annoying things to debug and at the top of the list is how track/waypoints are ordered in folders and the fact that they can't be resorted even by renaming them or adding/removing them. It is just such a black box.

I want to refactor this entire project so it is bi-directional. Currently I am transforming the complete GEOJSON export from CalTopo into seperate GPX files for tracks and markers that OnX can support but now I want to make it possible for people to migrate out of OnX into CalTopo in an easier way and preserve everything they've created.

There looks like there are some issues exporting onx into Caltopo so I want to try and resolve those issues.

Help me craft some instructions for gpt 5.2 to work though adding this functionality and doing a larger refactor to add this functionality. I can provide OnX export GPX file which was imported directly into CalTopo and the exported directly from CalTopo into GEOJSON

One issue I've already found is that a single entry in OnX gets duplicated in CalTopo. Lets work through that functionality and debugging portion. Please utilize documentation from OnX export of GPX and CalTopo import of GPX and export of GEOJSON.
[https://caltopo.com/help](https://caltopo.com/help)
[https://training.caltopo.com/](https://training.caltopo.com/)

I want to maintain OnX colors and Icons and create nice human readable descriptions in CalTopo from OnX exports. There are probably some non-standard namespaces in OnX which need to be mapped.

The attached file is what was exported from CalTopo
This is the link to the map in OnX
[https://webmap.onxmaps.com/backcountry/share/content?share_id=01KCEX70KRMTSX321WTWA7P110](https://webmap.onxmaps.com/backcountry/share/content?share_id=01KCEX70KRMTSX321WTWA7P110)


---

Higher level process and instructions -- these were written by perplexity

Conceptually, there are six markdown documents plus the analysis I did on your CalTopo GeoJSON:

START_HERE.md

High-level orientation: what the project is, what files exist, and what to do in the first 30 minutes / 2 hours / 4 hours.

Quick checklist of phases and what “success” looks like at each stage.

README_AGENT_BRIEFING.md

Narrative briefing for an AI agent or human:

Explains the OnX → CalTopo → GeoJSON duplication problem with concrete examples from your test-onx-export.json.

Describes the end-state: bi-directional conversion, metadata (colors/icons) preserved, round-trip safe.

Summarizes the planned architecture and canonical data model.

DEBUG_DUPLICATION_ISSUE.md

Deep dive just into the duplication bug:

Hypotheses (CalTopo export bug vs multiple imports vs folder flattening).

Concrete experiments to run with OnX GPX and CalTopo imports/exports.

How to analyze test-onx-export.json to understand why Bass Creek TH etc. are repeated many times.

cairn_agentic_instructions.md

The “master spec” for refactoring:

Phased plan: deduplication, metadata extraction, GeoJSON→GPX, GPX→GeoJSON, validation, bi‑directional pipeline.

Proposed Python module layout (transformers/, models/, validators/, cli.py).

How to parse and preserve OnX colors/icons and embed them in CalTopo/GPX.

Testing and round‑trip validation strategy.

AGENT_PROMPTS.md

A set of 7 prompts you can hand to GPT‑4/5.2 or Claude as “work orders”:

PROMPT 1: Analyze and fix duplication via dedup engine.

PROMPT 2: OnX metadata parsing and mapping.

PROMPT 3: GeoJSON→GPX transformer.

PROMPT 4: GPX→GeoJSON transformer.

PROMPT 5: Folder structure preservation.

PROMPT 6: CLI and pipeline integration.

PROMPT 7: Documentation and knowledge transfer.

Each with explicit deliverables and success criteria.

IMPLEMENTATION_ROADMAP.md

A day‑by‑day / week‑by‑week roadmap:

Which pieces to build in which order.

Code quality and performance targets.

Risk analysis and mitigation (e.g., if CalTopo behavior is a hard bug).

(Plus): We inspected your attached test-onx-export.json and characterized the duplication pattern so that all of the above docs can talk concretely about it.
