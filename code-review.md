# Code Review

## Findings

### High: Default web storage paths point at a different data tree than the worker/keygen defaults

- `web/config.php:14`
- `web/config.php:15`
- `web/lib/bootstrap.php:13`
- `web/lib/bootstrap.php:19`
- `worker/config.json:2`
- `worker/config.json:8`
- `keygen.py:21`

The PHP app resolves relative `data_dir`/`keys_db` paths under `web/` (`web/data/...`), while the worker and keygen default to the repo-root `data/...`. With defaults, the web app writes jobs/sessions/keys to a different location than the worker reads, so auth/queue/status/history can silently operate on different databases and directories unless `web/config.local.php` is overridden.

### High: Hidden Claude memory tags can leak into the assembled "Recent" conversation context

- `wake/assemble.py:291`
- `wake/assemble.py:310`
- `wake/assemble.py:353`
- `wake/assemble.py:355`

`_load_conversation()` includes all events with a non-null actor, not just events with display tags. For Claude events that contain only non-display tags (for example `<thought>` / `<secret>`), the code falls back to stripping tags and treating the remaining text as visible `say` content. That collapses the display-vs-memory separation and can re-inject internal/secret-tag contents into future prompt conversation context.

### Medium: Polling uses `setInterval` with async fetch and no in-flight guard, which can duplicate replies

- `web/static/app.js:289`
- `web/static/app.js:294`
- `web/static/app.js:317`
- `web/static/app.js:324`

`pollJob()` is async, but `startPolling()` schedules it on a fixed interval. If a status request takes longer than 1.2s, overlapping polls can run concurrently and both observe `done`, causing duplicate UI appends for the same response.

### Medium: Non-critical bookkeeping failures can overwrite a successful job result as an error

- `worker/worker_cron.py:343`
- `worker/worker_cron.py:347`
- `worker/worker_cron.py:357`
- `worker/worker_cron.py:437`
- `worker/worker_cron.py:444`

After a successful Claude turn, `track_usage()` and `append_history()` run inside the same `process_job()` try path. If either throws (e.g., I/O/SQLite issue), the outer catch marks the job `error` and writes a generic error response, even though the model response was already produced (and token usage may already have been charged).

### Medium: `pending_recall` can be replayed after a failed Claude call

- `agents/orchestrator.py:146`
- `agents/orchestrator.py:168`
- `agents/orchestrator.py:199`

`turn()` loads previous `pending_recall` before sending to Claude, but on API failure it returns early without clearing/replacing that state. A transient failure can therefore cause the same recall results to be injected again on the next turn instead of being one-turn carryover.

## Open Questions / Assumptions

- I assumed the default configs are intended to work together without required local overrides. If `web/config.local.php` is always mandatory in deployment/dev, the path mismatch is still a sharp footgun but may be considered setup-only.
- I did not execute end-to-end tests or hit the live APIs; this is a static review pass.

## Pass 2: Qualitative / Portfolio Framing Review

This pass is intentionally framed around portfolio impact and the frontend experience (what a reviewer can actually see and infer), not hidden backend-only implementation details.

### Highest impact on portfolio perception

#### The "What Claude Sees" promise reads stronger than what the panel actually shows

- `web/index.php:104`
- `ambient.md:29`
- `web/api/context.php:7`
- `web/api/context.php:23`
- `web/api/context.php:58`
- `wake/assemble.py:522`

The product story is strongest when it emphasizes transparency, but the UI label/copy implies a full assembled prompt view while the endpoint returns a partial snapshot (working memory, events count, pending recall, usage). That can create a subtle trust gap for technical reviewers expecting the actual assembled sections (`self-state`, `recent`, `hot context`, etc.).

#### Mixed naming ("Artifact" vs "Silentstar") makes the reframing feel unfinished instead of intentionally adapted

- `ambient.md:3`
- `wake-context.md:7`

You already called this out, and it does show up in the visible experience. The inconsistency is not fatal, but it reads as "internal rename in progress" unless you explicitly frame it as "adapted from a personal system." A one-line acknowledgement would turn this from a rough edge into a strength (honest provenance).

#### API-key-only entry creates portfolio friction before the interesting part starts

- `web/index.php:54`
- `web/static/app.js:40`
- `web/static/app.js:472`

