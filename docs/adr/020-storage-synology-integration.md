# ADR 020 — Storage and Synology NAS integration

## Status
Accepted

## Context
SirisOS needs storage awareness, and the deployed NAS platform is Synology DSM. A generic Proxmox integration is not useful for this installation and has been removed from the roadmap.

## Decision
SirisOS uses two complementary storage sources:

1. The existing node-exporter provides vendor-neutral host filesystem capacity for the SirisOS server.
2. Synology DSM is integrated as an optional `SirisConnector` for NAS-specific health.

DSM credentials remain inside the backend container. The backend follows Synology's WebAPI discovery/login flow, creates a short-lived SirisOS session, retrieves DSM information and storage state, and logs out after each snapshot. Storage calls prefer the DSM storage API exposed by the running system and fall back to discovered Core Storage APIs when required.

Flutter consumes only the authenticated SirisOS `/api/v1/homelab/synology` endpoint. It never receives DSM credentials or a DSM session ID.

The Synology connector publishes Homelab state-change events and uses Notification Policies for NAS unavailability and unhealthy disks/volumes. The host-storage connector separately raises deterministic capacity policies at 85% and 95% utilisation.

Backup API presence is detected during DSM API discovery. Hyper Backup task/history parsing is intentionally a follow-on slice because installed package APIs vary by DSM/package version and should be discovered rather than assumed.

## Consequences
- Existing installs remain deployable without Synology configuration.
- DSM version differences are handled through runtime API discovery where practical.
- NAS secrets remain server-side.
- Host storage and NAS storage remain distinct data sources rather than being conflated.
- Proxmox is not part of the active SirisOS roadmap.
- Hyper Backup monitoring can extend the same connector without changing Mission Control or notification architecture.
