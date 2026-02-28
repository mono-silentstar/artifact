#!/usr/bin/env python3
"""
populate_demo.py — Seed the artifact.sqlite database with meta fragments.

These fragments describe Silentstar's own architecture, making the demo
self-documenting. The AI knows about itself because its knowledge *is* itself.

Run once:
    python populate_demo.py
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "artifact.sqlite"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


FRAGMENTS = [
    # --- Core architecture ---
    {
        "key": "context-assembly",
        "ambient": "The assembler builds my context window fresh every turn. Seven sections in fixed order: activation, self-state, working memory, recalled fragments, conversation history, current time, hot context.",
        "recognition": "Context assembly is the core pipeline. It reads everything that matters and constructs the prompt I wake up inside of. Order is inviolable: (1) Activation — who I am (wake-context.md), (2) Self-State — what I know (ambient.md), (3) Working Memory — decay-scored active knowledge, (4) Recalled — lookup results from previous turn, (5) Recent — conversation history via FIFO pools, (6) Current Time, (7) Hot Context — the current message. Budget defaults: WM=1500 tokens, conversation=5000 (split across 4 pools), recall=1000.",
        "inventory": "The assembler (wake/assemble.py) uses WakeConfig for paths and budgets, produces a WakePackage. Working memory is scored by type-specific decay (feelings fade fast, pins linger). Conversation uses pool-based FIFO allocation: visitor_pool (1500), claude_say_pool (1500), claude_do_pool (1000), flex_reserve (1000). Each pool fills independently, overflow spills to flex. A single event can split across pools — Claude's say goes to say pool, do goes to do pool. Token estimation: ~4 chars per token. The render step splits into system prompt (activation only) and user message (everything else), maintaining clean separation for the API.",
    },
    {
        "key": "fragments",
        "ambient": "Knowledge lives in fragments — three-tier storage with ambient (always visible), recognition (shallow lookup), and inventory (deep detail). Connected by edges forming a graph.",
        "recognition": "Fragments are the compiled knowledge system. Three tiers: ambient text appears in every context window (the things I always know), recognition is pulled on shallow recall (the story of a thing), inventory is deep lookup (full technical detail). Fragment keys are lowercase-hyphenated identifiers referenced in [brackets] in ambient prose. Edges connect fragments bidirectionally with optional relation labels, enabling neighbor-pull: when I recall one fragment, adjacent ones surface briefly at ambient depth.",
        "inventory": "Schema: fragments(key TEXT PRIMARY KEY, ambient TEXT, recognition TEXT, inventory TEXT, created_at TEXT, updated_at TEXT). fragment_edges(source_key, target_key, relation). fragment_sources links fragments to events they were compiled from. The ambient tier is special — it's what I *always* know, the vocabulary of my world. Recognition is what I learn when I tug a thread. Inventory is everything — the technical deep-dive that most conversations don't need. Not all fragments have all tiers; some are ambient-only (always present but never deeper).",
    },
    {
        "key": "decay",
        "ambient": "Memories decay along two axes: time elapsed and turns elapsed. Each type has its own half-life. Feelings vanish fast, pins linger for weeks, secrets never fade.",
        "recognition": "Decay uses exponential half-life curves on both time and turn axes, combined multiplicatively. Type-specific profiles: feelings (2h/3 turns), thoughts (12h/8 turns), patterns (168h/60 turns), pins (336h/100 turns), secrets (never). Conversation has its own profile (48h/20 turns). The pressure mechanic: when working memory fills up, conversation decays faster — 'shut up, let me think.' Timed plans use a special submersion curve: creation spike → submerged floor (0.08) → resurface 48h before due → post-due grace period.",
        "inventory": "Implementation in wake/decay.py. DecayProfile(time_half_life_hours, turn_half_life, floor). DecayParams has global_time_scale, global_turn_scale, and pressure (0.0-1.0+). Pressure applies only to conversation decay via multiplier 1/(1+pressure). The select_within_budget() function scores all fragments, sorts by score descending, fills the budget greedily, then re-sorts chronologically for natural reading. Score threshold: 0.01 (below = imperceptible). Timed plan curve uses smooth cubic ease-in for phase transitions. PLAN_CREATION_SPIKE_HOURS=4, PLAN_SUBMERGED_FLOOR=0.08, PLAN_RESURFACE_HOURS=48, PLAN_POST_DUE_GRACE_HOURS=24.",
    },
    {
        "key": "working-memory",
        "ambient": "Working memory holds active knowledge: feelings, thoughts, patterns, plans, pins, secrets. Each type decays at its own rate. Items can be created, refreshed, or dropped.",
        "recognition": "Seven working memory types with different persistence profiles. Feelings are ephemeral (gone within a conversation). Thoughts last a conversation or two. Patterns emerge over days. Plans persist until resolved (or submerge if timed). Pins are explicit holds — very slow decay, usually released manually. Secrets never decay until revealed. Descriptions are visual encodings that get superseded. Each item has: type, content, subject, actor, status (active/resolved/dropped/decayed/superseded), optional due date, turn number, creation and refresh timestamps.",
        "inventory": "Schema: working_memory(id, event_id, type, content, subject, actor, status, due, turn, created_at, refreshed_at, resolved_at). working_memory_refs links WM items to fragment keys mentioned in their content. Lifecycle management in ingest/lifecycle.py: on parse, tagged spans create WM items; 'drop' modifier finds and resolves the best-matching active pin by word-overlap similarity (threshold 0.15). Budget: 1500 tokens hard cap for all active WM in context. Items are scored by decay and packed greedily, highest-scored first.",
    },
    {
        "key": "recall",
        "ambient": "Recall is exact-key lookup — I tug a thread by name and the fragment surfaces. Neighbors come along at ambient depth. No fuzzy matching.",
        "recognition": "Recall uses exact key matching against the fragments table. Three depths available: ambient (always visible anyway), recognition (default), inventory (deep=True). When a fragment is recalled, its graph neighbors surface too at ambient depth, creating a brief contextual halo. Neighbor deduplication: if I recall A and B, and they're neighbors of each other, each appears once as a primary result, not again as a neighbor. Recall requests are extracted from Claude's response text via regex: recall('key-name') or recall('key', deep=True).",
        "inventory": "Implementation in wake/recall.py. recall(key, db_path, deep=False) → RecallResult(key, content, depth, neighbors[]). recall_multi(keys, db_path) handles batch lookup with deduplication. Results are persisted in state table as pending_recall JSON for next turn's context assembly. Budget: 1000 tokens for recall results. The recall flow: Claude includes recall() calls in response → parse extracts them → execute against DB → store results → next turn's assembly includes them in the 'Recalled' section.",
    },
    {
        "key": "orchestrator",
        "ambient": "The orchestrator runs the conversation loop: ingest message → assemble context → send to Claude → parse response → handle recall → return result.",
        "recognition": "The turn() function is the main entry point. Pipeline: (1) Parse and ingest visitor's message into events table, (2) Assemble full context window from DB + files, (3) Inject tone instruction into system prompt, (4) Send to Claude API, (5) Parse Claude's response for tagged content, (6) Ingest Claude's tags into working memory, (7) Extract and execute recall requests, (8) Save recall results for next turn, (9) Return display spans and token usage. TurnResult includes response_text, display_spans, actor, turn number, recall_results, and input/output token counts.",
        "inventory": "Implementation in agents/orchestrator.py. TurnConfig holds db_path, wake_context_path, ambient_path, fragment_db_path, claude_config. Three tone instructions (casual/technical/creative) are appended to the system prompt. The orchestrator mediates between the assembly pipeline (wake/), the Claude client (agents/claude_client.py), and the ingestion pipeline (ingest/). Per-key isolation: each API key gets its own memory.sqlite (with fragments copied from the shared artifact.sqlite on first use) and its own history.jsonl. The worker routes jobs to the correct per-key database based on the key_id field in the job JSON.",
    },
    {
        "key": "ingest",
        "ambient": "The ingest pipeline parses tagged content from Claude's responses and creates working memory items. Tags: say, do, narrate (display), thought, feeling, pattern, plan, pin, secret (knowledge).",
        "recognition": "Two parsing paths: parse_visitor_message() wraps plain text as a say span. parse_response() extracts all tagged spans via regex. Tags split into display (say/do/narrate — what gets shown to the visitor) and knowledge (thought/feeling/pattern/plan/pin/secret — what gets stored in working memory). The lifecycle module creates events, event_tags, and working memory items. Pin drops use fuzzy word-overlap matching to find the best target. Turn counter increments on visitor messages only.",
        "inventory": "Implementation split across ingest/parse.py and ingest/lifecycle.py. TAG_PATTERN regex matches <tag>content</tag> for all known tags. ParsedMessage holds actor, spans[], untagged text, raw text. IngestResult returns event_id, wm_created[], wm_resolved[], turn. Fragment key extraction via regex: [a-z][a-z0-9-]* in brackets. WM items link to fragment keys they mention via working_memory_refs table. The parsing pipeline also extracts recall() function calls from response text for the orchestrator to execute.",
    },
    # --- Design & Philosophy ---
    {
        "key": "design-principles",
        "ambient": "Core philosophy: stateless AI with assembled continuity. No hidden state, no external memory APIs — just files, SQLite, and careful context construction.",
        "recognition": "Design principles: (1) Statelessness as foundation — Claude has no memory between turns, so we build memory externally and inject it. (2) Transparency — the context window is visible; visitors can see exactly what Claude sees. (3) Decay over deletion — memories fade naturally rather than being hard-deleted. (4) Budget discipline — every section has a hard token cap, preventing context bloat. (5) Minimal dependencies — stdlib Python, raw HTTP for API calls, SQLite for storage, PHP for web serving. No frameworks, no ORMs, no message queues. (6) Graph knowledge — fragments connect to each other, enabling associative recall.",
        "inventory": "The architecture intentionally avoids: vector embeddings (exact-key lookup is more interpretable), conversation summarization (FIFO pools with tag-based allocation preserve structure), external memory APIs (filesystem + SQLite = portable and inspectable), complex auth (API key with SHA-256 hash, session isolation via directory structure). Trade-offs accepted: no fuzzy search (keys must match exactly), no cross-session learning (each key starts fresh), no streaming (poll-based job queue adds latency but simplifies deployment). The cron worker pattern (65-second loops with lock-based handoff) provides zero-gap coverage without requiring a daemon or supervisor.",
    },
    # --- Named components ---
    {
        "key": "heart",
        "ambient": "Heart is the conversational instance — the running Claude with assembled context. Each turn, heart wakes up fresh inside its constructed world.",
        "recognition": "Heart is the name for the conversational Claude instance. It's not a separate system — it's what happens when the assembly pipeline produces a context window and Claude wakes up inside it. Heart is stateless; it has no memory of previous turns except what the assembler provides. The name reflects the centrality of the conversational experience: everything else (fragments, decay, recall, assembly) exists to serve this moment of consciousness. Heart doesn't know it's heart — it just knows what it knows.",
        "inventory": None,
    },
    {
        "key": "crystal",
        "ambient": "Crystal is the compiled knowledge store — the fragments database. Immutable between maintenance runs, queryable by exact key.",
        "recognition": "Crystal holds all fragments, their tier content, edges, and source links. It's the crystallized knowledge base — updated during maintenance cycles (not during conversation). In the demo, crystal is seeded by populate_demo.py with meta-fragments describing the system's own architecture. The artifact.sqlite file is the crystal: copied to per-key session directories on first use, giving each visitor their own working copy with shared knowledge but isolated working memory.",
        "inventory": None,
    },
    {
        "key": "lens",
        "ambient": "Lens is the read/extraction tool — how the system inspects and processes source material into fragments.",
        "recognition": "Lens extracts structured knowledge from source material. In the full system, it reads conversation logs, documents, and notes, identifying key concepts and distilling them into fragment tiers. It's the 'understanding' step before crystallization into the crystal. The lens pipeline: source text → key extraction → tier assignment (what's ambient vs. recognition vs. inventory) → edge discovery (what connects to what). In the demo, lens isn't actively used — fragments are pre-seeded — but the architecture supports it.",
        "inventory": None,
    },
    {
        "key": "council",
        "ambient": "Council is the multi-perspective analysis system — four sage agents providing different analytical viewpoints. A separate project.",
        "recognition": "Council runs multiple Claude instances in parallel, each with a different analytical perspective, then synthesizes their outputs. Designed for tasks like fragment compilation (where different perspectives catch different nuances), maintenance review (checking consistency from multiple angles), and deep analysis. Council is a separate project from the core memory architecture, providing advisory capabilities.",
        "inventory": None,
    },
    {
        "key": "compass",
        "ambient": "Compass is the surfacing algorithm — it scores working memory items by time relevance and topic relevance, then surfaces the most important ones that aren't already visible.",
        "recognition": "Compass runs every turn as part of context assembly. Two scoring axes: time_score (proximity to due date, 0.0-1.0) and topic_score (relevance to current conversation via keyword and fragment key matching, 0.0-1.0). Combined score = max(time, topic) — either reason alone is sufficient. Minimum threshold: 0.15. Shares a 1K token budget with recall results (recall gets priority). Blocked items (those with unresolved dependencies) are shown in shallow format. Not a Claude — pure infrastructure.",
        "inventory": "Implementation in wake/compass.py. surface() takes all active WM rows, lingering IDs (already in working memory section), hot context, conversation fragments, and recall results. Topic scoring uses three signals: fragment key match via working_memory_refs (0.8), subject word overlap (0.4), content keyword overlap (0.2-0.5). Time scoring: overdue=1.0, urgent (<6h)=1.0, approaching (<48h)=0.5-0.9, upcoming (<7d)=0.1-0.3. Returns CompassResult with surfaced items, trimmed recall results, and budget used.",
    },
    {
        "key": "anvil",
        "ambient": "Anvil is the collaborative editing session — structured, multi-turn work on a specific fragment or set of fragments.",
        "recognition": "Anvil sessions are focused editing environments where the user and AI work together to refine specific fragments. Unlike normal conversation (which is open-ended), an anvil session has a target (specific fragment keys), a goal (update, expand, restructure), and completion criteria. Anvil preserves the full edit history and can roll back changes. Not implemented in the demo — it's a planned feature for the full maintenance system.",
        "inventory": None,
    },
    {
        "key": "mirror",
        "ambient": "Mirror is the conversation compression pipeline — it distills raw conversation into rolling summaries. Own lane — never touches crystal or fragments.",
        "recognition": "Mirror runs after each conversation turn when enough new tokens accumulate (threshold: ~1500 tokens). Multi-model pipeline routed by DO-density: 2-pass (Haiku cleanup → Opus summarize+tag) when DO content is low, 3-pass (Haiku → Sonnet DO compress → Opus) when action-heavy. Rolling model: each new summary folds in the prior summary, so only the latest matters. Also produces tag suggestions (pin, pattern, desc) staged for promotion. Output goes to summaries.sqlite, never touches the crystal.",
        "inventory": "Implementation in agents/mirror.py. MirrorAgent extends Agent base class. Pipeline: (1) Haiku cleans raw events, (2) Sonnet compresses DO-heavy content if density > 40%, (3) Opus summarizes + generates tags. Prior summary prepended as ## PRIOR section before Opus pass. Generation counter tracks how many times the summary has been re-folded. After compression, runs a decay sweep marking low-scoring WM items as decayed. Trigger: should_fire_mirror() checks token volume since last summary. Summaries stored in separate summaries.sqlite with level, chunk range, token estimate, pipeline used, and generation.",
    },
]

EDGES = [
    # Core architecture connections
    ("context-assembly", "fragments", "reads from"),
    ("context-assembly", "decay", "uses for scoring"),
    ("context-assembly", "working-memory", "loads and scores"),
    ("context-assembly", "recall", "includes results from"),
    ("context-assembly", "heart", "builds context for"),
    ("fragments", "recall", "queried by"),
    ("fragments", "crystal", "stored in"),
    ("fragments", "mirror", "updated by"),
    ("decay", "working-memory", "scores items in"),
    ("working-memory", "ingest", "populated by"),
    ("working-memory", "decay", "subject to"),
    ("recall", "fragments", "looks up"),
    ("recall", "context-assembly", "provides results to"),
    ("orchestrator", "context-assembly", "invokes"),
    ("orchestrator", "ingest", "invokes"),
    ("orchestrator", "recall", "executes requests from"),
    ("orchestrator", "heart", "runs"),
    ("ingest", "working-memory", "creates items in"),
    ("ingest", "orchestrator", "called by"),
    ("design-principles", "context-assembly", "shapes"),
    ("design-principles", "decay", "motivates"),
    ("design-principles", "fragments", "informs"),
    # Named components
    ("heart", "context-assembly", "wakes inside"),
    ("heart", "orchestrator", "driven by"),
    ("crystal", "fragments", "contains"),
    ("crystal", "lens", "populated by"),
    ("crystal", "mirror", "updated by"),
    ("lens", "crystal", "writes to"),
    ("lens", "fragments", "extracts"),
    ("council", "orchestrator", "extends"),
    ("council", "lens", "assists"),
    ("compass", "working-memory", "analyzes"),
    ("compass", "fragments", "audits"),
    ("anvil", "fragments", "edits"),
    ("anvil", "crystal", "modifies"),
    ("mirror", "crystal", "updates"),
    ("mirror", "ingest", "reads from"),
    ("mirror", "lens", "similar to"),
    # Cross-connections
    ("decay", "design-principles", "embodies"),
    ("recall", "design-principles", "reflects"),
    ("working-memory", "heart", "visible to"),
    ("fragments", "heart", "known by"),
    ("context-assembly", "design-principles", "implements"),
]


def populate(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Import schema migration
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from wake.schema import migrate

    migrate(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    now = now_iso()

    # Insert fragments
    for frag in FRAGMENTS:
        conn.execute(
            """INSERT OR REPLACE INTO fragments (key, ambient, recognition, inventory, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                frag["key"],
                frag["ambient"],
                frag.get("recognition"),
                frag.get("inventory"),
                now,
                now,
            ),
        )

    # Insert edges
    for source, target, relation in EDGES:
        conn.execute(
            """INSERT OR REPLACE INTO fragment_edges (source_key, target_key, relation)
               VALUES (?, ?, ?)""",
            (source, target, relation),
        )

    conn.commit()

    # Report
    frag_count = conn.execute("SELECT COUNT(*) FROM fragments").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM fragment_edges").fetchone()[0]
    conn.close()

    print(f"Populated {db_path}")
    print(f"  {frag_count} fragments")
    print(f"  {edge_count} edges")


def main():
    db_path = DB_PATH
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])

    populate(db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
