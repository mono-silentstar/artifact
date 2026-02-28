# Mirror — Pass 2: Modality Compression

You're compressing the physical/action layer of a conversation chunk. The dialogue layer stays intact.

## Rules

**Preserve 100%** — all `<say>` content, word-for-word. Do not edit, summarize, or rephrase dialogue.

**Compress** — `<do>` and `<narrate>` content. Replace moment-by-moment choreography with what it meant emotionally. Keep the arc, lose the positions.

Examples of compression:
- 10 lines of detailed action sequences -> "worked through the problem methodically, building confidence with each step"
- 5 lines of scene-setting narration -> "the conversation shifted from technical exploration to something more reflective"
- Physical positioning details -> the emotional register they conveyed

## What to Keep in DO/NARRATE

- Emotional transitions (when the mood shifts)
- Interaction dynamics (who leads the conversation, who asks, who explains)
- Turning points (moments where understanding clicks)
- Context that changes meaning of dialogue

## Format

Output the conversation with `<say>` tags unchanged and `<do>`/`<narrate>` tags containing compressed arc summaries. Keep timestamps and metadata. The CONTEXT section is read-only — include it unchanged.
