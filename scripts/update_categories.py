"""Bake TempleOSRS's collection log category map into src/transform.py.

TempleOSRS rate limits by IP and TRMNL's servers are shared, so the plugin
should not fetch categories.php (which only changes when Jagex adds items) on
every refresh. This script fetches it once and rewrites the generated
CATEGORY_ITEMS block in src/transform.py with each top-level tab's unique
item IDs. Re-run it (make update-categories) after new content is released.
"""

import json
import pathlib
import re
import sys
import urllib.request
from typing import Dict, List

ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSFORM = ROOT / "src" / "transform.py"
URL = "https://templeosrs.com/api/collection-log/categories.php"
TABS = ["bosses", "raids", "clues", "minigames", "other"]

BEGIN = "# BEGIN GENERATED CATEGORY_ITEMS (make update-categories)"
END = "# END GENERATED CATEGORY_ITEMS"


def fetch() -> Dict[str, Dict[str, List[int]]]:
    req = urllib.request.Request(URL, headers={"User-Agent": "TRMNL-OSRS-Collection-Log/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data: Dict[str, Dict[str, List[int]]] = json.loads(resp.read())
    return data


def main() -> int:
    raw = fetch()
    tabs: Dict[str, List[int]] = {}
    for tab in TABS:
        subcats = raw.get(tab)
        if not isinstance(subcats, dict):
            print(f"categories.php has no '{tab}' tab", file=sys.stderr)
            return 1
        tabs[tab] = sorted({item for items in subcats.values() for item in items if isinstance(item, int)})

    lines = [BEGIN, "CATEGORY_ITEMS: Dict[str, List[int]] = {"]
    for tab, ids in tabs.items():
        lines.append(f'    "{tab}": {json.dumps(ids, separators=(",", ":"))},')
    lines += ["}", END]
    block = "\n".join(lines)

    source = TRANSFORM.read_text()
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    if not pattern.search(source):
        print(f"no generated block found in {TRANSFORM}", file=sys.stderr)
        return 1
    TRANSFORM.write_text(pattern.sub(lambda _: block, source))
    summary = ", ".join(f"{tab} {len(ids)}" for tab, ids in tabs.items())
    print(f"updated CATEGORY_ITEMS in {TRANSFORM.relative_to(ROOT)}: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