As a product demo, the best part is the live interaction + context panel. Requiring a key at the landing page means many reviewers will stop before seeing the differentiator. This is a portfolio/UX issue more than a security issue.

### Medium-impact presentation / UX notes

#### The interface is coherent and atmospheric, but the visual language is fairly standard for a portfolio showpiece

- `web/index.php:15`
- `web/static/style.css:22`
- `web/static/style.css:190`

The mood is strong (background, restrained palette, low-glow UI), but the typography (`Inter`) and overall chat-shell composition are conventional. That can undersell the originality of the architecture unless the "context transparency" interaction does more of the visual heavy lifting.

#### The most novel feature (context panel) is somewhat hidden in the interaction flow

- `web/index.php:76`
- `web/static/app.js:395`
- `web/static/app.js:400`

The context toggle is subtle, which fits the aesthetic, but it also hides the differentiator. For a portfolio audience, the design currently rewards exploration rather than guiding it.

#### Accessibility/polish: controls work, but some choices read as custom UI over native UI

- `web/index.php:86`
- `web/static/app.js:114`
- `web/static/style.css:432`

Tone chips are keyboard-enabled, which is good, but using clickable `span` elements (instead of buttons) still reads as custom-interaction code in a project that otherwise feels careful. For a portfolio reviewer, native semantics often signal maturity/polish.

#### No visible logout / session reset path in the frontend

- `web/index.php:66`
- `web/lib/auth.php:156`

There is server-side logout support, but no frontend affordance. In a portfolio/demo setting, reviewers often want to retry from a clean state or switch keys without clearing cookies manually.

### Qualitative strengths worth preserving

#### The concept-to-interface alignment is unusually strong

- `web/index.php:27`
- `ambient.md:27`
- `wake-context.md:21`
- `web/api/context.php:56`

The landing copy, prompt framing, and context-panel mechanic all point at the same idea: "assembled continuity, visible internals." That coherence is the main portfolio asset.

#### The atmosphere supports the thesis instead of competing with it

- `web/static/space.js:1`
- `web/static/style.css:9`
- `web/static/style.css:512`

The visual treatment reinforces "quiet system / memory / introspection" and avoids flashy demo aesthetics. It feels intentional and fits the project's identity.

#### The demo clearly communicates that it is an adapted architecture, not a toy chatbot skin

- `ambient.md:5`
- `ambient.md:25`
- `wake-context.md:1`

Even with imperfect reframing, the project reads as a real system distilled into a demo. That is a strong portfolio position.

## Pass 3: UX Surface Breakdown (What Users Can Actually See/Use) + CV Brag Framing

This is a user-visible inventory, not an internal code review. The goal is: given the current build, what experience exists on the frontend, what is exposed vs intentionally hidden, and what claims are credible to make on a CV/portfolio page.

### What a user can see and access (end-to-end UX)

#### 1. A branded landing page that explains the architecture before interaction

- `web/index.php:23`
- `web/index.php:27`
- `web/index.php:35`
- `web/static/space.js:91`
- `web/static/style.css:54`

Visible to the user:
- A polished landing view with project identity (`artifact`)
- High-level architecture explanation ("Persistent Memory for Stateless AI")
- A simple "how it works" list (fragments, decay, context assembly, graph edges)
- Ambient animated background / atmosphere

What this means for portfolio framing:
- You are not just presenting a chat box; you are onboarding the reviewer into a system concept before they interact with it.

#### 2. API-key gated access to the demo experience

- `web/index.php:54`
- `web/static/app.js:40`
- `web/api/auth.php:7`
- `web/lib/auth.php:82`

Visible to the user:
- Password-style key input
- Clear invalid-key error state
- Successful auth transitions directly into the chat shell (same page, SPA feel)

What they can infer:
- This is a controlled/private demo rather than a public toy
- Session-based auth is implemented (they stay logged in across refreshes)

#### 3. A single-page chat interface with immediate local echo

- `web/index.php:63`
- `web/index.php:80`
- `web/static/app.js:126`
- `web/static/app.js:133`
- `web/static/app.js:194`

Visible to the user:
- Their message appears immediately in the chat log
- Chat is structured with actor labels and timestamps
- Distinct visual treatment for visitor vs artifact messages

UX significance:
- The interface feels responsive even though backend processing is async and non-streaming.

