# ADR 004: Deterministic Briefing Engine

## Status

Accepted.

## Context

SirisOS needs a coherent daily briefing that can combine observations from Running, Gym, Health, Homelab, Engineering, Knowledge, Tasks, and future modules. Generating the briefing directly with an LLM would make prioritisation difficult to test and could introduce unsupported claims.

## Decision

SirisOS will use a deterministic briefing engine beneath any future AI wording layer.

Each module contributes typed `BriefingObservation` values with:

- Stable observation ID
- Module source
- Human-readable message
- Priority
- Tone
- Optional expiry

The engine deduplicates observations by stable ID, removes expired items, sorts by priority, and assembles a bounded briefing. Existing backend briefing strings remain a fallback while contributors are expanded.

The Health contributor is registered now but emits no observation until dedicated Health data is added to the shared briefing input. SirisOS must not fabricate a health observation from unrelated dashboard data.

## Consequences

- Briefing behaviour is predictable and testable.
- Modules remain responsible for domain observations.
- Mission Control and future delivery channels can share the same ranked output.
- Ollama may later rewrite wording, but it must not change the underlying facts or priority ordering.
- Adding a new module requires a contributor rather than edits to one central briefing switch.
