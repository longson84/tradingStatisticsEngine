# CLAUDE.md

## Communication

When I describe something I already did or explain context, do NOT jump to writing code or fixing things. Ask first if I want you to take action.

When I ask to see output or results, focus on showing me the output first. Do not autonomously debug or fix failures unless I ask you to.

## Project Context

This project uses Python (primary), TypeScript, and Streamlit. The trading engine has a clear distinction between signals and strategies — do not conflate them.

## Code Style

Reuse existing utility functions before creating new ones. Always check for existing helpers (formatting, shared components) before duplicating logic.

## Frameworks & Libraries

When modifying Streamlit apps: be aware of session_state key collisions, cache hashing quirks (exact type matching, not isinstance), and always test UI changes mentally before applying.