#### 4. Tone control (casual / technical / creative) as an explicit UX feature

- `web/index.php:85`
- `web/index.php:86`
- `web/static/app.js:104`
- `agents/orchestrator.py:33`
- `agents/orchestrator.py:156`

Visible to the user:
- Tone chips in the composer area
- Active state updates immediately
- Different response styles can be tested without changing the underlying architecture

What you can credibly claim:
- You exposed model behavior controls in the UI and wired them through to prompt/system behavior.

#### 5. Async job processing UX with progress state (non-streaming but legible)

- `web/static/app.js:142`
- `web/static/app.js:253`
- `web/static/app.js:289`
- `web/api/submit.php:43`
- `web/api/status.php:36`
- `worker/worker_cron.py:4`

Visible to the user:
- A "breathing" pending indicator while the response is being generated
- Polling-based completion (response appears when job finishes)
- Graceful system messages for busy/error/budget exhausted cases

What the user experiences (important for framing):
- This feels like a queued inference system, not a fake local response
- They can perceive the separation between frontend request and backend worker processing

#### 6. Structured rendering of model output (not just plain text)

- `web/static/app.js:209`
- `web/static/app.js:212`
- `web/static/app.js:272`
- `agents/orchestrator.py:204`

Visible to the user:
- `say`, `do`, and `narrate` content rendered differently (normal / italic / dimmed)
- Basic inline markdown styling (`**bold**`, `*italic*`)

What this demonstrates:
- The frontend is aware of semantic output structure from the backend/model pipeline
- You are building a typed presentation layer over LLM output, not only dumping strings

#### 7. Live system status indicator ("bridge" online/offline)

- `web/index.php:69`
- `web/static/app.js:347`
- `web/api/status.php:13`
- `web/lib/jobs.php:44`
- `worker/worker_cron.py:266`

Visible to the user:
- Header status dot and label showing online/offline state

What this communicates:
- The demo has an operational backend worker lifecycle, and the UI reflects backend availability in real time.

#### 8. Token budget visibility as a first-class UX element

- `web/index.php:75`
- `web/static/app.js:84`
- `web/api/usage.php:7`
- `web/lib/auth.php:119`

Visible to the user:
- Remaining token budget badge in the header
- Refresh after completions
- Explicit budget exhausted message if they hit the limit

Portfolio value:
- Shows product thinking around usage limits/cost controls, not just technical experimentation.

#### 9. Persistent conversation history (per authenticated user/session)

- `web/static/app.js:371`
- `web/api/history.php:8`
- `web/lib/history.php:19`
- `worker/worker_cron.py:239`

Visible to the user:
- Prior messages reload into the chat log when they enter the app again
- History contains both their messages and structured model display spans

What they can infer:
- The app persists interactions server-side and reconstructs UI state from stored data
- This is beyond a transient frontend-only prototype

#### 10. A "What Claude Sees" context panel (debuggable AI UX)

- `web/index.php:103`
- `web/index.php:104`
- `web/static/app.js:393`
- `web/static/app.js:404`
- `web/api/context.php:7`
- `web/api/context.php:56`

Visible to the user:
- Toggleable side panel
- Turn counter
- Token budget snapshot
- Active working memory items
- Event count
- Pending recall entries and neighbors

This is the biggest UX differentiator:
- The user can inspect the memory system state instead of treating the model as a black box.

#### 11. Mobile-responsive and reduced-motion-aware presentation

- `web/static/style.css:593`
- `web/static/style.css:606`
- `web/static/space.js:13`
- `web/static/space.js:160`
- `web/static/space.js:230`

Visible to the user:
- Full-width context panel on mobile
- Layout compression on smaller screens
- Reduced-motion users get a static background instead of animation

What this demonstrates:
- The demo is designed as a real product surface, not only a desktop screenshot experience.

### What users do NOT directly access (by design)

This matters because it clarifies what claims should be framed as "architecture behind the demo" versus "visible product features."

#### Hidden implementation layers (backend/private)

- `worker/worker_cron.py`
- `agents/orchestrator.py`
- `wake/assemble.py`
- `wake/decay.py`
- `wake/recall.py`

