# Log Discussion Workflow

Use this workflow when the user asks to preserve an important discussion,
decision, risk, analysis idea, or implementation rationale for later reference.

## Inputs Required

Ask the user what to log if it is not already clear. The user should provide one
or more topics, for example:

- A decision we made
- A risk or danger we discussed
- A definition or calculation rule
- A future integration idea
- A current implementation caveat

## Output Location

Create or update markdown files in:

```text
discussion_logs/
```

## Filename Format

Use this exact filename format:

```text
YYMMDD - {file_name}.md
```

Rules:

- `YYMMDD` is the local current date.
- `{file_name}` should be short, lowercase, descriptive, and use hyphens.
- Keep the `.md` extension.
- Example: `260607 - new-low-analysis-risks.md`

## File Metadata

Every log file must begin with this metadata block:

```yaml
---
createdate: YYYY-MM-DD
changedate: YYYY-MM-DD
topic: "Short human-readable topic"
source: "discussion"
status: "active"
---
```

When updating an existing log, preserve `createdate` and update `changedate`.

## Content Structure

Use these sections unless the user asks for a different shape:

```md
# Title

## Context

## Key Points

## Decisions / Current Understanding

## Risks / Caveats

## Future Follow-Ups
```

Keep the writing practical and specific. This is a memory aid for future work,
not a transcript. Prefer bullets over long paragraphs.

## Workflow Steps

1. Identify the topic the user wants to preserve.
2. Choose whether to create a new log or update an existing related log.
3. Create/update the file in `discussion_logs/`.
4. Use the metadata block and content structure above.
5. Summarize the file path and what was logged.

## Important Rules

- Do not invent decisions that were not actually discussed.
- Separate confirmed decisions from open questions.
- If a point is a trading/investing caveat, label it clearly as a caveat.
- If a point may become stale, say what would need to be refreshed later.
