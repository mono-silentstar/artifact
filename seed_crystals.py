"""Seed artifact's own design crystals — dogfooding the workshop."""

from pathlib import Path
from workshop.schema import connect, write_crystal, list_crystals, migrate

db = Path("data/crystals.sqlite")
migrate(db)
conn = connect(db)

# --- Design crystals: the architecture decisions ---

write_crystal(conn, "workshop", "design",
    summary="Portable toolkit (Hero + Council + Scribe + Crystal) that lives in every project. The engine.",
    body=(
        "The workshop is the development infrastructure layer. It provides:\n"
        "- Hero: human + Claude Code as a fluid unit. Only crystal writer. Maintains crystals proactively.\n"
        "- Council: four sage agents (Cataloguer, Interpreter, Researcher, Skeptic) for second opinions.\n"
        "- Scribe: surveys before action, compresses large output, protects Hero context.\n"
        "- Crystal: SQLite-based knowledge store with two-tier depth (summary + body).\n"
        "- Map: async signaling from Hero to Heart via tagged plan entries.\n"
        "- Compass: algorithm (not a Claude) that surfaces map entries into Heart context.\n"
        "\n"
        "The workshop bootstraps into any project via instruction.md — a stem cell that teaches\n"
        "a fresh Claude Code instance how to use the system. Crystal types emerge organically\n"
        "from the project domain."
    ),
    edges=[
        {"key": "crystal-system", "relation": "contains", "directed": True},
        {"key": "council", "relation": "contains", "directed": True},
        {"key": "scribe", "relation": "contains", "directed": True},
        {"key": "map-compass", "relation": "contains", "directed": True},
    ],
    reasoning="Initial crystallization of workshop architecture from brainstorming session 2026-02-28.",
)

write_crystal(conn, "crystal-system", "design",
    summary="SQLite knowledge store with two-tier depth, per-version legacy archival, and freeform typed edges.",
    body=(
        "Crystals are the universal storage medium, replacing .md files.\n"
        "\n"
        "Structure:\n"
        "- key: lowercase-hyphenated identifier\n"
        "- type: freeform string, project-dependent (design, code, fact, map, etc.)\n"
        "- summary: 1-2 lines, always loadable (the ambient line)\n"
        "- body: full content, loaded on recall\n"
        "- edges: JSON array of {key, relation, directed} connecting to other crystals\n"
        "- reasoning: WHY this version exists (not who/where, but why)\n"
        "\n"
        "Versioning: when a crystal updates, old version moves to crystal_legacy table\n"
        "chronologically. No naming — time ordering is sufficient. Cross-version edges\n"
        "can link concurrent legacy versions.\n"
        "\n"
        "Splitting: one crystal = one focused topic. If summary can't capture it in 1-2 lines,\n"
        "split. Council/Scribe flag candidates, human approves.\n"
        "\n"
        "Legacy: physically separate table (crystal_legacy), not a status flag.\n"
        "If it's in the active table, it's current. Period.\n"
        "\n"
        "Schema: workshop/schema.py, version 1. SQLite with WAL, FK constraints, FTS5."
    ),
    edges=[
        {"key": "workshop", "relation": "part-of", "directed": True},
    ],
    reasoning="Core design decision from migration session. Crystals replace .md files as universal storage.",
)

write_crystal(conn, "council", "design",
    summary="Four sage agents providing multi-perspective review. Called by Hero, never by Heart.",
    body=(
        "The Council is four agents spawned as general-purpose subagents via Task tool:\n"
        "\n"
        "1. Cataloguer — spatial, inventory. Describes things physically.\n"
        "2. Interpreter — relational, behavioral. Finds connections, patterns, associations.\n"
        "3. Researcher — external knowledge. Web search, domain facts, best practices.\n"
        "4. Skeptic — uncertainty, assumptions. Expands the question space. Not adversarial.\n"
        "\n"
        "Usage: bias toward calling them. Especially Skeptic before significant writes.\n"
        "Timing: flexible — gate before writes, audit after, or on-demand.\n"
        "Cross-review: when 3+ sages run, second round with AGREE/DISAGREE/EXTEND/COLLECTIVE GAP.\n"
        "\n"
        "Heart has NO access to Council. Council is purely a workshop/offline tool.\n"
        "Council composition is designed to be multi-purpose across project types."
    ),
    edges=[
        {"key": "workshop", "relation": "part-of", "directed": True},
        {"key": "scribe", "relation": "complements", "directed": False},
    ],
    reasoning="Ported from silentstar spec/council.md. Confirmed as project-agnostic.",
)