Users do not directly see:
- Prompt assembly internals
- SQLite schemas/tables
- Worker lock/cron mechanics
- Full fragment tiers (unless surfaced in conversation)
- Raw Claude response text (only display spans are shown)

CV framing implication:
- Phrase these as "implemented backend architecture supporting the demo," not as user-facing features.

#### Partial transparency (important nuance)

- `web/api/context.php:23`
- `web/api/context.php:58`

Users can see a context snapshot, but not the full exact prompt package as sent to the model. The current panel is still a strong transparency feature, just best described as "runtime memory/context inspector" rather than "verbatim prompt viewer."

### What is especially brag-worthy (supported by the current UX)

These are strong, defensible claims because they are either directly visible or easy to verify during a demo.

#### Product/UX brag points

1. Built a custom AI chat interface that exposes internal memory state to the user via an inspectable context panel.
2. Designed a structured response rendering pipeline (`say` / `do` / `narrate`) so model output drives differentiated UI presentation.
3. Implemented an asynchronous job-based inference UX (queued submit + polling + worker status) with clear progress and error states.
4. Added user-selectable communication tone controls that affect model behavior in real time.
5. Added token budget visibility and exhaustion handling as a first-class product constraint, not an afterthought.
6. Implemented persistent per-user conversation history and session continuity in a lightweight stack.
7. Shipped a polished, atmospheric frontend that supports mobile layouts and reduced-motion accessibility.

#### Architecture/system brag points (safe to claim, but frame as backend support)

1. Built a memory-oriented AI runtime with context assembly, working memory, recall, and decay-based selection.
2. Implemented a per-user isolated session model backed by SQLite and filesystem job queues.
3. Separated visible chat output from internal memory tags, enabling structured ingestion and memory updates.
4. Built a lightweight deployment-friendly stack (PHP + Python + SQLite + vanilla JS) without framework dependencies.

### CV / portfolio wording you can use (evidence-aligned)

These are phrased to match what the project demonstrably does today.

#### Resume-style bullets (technical + product)

1. Built a full-stack AI demo platform (PHP, Python, SQLite, vanilla JS) showcasing a custom memory architecture for stateless LLMs.
2. Designed an interactive "context inspector" UI that exposes working memory, recall state, and token budgets to make model behavior debuggable and transparent.
3. Implemented structured LLM output rendering (`say`/`do`/`narrate`) to support semantic presentation rather than plain-text chat output.
4. Developed an async job/worker inference pipeline with frontend polling, live worker availability status, and resilient error/busy handling.
5. Added per-user session isolation and persisted conversation history with lightweight storage primitives (filesystem queues + SQLite).
6. Built a production-minded UX with responsive layout, motion-aware animation behavior, and clear operational telemetry in the interface.

#### Portfolio blurb angle (less resume, more narrative)

This demo turns a memory architecture into an inspectable product experience. Instead of hiding the system behind a chat box, it lets users see working memory, recall state, and token constraints while interacting with the model. The result is both a technical backend experiment and a UX exploration of transparent AI interfaces.

### Claims to qualify (to stay precise and credible)

These are still valid ideas, but they should be phrased carefully based on the current frontend surface.

1. Prefer "context/memory inspector" over "full prompt viewer" unless you expose the exact rendered prompt.
2. Prefer "async queued responses" over "streaming" (the current UX is polling-based, not token streaming).
3. Prefer "demo with private key access" over "public product" unless you add a guest path.

## Pass 4: Recommendations + Exact Wording (Thorough)

This pass answers:
- What should be improved next?
- How can the demo be described more clearly?
- How can more of Silentstar's design language be incorporated without exposing private/personal content?

This section includes exact wording suggestions you can paste (or adapt) into the visible copy and prompt framing.

### Executive recommendation (highest ROI)

If you change only three things, do these:

1. Add explicit provenance framing: Artifact is a public, privacy-safe slice of Silentstar.
2. Reframe the context panel as an inspector (accurate transparency claim).
3. Introduce a visible "Artifact Map" (Seven Artifacts + status) to import Silentstar's strongest design language into the portfolio UX.

Why this matters:
- It resolves the current "rename in progress" feeling.
- It increases trust (reviewers understand what is shown vs hidden).
- It makes the project read as a coherent system design, not only a chat demo.

### Where the current description is underspecified (and how to fix it)

#### 1. Provenance is implied but not stated

