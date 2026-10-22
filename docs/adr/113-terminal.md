# ADR 113: A terminal on the home network, behind 2FA

**Status:** accepted (SirisOS 2.8, October 2026)

## Context

Brad wants a shell on a machine at home from SirisOS while he's at work. A shell is the most powerful thing SirisOS can hand out, so a stolen or forgotten-open SirisOS session must not be enough to get one.

## Decision

- **SSH, not a shell in the container.** SirisOS opens an SSH connection (asyncssh) to hosts listed in `SIRISOS_TERMINAL_HOSTS` (`name=user@host[:port]`). The browser only names a host from that list; it can never give an address. SirisOS signs in with its own ed25519 key (`data/app/terminal/id_ed25519`, mode 600). Only the public half is shown, so Brad can choose which user it gets on each host.
- **Host keys are pinned** on the first connection and shown as SHA256 fingerprints. A changed key refuses the connection until `make terminal-forget-host NAME=…` is run on the server.
- **2FA is a TOTP code from an authenticator app (RFC 6238), on every terminal.**
  - Setting it up needs the SirisOS password as well as a session, and a first code to confirm it.
  - Turning it off needs the password and a current code. A lost phone is handled on the server with `make terminal-reset-2fa`.
  - The secret is encrypted with a key derived from `SIRISOS_JWT_SECRET`, so a copy of the data folder alone can't make codes.
  - Each code works once: the last used step is stored.
  - Five wrong codes from one client, or ten from anywhere, lock unlocking for 15 minutes. This is separate from the sign-in limit.
- **Unlocking issues a ticket.** A good code returns a random ticket that is good once, for one host, for 30 seconds. The WebSocket (`/api/v1/terminal/ws?ticket=`) also has to come from SirisOS's own origin.
- **Sessions close by themselves** after `SIRISOS_TERMINAL_IDLE_MINUTES` with no typing (15 by default) or `SIRISOS_TERMINAL_MAX_MINUTES` in all (120). At most two are open at once, and a new one needs a new code.
- **Every unlock, refusal and session is logged** in `terminal-audit.jsonl` and shown on the Terminal page. Keystrokes are never logged. Each session that opens sends a push notification to every device that has notifications on.

## Not done

- Passkeys as the second factor. TOTP was asked for, and it works the same on a work PC as on the phone.
- Exposing SirisOS to the internet. The terminal is meant for SirisOS reached over Tailscale or a VPN, and the docs and settings check say so.
