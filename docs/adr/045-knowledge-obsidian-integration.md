# ADR 045 — Knowledge vault health and optional Obsidian launch integration

## Status
Accepted

## Context
SirisOS Knowledge already treats a mounted Markdown/Obsidian vault as the source of truth. A browser-hosted Obsidian UI such as Selkies is useful for full editing, but it must not become a dependency of Knowledge browsing, search, backlinks or graph features.

## Decision
- Register the Knowledge vault with `SirisIntegrationManager` through a lightweight `KnowledgeConnector`.
- Connector health is determined from the authenticated Knowledge overview endpoint and therefore represents vault availability, not Selkies process availability.
- Keep the vault read-only from SirisOS.
- Add an optional `SIRISOS_OBSIDIAN_URL` production build setting.
- When configured, the Knowledge module exposes a browser launch action to that URL.
- When unset, the launcher is hidden and all Knowledge functionality remains unchanged.
- Do not proxy, embed, authenticate to, or control the Selkies/Obsidian process in this slice.

## Consequences
Knowledge integration health remains meaningful even if a separate Obsidian UI is stopped. Users can launch their preferred self-hosted Obsidian front end without coupling SirisOS APIs to that deployment. A future connector may monitor Selkies separately if process-level health becomes useful.