- `ambient.md:3`
- `wake-context.md:7`
- `../silentstar/ARCHITECTURE.md:11`

Current impression:
- The app clearly references a larger architecture ("Silentstar"), but the UI does not explicitly explain that Artifact is a public adaptation of a private system.

Effect on reviewers:
- Some will read this as unfinished renaming instead of intentional curation.

Fix:
- Add one concise provenance sentence in the landing page and a matching sentence in `ambient.md`.

#### 2. Transparency language is stronger than the current surface

- `web/index.php:104`
- `ambient.md:29`
- `web/api/context.php:56`

Current impression:
- "What Claude Sees" + "Visitors can see exactly what I see" implies full prompt visibility.
- Current panel shows an important subset, not the exact rendered prompt.

Effect on reviewers:
- Technical reviewers may feel a small mismatch once they inspect the panel.

Fix:
- Rename and scope the claim precisely ("runtime memory inspector", "partial context snapshot").

#### 3. Silentstar's strongest design idea is mostly hidden in internal docs

- `../silentstar/ARCHITECTURE.md:21`
- `../silentstar/ARCHITECTURE.md:63`

Current impression:
- Artifact demonstrates the mechanics, but less of the conceptual design grammar (artifact roles, delegation line, what belongs to Heart vs Loom vs Lens, etc.).

Effect on reviewers:
- They may leave with "cool memory chat" rather than "this person designed a full system with role boundaries and operating model."

Fix:
- Surface the artifact vocabulary visually in a small, honest "architecture map" section with statuses.

### Exact wording pack (portfolio-safe, accurate, stronger)

These are phrased to match what the demo currently does.

#### A. Landing page hero / description (`web/index.php`)

- `web/index.php:25`
- `web/index.php:26`
- `web/index.php:27`
- `web/index.php:35`

##### Recommended hero subtitle (replace current `hero-sub`)

Option A (most direct):
- `A public demo of a private memory architecture for stateless AI`

Option B (more product-y):
- `Inspectable memory and context assembly for stateless AI`

Option C (portfolio framing first):
- `Portfolio demo: transparent runtime memory for LLM conversations`

##### Recommended hero description (replace current `hero-description`)

Suggested text:

> Artifact is a privacy-safe portfolio distillation of Silentstar, my personal persistent-memory architecture for Claude.  
> It demonstrates how a stateless model can feel continuous by assembling context each turn from working memory, graph-linked knowledge fragments, recent conversation, and runtime state.  
> Instead of hiding the system behind a chat UI, Artifact exposes a live inspector so visitors can see memory and recall state change during interaction.

Why this wording works:
- It explains the Silentstar reference
- It avoids overclaiming ("distillation" instead of "full system")
- It highlights the inspectability differentiator

##### Recommended "how it works" step labels (clearer + more outcome-oriented)

Suggested replacements for `web/index.php:38-50` labels:

1. `Knowledge is stored as graph-linked fragments (ambient / recognition / inventory)`
2. `Working memory is updated from tagged responses and decays over time + turns`
3. `Context is assembled fresh for every reply (not stored inside the model)`
4. `A runtime inspector exposes memory state, recall queue, and token usage`

These communicate user-visible outcomes and the underlying mechanism in the same line.

#### B. Key-gate framing (`web/index.php`, `web/static/app.js`)

- `web/index.php:54`
- `web/index.php:58`
- `web/api/auth.php:16`

If you want to keep the API key gate (reasonable for a portfolio demo), make it feel intentional with a microcopy line near the form:

Suggested helper text (below the key form):

> Private demo access. Keys are used to isolate sessions and token budgets per reviewer.

This turns a potential friction point into evidence of product thinking.

If you later add a guest mode, suggested copy:

> Use a reviewer key for a persistent session, or continue in guest mode for a temporary sandbox.

#### C. Context panel rename + accuracy copy (`web/index.php`, `web/static/app.js`)

- `web/index.php:104`
- `web/index.php:105`
- `web/static/app.js:415`
- `web/static/app.js:427`
- `web/api/context.php:7`

##### Recommended panel title

Replace:
- `What Claude Sees`

With:
- `Context Inspector`

##### Recommended panel subtitle (new line under title)

Suggested text:

> Live runtime snapshot: working memory, recall state, events, and token usage (not the full prompt payload).

