"""Inline the plugin's static icons into src/shared.liquid.

Reads assets/icons/manifest.json (icon name -> OSRS item ID), downloads any
missing PNG from RuneLite's icon CDN into assets/icons/, then rewrites the
generated block in src/shared.liquid with a JSON map of name -> data URI.
Markup looks icons up with `osrs_icons[name]`.
"""

import base64
import json
import pathlib
import re
import sys
import urllib.request
from typing import Dict

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "icons"
MANIFEST = ICON_DIR / "manifest.json"
SHARED = ROOT / "src" / "shared.liquid"
ICON_URL = "https://static.runelite.net/cache/item/icon/{item_id}.png"

BEGIN = "{%- comment -%} BEGIN GENERATED ICONS (make inline-icons) {%- endcomment -%}"
END = "{%- comment -%} END GENERATED ICONS {%- endcomment -%}"


def download(name: str, item_id: int) -> pathlib.Path:
    path = ICON_DIR / f"{name}.png"
    if not path.exists():
        req = urllib.request.Request(ICON_URL.format(item_id=item_id), headers={"User-Agent": "trmnl-osrs-clog"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            path.write_bytes(resp.read())
        print(f"downloaded {path.relative_to(ROOT)}")
    return path


def main() -> int:
    manifest: Dict[str, int] = json.loads(MANIFEST.read_text())
    icons = {
        name: "data:image/png;base64," + base64.b64encode(download(name, item_id).read_bytes()).decode()
        for name, item_id in manifest.items()
    }
    block = f"{BEGIN}\n{{%- assign osrs_icons = '{json.dumps(icons, separators=(',', ':'))}' | parse_json -%}}\n{END}"

    shared = SHARED.read_text()
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    shared = pattern.sub(lambda _: block, shared) if pattern.search(shared) else block + "\n" + shared
    SHARED.write_text(shared)
    print(f"inlined {len(icons)} icons into {SHARED.relative_to(ROOT)} ({SHARED.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
