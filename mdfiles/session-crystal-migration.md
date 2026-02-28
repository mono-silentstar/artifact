# Session: Crystal Migration & Architecture Reframing
## 2026-02-28

---

## The Three Things

**The Workshop** — Hero + Council + Crystal + Scribe. Portable toolkit that lives in *every* project. The engine.

**Silentstar** — A project running on the workshop. The Heart (live Claude with personality, WM, feelings, Mirror). Personal, intimate. Contains Mono's private data.

**Artifact** — Two roles:
1. The repo where we *build* the workshop itself.
2. The portfolio that *showcases* both silentstar and the workshop.

The portfolio has two parts:
- A landing page explaining how everything works
- A login to access a public demo (silentstar-shaped but with demo data, not personal info — e.g., chess games from this year)
- A link to the public github showing the workshop code

### Workshop as Stem Cell
The workshop needs to be bootstrappable into any new project. Some kind of init — an instruction.md or seed script that stands up the crystal DB, the schema, and the basic tooling. Like `npx create-workshop` conceptually.

---

## Architecture

### What Lives Where

**Every project gets:**
- The workshop (Hero, Council, Scribe, crystal DB, compass algorithm, map)
- Project-specific crystal types that emerge from the domain
- Boot file(s) — plain text system prompt, like CLAUDE.md. Simple.

**Silentstar additionally gets:**
- Heart (live conversation Claude with personality)
- Mirror (conversation compression)
- Working Memory (feelings, thoughts, decay — Heart-only)
- Heart does NOT have access to Council

**The public demo gets:**
- Heart + Mirror + Compass + Map + Crystal
- Same architecture as silentstar, but with impersonal demo data
- Showcases the system without exposing private information

### Crystal Fragmentation
Within a single project, there can be many crystal shards — as many as the complexity demands. One DB per logical unit, or multiple if needed. Some might be volatile/temporary (archived on commit), others permanent. The whole thing should feel like a **living membrane** that grows with the project.

No strict "one DB at this path" rule. Fragment storage to match the project's shape:
- A volatile shard for in-progress work (gets archived)
- A stable shard for established knowledge
- Edges connect across shards

### Boot Files
Boot files are just boot files. Plain text system prompt. Gets loaded into wake context. Like CLAUDE.md. Not crystals — they're the thing that exists *before* crystals are queryable.

---

## Crystal System

### Schema (Universal)

```sql
-- Active crystals (current, live knowledge)
crystals (
  key       TEXT PRIMARY KEY,
  type      TEXT NOT NULL,       -- freeform, project-dependent
  summary   TEXT NOT NULL,       -- 1-2 lines, always loadable
  body      TEXT,                -- full content, loaded on recall
  edges     TEXT,                -- JSON array of {key, relation, directed}
  reasoning TEXT,                -- WHY this version exists / was changed
  created   TEXT NOT NULL,
  updated   TEXT NOT NULL
)

-- Version history (chronological per crystal)
crystal_legacy (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  key       TEXT NOT NULL,       -- which crystal this was
  type      TEXT NOT NULL,
  summary   TEXT NOT NULL,
  body      TEXT,
  edges     TEXT,
  reasoning TEXT,                -- why THIS version was superseded
  created   TEXT NOT NULL,       -- when this version was created
  archived  TEXT NOT NULL        -- when it was superseded
)

-- Edge index (for graph queries)
crystal_edges (
  source    TEXT NOT NULL,
  target    TEXT NOT NULL,
  relation  TEXT NOT NULL,       -- freeform
  directed  INTEGER DEFAULT 1,  -- 1 = directional, 0 = bidirectional
  PRIMARY KEY (source, target, relation)
)

-- Cross-version edges (temporal context)
crystal_version_edges (
  legacy_id         INTEGER NOT NULL,
  related_legacy_id INTEGER NOT NULL,
  relation          TEXT NOT NULL,
  FOREIGN KEY (legacy_id) REFERENCES crystal_legacy(id),
  FOREIGN KEY (related_legacy_id) REFERENCES crystal_legacy(id)
)
```

### Crystal Types: Freeform, Project-Native
- Not a fixed enum. Not pre-declared. Emerge organically.
- A coding project: design, code, api-contract, dependency
- A makeup project: facial-structure, color-theory, product-inventory
- A creative writing project: character, world, plot, theme
- The schema is universal. The types grow from the domain.

### Crystal Versioning (Per-Fragment History)
When Hero updates a crystal body, old version → legacy table chronologically.
- No naming needed — time ordering is sufficient.
- Reasoning field captures WHY the change happened.
- Cross-version edges capture what was concurrent (e.g., "mirror v2 was active alongside heart v1").
- Cross-version edges created by Hero (Claude Code) or delegated to spawned agents (with trust verification).

### Crystal Splitting
- Hero/Council/Scribe flag when a crystal is too broad
- Mono approves
- Two-tier structure (summary + body) — if it needs a third tier, split it

### Edge System
- **Both:** Self-contained in crystal JSON + separate index for graph queries
- **Both:** Directed when naturally directional, undirected when not. Stored with a flag.
- **Freeform** relation strings
- **Legacy edges:** Archived with the crystal version

---

## The Workshop Agents

### Hero
The human + Claude Code as a fluid unit. Mono has final say ("truth is mine to command") but expects Claude Code to maintain crystals proactively.

**Crystal maintenance is housekeeping.** If Claude Code doesn't do it, next /compact everything is lost. Same instinct as maintaining this session doc — but with better structure than a flat .md file.

Claude Code should think: "I'm smart but forgetful. The crystal DB is my external memory. Edges help me understand relationships. Depth levels let me grasp structure without wasting context on implementation details. I should use this to make my own life easier."