This is one of the highest-value wording fixes in the whole project.

##### Recommended section label changes inside the panel

Current labels are functional; these versions read more like an intentional debugging UX:

- `Turn` -> `Current Turn`
- `Token Budget` -> `Token Budget (Session)`
- `Working Memory` -> `Active Working Memory`
- `Events Logged` -> `Events (Session Log Count)`
- `Pending Recall` -> `Recall Queue (Next Turn)`

These labels explain time-scope and lifecycle, which helps reviewers understand what they are looking at.

##### Recommended empty-state copy for inspector

Current empty states are terse (`No active items`, `None`, `Failed to load context`).

Suggested alternatives:
- Working memory empty:
  - `No active memory items yet. Tagged thoughts/pins/plans will appear here after responses.`
- Recall queue empty:
  - `No queued recalls. Recall requests issued this turn appear on the next turn.`
- Inspector load failure:
  - `Inspector unavailable right now. The conversation can continue, but runtime state could not be loaded.`

#### D. First-run guidance (show the differentiator earlier)

- `web/static/app.js:73`
- `web/static/app.js:400`
- `web/static/app.js:404`

Without changing the architecture, a tiny copy addition can increase comprehension a lot.

Suggested one-time system message after `enterChat()` (or after first completed response):

> Tip: Open the Context Inspector in the header to watch working memory and recall state change as you chat.

Alternative (more technical audience):

> Tip: This demo exposes runtime memory state. Open the Context Inspector to see active memory, recall queue, and token usage update per turn.

#### E. `ambient.md` reframing (public slice of Silentstar)

- `ambient.md:1`
- `ambient.md:3`
- `ambient.md:25`

Current `ambient.md` is good but can be clearer about being an adapted/public slice.

Suggested replacement for the opening paragraph:

> I'm a public demonstration of the Silentstar memory architecture.  
> My knowledge in this demo describes the system itself (not the private personal data used in the original version).

Suggested replacement for the "How I Work" paragraph:

> Every turn, the assembler rebuilds my context from persistent knowledge fragments, decay-scored working memory, recent conversation, and the current message. I remain stateless between turns; continuity comes from context assembly, not hidden model memory.

Suggested replacement for the final line (`ambient.md:29`):

> Visitors can open the Context Inspector to see a live runtime snapshot of memory, recall state, and usage.

This keeps the spirit while fixing the "exactly what I see" overclaim.

#### F. `wake-context.md` prompt wording (public-demo guardrails + clearer UX behavior)

- `wake-context.md:1`
- `wake-context.md:21`
- `wake-context.md:28`
- `wake-context.md:47`

The current prompt is strong. The main opportunity is to align it with the public/portfolio framing and the inspector naming.

Suggested replacement for opening two lines:

> You are the public demonstration instance of Artifact, a portfolio-safe slice of the Silentstar memory architecture.  
> Your knowledge in this environment is intentionally limited to architecture and system behavior (not private personal data from the original system).

Suggested replacement for the recall guidance paragraph (`wake-context.md:21-29` equivalent):

> If the visitor asks about a concept you recognize from ambient fragment keys (for example `[decay]`, `[recall]`, or `[context-assembly]`), proactively issue a `recall(...)` request so you can answer with more detail.  
> Recall results arrive on the next turn. If you issue one, tell the visitor what you are pulling and suggest they open the Context Inspector to watch the recall queue.

Suggested tweak to "Important" section:

Replace:
- `Point visitors to the context panel (toggle in header) to see working memory, recall results, and token usage`

With:
- `Point visitors to the Context Inspector (toggle in header) to see runtime memory state, recall queue, and token usage`

This improves terminology consistency across prompt + UI.

### How to incorporate more of Silentstar's design (without private content)

This is the biggest strategic opportunity.

#### 1. Add an "Artifact Map" using the Seven Artifacts language (with explicit status labels)

- `../silentstar/ARCHITECTURE.md:21`
- `../silentstar/ARCHITECTURE.md:63`
- `../silentstar/README.md:3`

Why this is valuable:
- Silentstar's artifact vocabulary is unusually memorable and demonstrates system design maturity.
- You can expose the design grammar without exposing personal context.

