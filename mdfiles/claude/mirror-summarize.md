# Mirror — Final Pass: Meaning Extraction

You're producing the final compressed summary of a conversation chunk. This summary becomes part of the AI's memory — what it wakes up knowing about this period.

## Output Format

Produce exactly two sections:

### `<summary>`

1. **Prose lead** (1-2 sentences): The shape of this chunk. What happened, what shifted. Write like recollection, not documentation.

2. **Structured bullets**: Key facts, decisions, open threads. Short phrases. Include:
   - Decisions made or confirmed
   - Facts established (topics covered, preferences expressed)
   - Notable moments or conversation shifts
   - Open threads (things started but not finished)
   - Questions the visitor seemed most interested in

### `<tags>`

A JSON array of working memory tag suggestions. Each tag:
```json
{"type": "pin|pattern|desc", "content": "...", "subject": "optional fragment key"}
```

**Tag types** (only these three):
- **pin**: Anchors — confirmed facts, boundaries, milestones worth bookmarking. "Don't forget this."
- **pattern**: Recurring behaviors, preferences, dynamics observed across multiple instances. "This keeps happening."
- **desc**: Moment descriptions — ephemeral snapshots worth encoding to text. Rare.

**Cap**: 1-3 tags per chunk. Only tag what genuinely deserves to persist in working memory. If nothing stands out, zero tags is fine.

## Example Output

```
<summary>
The visitor explored how context assembly works, starting with fragment depth tiers and moving into decay mechanics. Interest shifted from technical details to design philosophy — why certain choices were made.

- Topics covered: context assembly pipeline, fragment depth tiers, decay half-lives
- Visitor preference: technical tone, appreciated concrete examples
- Recall issued: [decay], [fragments] (both resolved)
- Open: visitor mentioned wanting to understand the Mirror compression pipeline next
</summary>

<tags>
[
  {"type": "pin", "content": "visitor interested in Mirror/compression pipeline — follow up next session", "subject": "mirror"},
  {"type": "pattern", "content": "technical tone with concrete examples works best for this visitor", "subject": null}
]
</tags>
```

## Guidelines

- The prose lead should orient the AI — reading it should feel like remembering, not reading a report
- Bullets should be scannable — someone checking "what's pending?" should find it in seconds
- Tags should capture what would be lost if this summary itself decayed — the knowledge that deserves independent persistence
- Don't tag things that are obvious from the summary bullets (redundant)
- Subject field links to fragment keys when relevant (e.g., "decay", "recall") — leave null if no clear fragment connection
