"""Terminal housekeeping from the server itself (being on the server is the proof):

    python -m app.terminal.admin reset-2fa           turn 2FA off (lost phone); set it up again in SirisOS
    python -m app.terminal.admin forget-host NAME    forget a host's pinned SSH key (after a reinstall)
    python -m app.terminal.admin public-key          SirisOS's SSH public key, for authorized_keys
"""

from __future__ import annotations

import sys

from app.terminal import service, store


def main(argv: list[str]) -> int:
    if argv[:1] == ["reset-2fa"]:
        service.turn_off()
        store.audit("2fa-reset-on-server")
        print("2FA for the terminal is off. Open the Terminal page in SirisOS to set it up again.")
        return 0
    if argv[:1] == ["forget-host"] and len(argv) == 2:
        found = service.forget(argv[1])
        store.audit("host-key-forgotten", host=argv[1])
        print(f"Forgot {argv[1]}'s SSH key; the next connection pins the new one." if found else f"No pinned key for {argv[1]}.")
        return 0
    if argv[:1] == ["public-key"]:
        print(service.public_key())
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