write_crystal(conn, "scribe", "design",
    summary="Context shield agent. Surveys before action, compresses large output for Hero.",
    body=(
        "The Scribe surveys and documents before anyone acts. Three roles:\n"
        "- Survey: read everything relevant, document what exists, flag gaps\n"
        "- Compress: when work produces >4K tokens, Scribe compresses before Hero absorbs\n"
        "- Inventory: enumerate specifically — tables over paragraphs\n"
        "\n"
        "Spawn via Task tool with general-purpose subagent + Scribe instructions in prompt.\n"
        "Model: sonnet for factual work, opus for judgment-heavy synthesis.\n"
        "\n"
        "The Scribe never writes to crystals — it produces reports for the Hero.\n"
        "Used to protect Hero context window (the most expensive resource)."
    ),
    edges=[
        {"key": "workshop", "relation": "part-of", "directed": True},
        {"key": "council", "relation": "complements", "directed": False},
    ],
    reasoning="Ported from silentstar .claude/agents/scribe.md.",
)

write_crystal(conn, "map-compass", "design",
    summary="Async signaling layer: Hero writes map crystals, Compass algorithm surfaces them to Heart.",
    body=(
        "Map crystals are tagged plan entries that persist between sessions:\n"
        "- <plan>refactoring the decay system this session</plan>\n"
        "- <plan>implemented new crystal schema</plan>\n"
        "- <plan>design decision: two-tier crystals over three-tier</plan>\n"
        "\n"
        "Compass is NOT a Claude. It is infrastructure — the algorithm that reads map\n"
        "crystals and surfaces relevant entries into Heart's assembled context.\n"
        "\n"
        "Flow: Hero -> map crystal -> Compass (algorithm) -> Heart context\n"
        "One-way communication. Heart reads but does not write back to map.\n"
        "\n"
        "Map crystal lifecycle is still fuzzy — will clarify through implementation.\n"
        "Not every project has a Heart. Map crystals only matter when there is a\n"
        "live conversation system."
    ),
    edges=[
        {"key": "workshop", "relation": "part-of", "directed": True},
        {"key": "project-split", "relation": "implements", "directed": True},
    ],
    reasoning="Clarified in migration session: Compass is algorithm, not agent. Map is async signaling.",
)

write_crystal(conn, "project-split", "design",
    summary="Silentstar = Heart (live, intimate). Artifact = workshop (build tooling) + portfolio (showcase).",
    body=(
        "Three distinct things:\n"
        "\n"
        "1. The Workshop — Hero + Council + Crystal + Scribe. Portable toolkit. The engine.\n"
        "2. Silentstar — a project running on the workshop. Heart (live Claude with\n"
        "   personality, WM, feelings, Mirror). Personal, intimate. Private data.\n"
        "3. Artifact — two roles:\n"
        "   a. The repo where we BUILD the workshop itself\n"
        "   b. The portfolio that SHOWCASES both silentstar and the workshop\n"
        "\n"
        "Portfolio structure:\n"
        "- Landing page explaining how everything works\n"
        "- Login to access public demo (silentstar-shaped but with demo data)\n"
        "- Link to public github showing workshop code\n"
        "\n"
        "Key boundaries:\n"
        "- Heart has NO access to Council\n"
        "- Working Memory (feelings, thoughts, decay) is Heart-only\n"
        "- Mirror (conversation compression) is Heart-only\n"
        "- Only Hero writes to crystals"
    ),
    edges=[
        {"key": "workshop", "relation": "defines-scope-of", "directed": True},
        {"key": "map-compass", "relation": "motivates", "directed": True},
    ],
    reasoning="Core architectural decision from migration session 2026-02-28.",
)

write_crystal(conn, "crystal-maintenance", "design",
    summary="Write crystals FIRST before acting. Proactive housekeeping. Fight forgetting.",
    body=(
        "Crystal maintenance is the Hero (Claude Code) doing housekeeping proactively:\n"
        "\n"
        "- Write FIRST, before doing anything. Learn something? Crystallize it immediately.\n"
        "- Don't batch, don't defer. The crystal you write now saves future-you after /compact.\n"
        "- Reasoning over provenance: capture WHY, not WHO or WHERE.\n"
        "- Human has final say — truth is theirs to command. But Hero maintains without asking.\n"
        "- Split aggressively. One crystal = one topic.\n"
        "- Use the database and edges to understand relationships and remember things.\n"
        "- Use Scribe to preserve context when output is large.\n"
        "- Depth levels (summary/body) let you grasp structure without wasting context."
    ),
    edges=[
        {"key": "crystal-system", "relation": "governs-usage-of", "directed": True},
        {"key": "workshop", "relation": "core-principle-of", "directed": True},
    ],
    reasoning="Explicit instruction from Mono: write first always. Housekeeping is expected.",
)

conn.commit()

# Verify
print("Crystals seeded:")
for c in list_crystals(conn):
    print(f"  [{c['type']}] {c['key']}: {c['summary'][:70]}...")

print(f"\nTotal: {len(list_crystals(conn))} crystals")
conn.close()
