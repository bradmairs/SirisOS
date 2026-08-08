# ADR 029 — Separate SirisAI orchestration, Hermes Agent runtime, and Ollama inference

## Status

Accepted for roadmap planning.

## Context

SirisOS will use AI for two materially different workloads:

1. Local inference and domain assistance such as SirisHydro, SirisPM, briefings, semantic search, and deterministic-output rewriting.
2. Tool-using server administration where an agent may inspect files, run commands, edit configuration, or perform operational actions.

Hermes Agent provides an agent/runtime layer with tool use, terminal/file capabilities, memory, skills and scheduling. Ollama provides local model serving and can also act as a model backend for Hermes.

## Decision

SirisOS will treat these as separate layers:

- **SirisAI** is the SirisOS orchestration, policy, identity, approval, audit, context and UX layer.
- **Hermes Agent** is an optional server-side agent runtime for tool-using operational tasks.
- **Ollama** is the local inference layer for SirisHydro, SirisPM, briefings, semantic search and other SirisOS AI features, and may optionally back Hermes models.

SirisOS must not expose unrestricted Hermes execution directly to the browser. High-impact actions must flow through SirisOS policy/approval and audit controls. Hermes approval-bypass modes must not be enabled by SirisOS.

## Initial roadmap

- Add an optional Hermes connector/runtime adapter.
- Keep Hermes credentials/endpoints server-side.
- Build an allow-listed SirisAI action broker for server operations.
- Require explicit confirmation for destructive/high-impact actions.
- Record requests, approvals, commands/actions and results in an audit trail.
- Feed Digital Twin, Incident Engine and Operations Center context into Hermes tasks.
- Keep Ollama as an independent reusable inference provider.
- Allow Hermes to use Ollama as one backend without coupling all SirisAI features to Hermes.

## Consequences

This separation lets SirisOS use lightweight local models for domain assistants while reserving agentic execution for explicit operational tasks. It also creates a clear security boundary around server control and avoids making Hermes Agent a single mandatory dependency for all AI capabilities.