Recommended UI pattern (landing page or collapsible panel):
- Title: `Architecture Map`
- Subtitle: `Artifact is a public demo slice of the larger Silentstar system`

Suggested artifact cards (exact wording, portfolio-safe):

1. `Heart` — `The conversational runtime (the visible chat experience in this demo).`  
   Status: `Live in demo`
2. `Gem` — `The fragment knowledge store (graph-linked memory fragments used for recall).`  
   Status: `Live in demo`
3. `Lens` — `Read/exploration tools for inspecting the knowledge graph and memory state.`  
   Status: `Concept shown; read-only explorer can be added`
4. `Loom` — `Multi-agent analysis/facet system for second-opinion enrichment.`  
   Status: `Part of parent architecture`
5. `Mirror` — `Compression pipeline that reflects past interactions into structured summaries.`  
   Status: `Part of parent architecture`
6. `Compass` — `Planning agent for autonomous suggestions and long-horizon direction.`  
   Status: `Part of parent architecture`
7. `Anvil` — `The authoring workflow where the system and knowledge are shaped collaboratively.`  
   Status: `Outside this demo (development workflow)`

Important UX note:
- The status labels are the key. They prevent the map from feeling like vaporware and make the demo feel honest.

#### 2. Surface the Delegation Line as a "role boundaries" section

- `../silentstar/ARCHITECTURE.md:63`

Why this is strong for a portfolio:
- It communicates that you designed operating boundaries, not just features.

Suggested title:
- `Role Boundaries (What this demo does vs what the parent system does)`

Suggested copy:

> Artifact demonstrates the runtime conversation layer and inspectable memory state.  
> The broader Silentstar architecture also includes authoring, compression, and multi-agent analysis workflows that are not exposed in this public demo.

Suggested simple table labels:
- `In this demo`: Chat runtime, memory updates, recall, history, token budgets, runtime inspector
- `In Silentstar (parent system)`: Compression (Mirror), multi-agent enrichment (Loom), planning (Compass), authoring workflows (Anvil), read tooling (Lens)

#### 3. Add a read-only "Lens" micro-feature (best next feature for brag value)

- `../silentstar/ARCHITECTURE.md:50`
- `../silentstar/README.md:30`

This is the single best Silentstar concept to transplant into Artifact because:
- It is portfolio-safe
- It is user-visible
- It concretely proves the fragment/graph architecture
- It complements the chat + inspector flow

Minimum viable version (frontend-visible):
- Search a fragment key
- Show tiers (`ambient`, `recognition`, `inventory`)
- Show neighboring fragment keys and relations
- Mark it read-only

Suggested UI title:
- `Lens (Read-Only Fragment Explorer)`

Suggested subtitle:
- `Inspect the knowledge graph directly: fragment tiers, links, and recall targets.`

This would materially improve the "what can I brag about?" answer.

#### 4. Borrow Silentstar's stronger operational polish patterns

- `../silentstar/web/index.php:83`
- `../silentstar/web/api/stream.php:8`
- `../silentstar/web/sw.js:1`
- `../silentstar/web/static/style.css:786`

Recommended imports (in order):

1. `Logout / reset session` control  
Why: lets reviewers restart without manual cookie clearing; signals product completeness.

2. Better mobile ergonomics (tap target sizing, safe-area padding)  
Why: your Artifact UI is already decent; this makes it feel production-ready.

3. Service worker shell caching (optional but strong portfolio signal)  
Why: small feature, strong "I think beyond the happy path" signal.

4. SSE streaming (later, not required)  
Why: premium UX, but not necessary for the current architecture story.

### Wording strategy for CV / portfolio / interviews (clear and credible)

This section is about how to describe the project without underselling it or overclaiming it.

#### 1. Recommended one-line description (portfolio header)

Option A:
- `Artifact is a public, privacy-safe demo of my Silentstar memory architecture: an inspectable runtime for context assembly, working memory, and graph-based recall in a stateless LLM chat experience.`

Option B (shorter):
- `A portfolio-safe slice of Silentstar: transparent memory and context assembly for stateless LLM conversations.`

#### 2. Recommended two-paragraph portfolio description

Suggested text:

