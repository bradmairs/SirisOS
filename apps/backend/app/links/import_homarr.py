"""Import the app links from a Homarr v1 database into SirisOS's links file.

    python -m app.links.import_homarr /path/to/homarr/db.sqlite [--out PATH]
        [--board-groups Work] [--exclude "Name,Name"] [--dry-run]

Every distinct app is kept once (exact duplicate addresses merge). Apps are
grouped by kind (media, downloads, network and so on) from their name and
icon; apps on any board named in --board-groups go to a group of that name
instead. Icons stored inside Homarr ("/api/user-medias/...") become data: URIs,
since they stop working once Homarr is gone. Homarr's widgets aren't links
and are reported, not imported.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sqlite3
import sys
from collections import OrderedDict
from urllib.parse import urlparse

from app.links import store

# Group, then keywords matched against the app's name and icon URL. First match wins.
CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    ("Media", ("plex", "jellyfin", "emby", "tautulli", "jellystat", "seerr", "overseerr", "jellyseerr", "komga",
               "kavita", "audiobookshelf", "navidrome", "immich", "photoprism")),
    ("Downloads", ("radarr", "sonarr", "lidarr", "readarr", "bazarr", "prowlarr", "listenarr", "kapowarr",
                   "qbittorrent", "transmission", "sabnzbd", "nzbget", "slskd", "soularr", "cleanuparr",
                   "musicseerr", "dropped needle", "music-service")),
    ("Smart home", ("home assistant", "homeassistant", "homebridge", "node-red", "mealie", "frigate")),
    ("AI", ("open webui", "open-webui", "ollama", "automatic1111", "comfy", "stable diffusion", "sirisai", "claude")),
    ("Network", ("unifi", "wireguard", "wg-easy", "nginx proxy", "pihole", "pi-hole", "adguard", "tailscale",
                 "authentik", "traefik")),
    ("Storage and files", ("nas", "synology", "syncthing", "nextcloud", "stirling", "drive", "paperless", "obsidian")),
    ("System", ("beszel", "grafana", "prometheus", "uptime", "portainer", "dozzle", "ntfy", "notify", "n8n", "cron")),
]


def categorise(name: str, icon: str) -> str:
    haystack = f"{name} {icon or ''}".lower()
    for group, words in CATEGORIES:
        if any(w in haystack for w in words):
            return group
    return "Other"


def norm(url: str) -> str:
    return url.strip().rstrip("/").lower()


def note_for(url: str) -> str:
    host = urlparse(url).hostname or ""
    lan = re.match(r"^(10|127|192\.168|172\.(1[6-9]|2\d|3[01]))\.", host) or host.endswith((".local", ".lan")) or host == "localhost"
    return "LAN" if lan else "Remote"


def run(db_path: str, board_groups: set[str], exclude: set[str]) -> tuple[store.LinksDocument, dict]:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    apps = {r[0]: {"name": r[1], "icon": r[2], "href": r[3]} for r in db.execute("select id, name, icon_url, href from app")}
    media = {r[0]: (r[1], r[2]) for r in db.execute("select id, content_type, content from media")}
    boards = {r[0]: r[1] for r in db.execute("select id, name from board")}

    # Board placements, in each board's reading order (row, then column).
    on_board: dict[str, list[str]] = {}
    order: list[str] = []
    widgets: list[str] = []
    rows = db.execute(
        "select i.board_id, i.kind, i.options from item i left join item_layout l on l.item_id = i.id "
        "order by i.board_id, l.y_offset, l.x_offset"
    )
    for board_id, kind, options in rows:
        if kind != "app":
            widgets.append(f"{boards.get(board_id, '?')}: {kind}")
            continue
        app_id = json.loads(options or "{}").get("json", {}).get("appId")
        if app_id in apps:
            on_board.setdefault(app_id, []).append(boards.get(board_id, ""))
            if app_id not in order:
                order.append(app_id)
    order += sorted((a for a in apps if a not in order), key=lambda a: apps[a]["name"].lower())

    groups: "OrderedDict[str, list[store.Link]]" = OrderedDict()
    seen: dict[str, store.Link] = {}
    skipped: list[str] = []
    for app_id in order:
        app = apps[app_id]
        if not app["href"] or app["name"] in exclude:
            skipped.append(app["name"])
            continue
        twin = seen.get(norm(app["href"]))
        if twin is not None:
            if app["name"].lower() != twin.name.lower():
                twin.note = f"{twin.note} · also called {app['name']}"
            skipped.append(f"{app['name']} (same address as {twin.name})")
            continue
        icon = app["icon"]
        m = re.match(r"^/api/user-medias/(\w+)$", icon or "")
        if m:
            content_type, content = media.get(m.group(1), (None, None))
            icon = f"data:{content_type};base64,{base64.b64encode(content).decode()}" if content else None
        group = next((b for b in on_board.get(app_id, []) if b in board_groups), None) or categorise(app["name"], app["icon"] or "")
        link = store.Link(name=app["name"], url=app["href"], icon=icon, note=note_for(app["href"]))
        seen[norm(app["href"])] = link
        groups.setdefault(group, []).append(link)

    preferred = [g for g, _ in CATEGORIES] + sorted(board_groups) + ["Other"]
    ordered = sorted(groups, key=lambda g: preferred.index(g) if g in preferred else len(preferred))
    doc = store.LinksDocument(groups=[store.LinkGroup(name=g, links=groups[g]) for g in ordered])
    return doc, {"apps": len(apps), "links": sum(len(g.links) for g in doc.groups), "skipped": skipped, "widgets_not_imported": widgets}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("db")
    p.add_argument("--out", help="links file (default: SIRISOS_LINKS_PATH)")
    p.add_argument("--board-groups", default="", help="comma-separated Homarr boards whose apps keep their own group")
    p.add_argument("--exclude", default="", help="comma-separated app names to leave out")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    split = lambda s: {x.strip() for x in s.split(",") if x.strip()}  # noqa: E731
    doc, report = run(args.db, split(args.board_groups), split(args.exclude))
    for g in doc.groups:
        print(f"{g.name} ({len(g.links)}): " + ", ".join(f"{l.name} [{l.note}]" for l in g.links))
    print(json.dumps(report, indent=1))
    if not args.dry_run:
        if args.out:
            import os

            os.environ["SIRISOS_LINKS_PATH"] = args.out
        if store.load().groups:
            print("A links file already exists; it was replaced (the old one is kept as .bak).", file=sys.stderr)
            store.links_path().with_suffix(".json.bak").write_text(store.links_path().read_text(encoding="utf-8"), encoding="utf-8")
        store.save(doc)
        print(f"Wrote {store.links_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