### Council
Four sages (Cataloguer, Interpreter, Researcher, Skeptic) — designed to be multi-purpose across project types. Can review later but believed to be general enough.

**Timing is flexible:** Gate before writes, audit after, or on-demand second opinion. Called whenever practical.

**Heart has NO access to Council.** Council is purely a workshop/offline tool.

### Scribe
Helps preserve context. Surveys and documents before action. Delegates compression of large outputs. Essential for protecting Hero's (Claude Code's) context window.

### Compass
**NOT a Claude.** Infrastructure — the read/write algorithm that surfaces map-crystal content into Heart's assembled context. The postal service, not a person.

### Mirror
**Silentstar-only (Heart side).** Conversation compression pipeline. Own lane — does not interact with crystals. Haiku drafts → Sonnet refines → staged summaries.

---

## Existing Implementation
Heart's crystal access patterns (recall, surfacing, FTS, budgets) are already implemented in silentstar. Refer to silentstar's codebase rather than re-specifying:
- `wake/compass.py` — surfacing algorithm
- `wake/recall.py` — crystal/fragment recall
- `wake/assemble.py` — context assembly with budgets
- `wake/decay.py` — half-life scoring

---

## Decisions Summary

| Topic | Decision |
|-------|----------|
| Storage | SQLite. Fragmented per project needs. |
| Crystal types | Freeform strings. Project-native. |
| Legacy | Per-version archival. Old body → legacy table chronologically. |
| Edges | Both self-contained + index. Freeform relations. Directional flag. |
| Boot files | Plain text. Not crystals. System prompt. |
| WM | Silentstar/Heart only. Artifact doesn't need it. |
| Compass | Algorithm, not an agent. Surfaces map→Heart. |
| Mirror | Own lane. Conversation compression only. |
| Council access | Workshop only. Heart cannot call Council. |
| Council timing | Flexible. Gate, audit, or on-demand. |
| Hero identity | Fluid. Mono + Claude Code. Mono has final say. |
| Crystal maintenance | Claude Code does it proactively (housekeeping). |
| Cross-version edges | Created by Hero/Claude Code or trusted delegates. |
| Splitting | Agents flag, Mono approves. |
| Workshop portability | Lives in every project. Bootstrappable via init/stem cell. |
| Public demo | Heart + Mirror + Compass + Map + Crystal with demo data. |
| Self-dogfooding | Yes. Artifact's own architecture stored in its own crystals. |

## Map Crystals
Definition still fuzzy. General sense:
- Async signaling: Hero → map → compass → Heart
- Plan persistence: `<plan>do this</plan>`, `<plan>we implemented this</plan>`
- Will clarify through implementation. No forced definition.

## Final Clarifications

**Bootstrap: Instruction over template.**
- No template DB. Too rigid.
- An `instruction.md` (or similar) that Hero reads on first session and follows.
- Crystal types emerge organically from the first conversation, not pre-declared.

**Write first, always.**
- When learning something important mid-session, write the crystal FIRST, before doing anything else.
- Crystal maintenance is the first instinct, not an afterthought or a batch job.
- This is how Claude Code fights forgetting across /compact boundaries.

**No special read/write tooling needed.**
- Claude Code can just read/write SQLite directly.
- Lens exists in silentstar for Heart's use, but Hero doesn't need a tool — it IS the tool.

**populate_demo.py is heart fragments, not workshop.**
- Demo fragment population is a Heart concern (for the public demo).
- Workshop itself doesn't need pre-populated demo data.

**Migration is not our job right now.**
- Silentstar migration happens later: go into silentstar, read instruction.md, repopulate fresh.
- Workshop just needs to be ready to receive that.

**Volatile crystal archival:**
- "Commit" as a full stop makes sense conceptually.
- Doesn't have to be git commit specifically. Could be any deliberate checkpoint.
- Not rigid — figure out what feels right in practice.

---

## Build Plan (Today)

### Phase 1: Workshop (framing + init) — DONE
- `workshop/instruction.md` — stem cell, project-agnostic bootstrap instructions
- `workshop/schema.py` — crystal schema v1 (crystals, crystal_legacy, crystal_edges, crystal_version_edges, crystals_fts)
- `data/crystals.sqlite` — 7 design crystals describing artifact's own architecture (dogfooding)
- `seed_crystals.py` — initial seeder
- Verified: CRUD, FTS search, edge traversal, automatic legacy archival on update

### Phase 2: Beating Heart Demo — DONE

**All changes:**
1. `ingest/parse.py` — added PLAN_RESOLVE_WORDS, PLAN_CANCEL_WORDS, plan lifecycle modifiers
2. `wake/recall.py` — added plans(), PlanSummary, _classify_plan_phase; flipped default to deep=True
3. `wake/schema.py` — v4: added working_memory_deps table
4. `wake/summaries_schema.py` — v2: added generation column for rolling Mirror
5. `wake/compass.py` — NEW FILE: full Compass surfacing algorithm (ported from silentstar)
6. `wake/assemble.py` — wired Compass: surfaced field on WakePackage, compass_surface call, Surfaced render section. Rolling summary loading (single latest, not multi-row).
7. `agents/mirror.py` — rolling model (prior_summary folded into Opus pass), generation tracking, simpler token-volume trigger (1500 tokens), decay sweep after compression
8. `wake/decay.py` — added sweep_decayed() with CONTEXT_THRESHOLD/SWEEP_THRESHOLD constants

**All imports verified clean.**

### Phase 3: Demo Data
Populate the demo's crystal with interesting, public data.
Something the training data shouldn't have (e.g., chess games from this year).

### Then that's a day.