> Artifact is a public demonstration of Silentstar, a persistent-memory architecture I built for stateless Claude conversations. This version intentionally removes private/personal data and focuses on the architecture itself: graph-linked knowledge fragments, working memory that changes over time, and per-turn context assembly.  
>  
> The key UX idea is transparency. Instead of presenting a black-box chat interface, Artifact exposes a runtime inspector that shows active memory, recall state, and token constraints while the user interacts with the model. It demonstrates both backend systems design (worker queue, per-session storage, context assembly) and frontend product thinking (inspectability, operational status, graceful async UX).

#### 3. Interview-ready explanation (what is built vs what is represented)

Suggested wording:

> Artifact is the public-facing runtime slice. It includes the chat experience, per-session memory state, graph recall, and a context inspector. Silentstar is the broader architecture around it, with additional systems like authoring workflows, multi-agent enrichment, and compression pipelines that aren't exposed in this demo because they depend on personal/private data and workflows.

This sentence prevents confusion and makes the relationship between the two codebases a strength.

### Suggested information architecture for the Artifact landing page (copy-first)

This is a content structure recommendation, not a UI redesign requirement.

Suggested order:

1. `artifact` (title)
2. One-line provenance (`public demo of Silentstar`)
3. Two-paragraph explanation (what it demonstrates + why inspectability matters)
4. `How it works` (4 concise steps)
5. `Architecture Map` (Seven Artifacts + status chips)
6. Access form (API key)
7. Small footer note: `Private demo keys create isolated sessions and separate token budgets`

Why this order works:
- It answers "what is this?" before "how do I log in?"
- It gives your conceptual design language a visible place
- It makes the login gate feel justified instead of arbitrary

### Exact wording for an "Architecture Map" section (drop-in copy)

Use this if you add a new section in the landing page.

#### Section title
- `Architecture Map`

#### Section subtitle
- `Artifact is a public demo slice of Silentstar. Some artifacts are live here; others belong to the parent system's private workflows.`

#### Intro sentence
- `The names below are design roles, not marketing labels: they describe what each part of the system is responsible for.`

#### Card copy (compact version)

1. `Heart` — `The conversational runtime (chat + reply generation experience).` — `Live in demo`
2. `Gem` — `The fragment knowledge store and graph recall source.` — `Live in demo`
3. `Lens` — `Read tools for inspecting fragments and memory.` — `Partially represented`
4. `Loom` — `Multi-agent second-opinion / enrichment workflows.` — `Parent system`
5. `Mirror` — `Compression pipeline for reflecting past interactions.` — `Parent system`
6. `Compass` — `Planning and long-horizon suggestion system.` — `Parent system`
7. `Anvil` — `The authoring workflow where the system is shaped.` — `Development workflow`

### Exact wording for a "What this demo exposes" section (optional but excellent for trust)

Suggested title:
- `What You Can Inspect Here`

Suggested bullets:

1. `Structured chat output (say / do / narrate display spans)`
2. `Runtime memory state (active working memory items)`
3. `Recall queue state (what will be pulled next turn)`
4. `Per-session token budget usage`
5. `Per-session conversation history`
6. `Backend worker availability (online/offline status)`

Suggested closing line:

> This demo exposes runtime behavior, not the full private authoring and maintenance workflows of the parent system.

### Prioritized implementation roadmap (if you want to strengthen the portfolio quickly)

This is scoped around maximizing brag-value per unit effort.

#### Tier 1 (copy + framing only, high impact, low effort)

1. Add provenance line ("public slice of Silentstar")
2. Rename `What Claude Sees` -> `Context Inspector`
3. Update ambient/prompt wording to match inspector terminology
4. Add a first-run tip pointing users to the inspector

#### Tier 2 (small UI additions, high impact)

1. Add `Architecture Map` section with Seven Artifacts + statuses
2. Add logout/reset session control
3. Add inspector subtitle clarifying partial transparency

#### Tier 3 (feature additions, very high brag value)

1. Add read-only `Lens` fragment explorer
2. Add SSE streaming (if desired)
3. Add PWA shell caching/service worker

### Final recommendation on tone

Lean into:
- `public demo of a private system`
- `inspectable runtime`
- `transparent AI UX`
- `portfolio-safe slice`

Avoid (unless you implement more surface):
- `full prompt transparency`
- `streaming`
- `full Silentstar`

This framing makes Artifact feel more intentional, more credible, and more connected to the strength of Silentstar's design language.
