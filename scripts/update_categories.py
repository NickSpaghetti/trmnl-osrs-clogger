"""Bake TempleOSRS's collection log category map into src/transform.py.

TempleOSRS rate limits by IP and TRMNL's servers are shared, so the plugin
should not fetch categories.php (which only changes when Jagex adds items) on
every refresh. This script fetches it once and rewrites the generated
CATEGORY_ITEMS block in src/transform.py with each top-level tab's unique
item IDs. Re-run it (make update-categories) after new content is released.
"""

import argparse
import ast
import json
import pathlib
import re
import sys
import urllib.request
from typing import Any, Dict, List, Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSFORM = ROOT / "src" / "transform.py"
URL = "https://templeosrs.com/api/collection-log/categories.php"
ITEMS_URL = "https://templeosrs.com/api/collection-log/items.php"
USER_AGENT = "TRMNL-OSRS-Collection-Log/1.0"
TABS = ["bosses", "raids", "clues", "minigames", "other"]
TAB_LABELS: Dict[str, str] = {
    "bosses": "Bosses",
    "raids": "Raids",
    "clues": "Clues",
    "minigames": "Minigames",
    "other": "Other",
}

BEGIN = "# BEGIN GENERATED CATEGORY_ITEMS (make update-categories)"
END = "# END GENERATED CATEGORY_ITEMS"


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch() -> Dict[str, Dict[str, List[int]]]:
    data: Dict[str, Dict[str, List[int]]] = fetch_json(URL)
    return data


def fetch_item_names() -> Dict[int, str]:
    try:
        data = fetch_json(ITEMS_URL)
    except Exception as exc:
        print(f"warning: could not fetch item names from {ITEMS_URL}: {exc}", file=sys.stderr)
        return {}
    raw_items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(raw_items, dict):
        return {}
    names: Dict[int, str] = {}
    for key, val in raw_items.items():
        if isinstance(val, str):
            try:
                names[int(key)] = val
            except (TypeError, ValueError):
                continue
    return names


def parse_existing(block: str) -> Dict[str, List[int]]:
    start = block.find("{")
    end = block.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    parsed = ast.literal_eval(block[start : end + 1])
    if not isinstance(parsed, dict):
        return {}
    return {
        tab: [i for i in ids if isinstance(i, int)]
        for tab, ids in parsed.items()
        if isinstance(tab, str) and isinstance(ids, list)
    }


def format_item_line(
    item_id: int,
    item_names: Dict[int, str],
    subcats: Optional[List[str]] = None,
) -> str:
    name = item_names.get(item_id)
    details = [f"`{item_id}`"]
    if subcats:
        details.extend(f"`{sc}`" for sc in subcats)
    if name:
        return f"  - {name} ({', '.join(details)})"
    if subcats:
        return f"  - Item `{item_id}` ({', '.join(f'`{sc}`' for sc in subcats)})"
    return f"  - Item `{item_id}`"


def format_pr_body(
    added: Dict[str, List[int]],
    removed: Dict[str, List[int]],
    item_names: Dict[int, str],
    item_subcats: Dict[str, Dict[int, List[str]]],
) -> str:
    lines = [
        f"Re-baked `CATEGORY_ITEMS` in `src/transform.py` from TempleOSRS ({URL}).",
        "",
    ]

    added_total = sum(len(ids) for ids in added.values())
    if added_total:
        lines.append(f"### Added ({added_total})")
        for tab in TABS:
            ids = added.get(tab)
            if not ids:
                continue
            lines.append(f"- **{TAB_LABELS[tab]}**")
            tab_subcats = item_subcats.get(tab, {})
            for item_id in ids:
                lines.append(format_item_line(item_id, item_names, tab_subcats.get(item_id)))
        lines.append("")

    removed_total = sum(len(ids) for ids in removed.values())
    if removed_total:
        lines.append(f"### Removed ({removed_total})")
        for tab in TABS:
            ids = removed.get(tab)
            if not ids:
                continue
            lines.append(f"- **{TAB_LABELS[tab]}**")
            for item_id in ids:
                lines.append(format_item_line(item_id, item_names))
        lines.append("")

    lines.append("Lint and plugin tests passed. Run the Release workflow after merging to publish to TRMNL.")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bake TempleOSRS collection log categories into src/transform.py.")
    parser.add_argument("--pr-body", type=pathlib.Path, help="Write a markdown PR body summarizing item changes.")
    args = parser.parse_args(argv)

    raw = fetch()
    tabs: Dict[str, List[int]] = {}
    item_subcats: Dict[str, Dict[int, List[str]]] = {}
    for tab in TABS:
        subcats = raw.get(tab)
        if not isinstance(subcats, dict):
            print(f"categories.php has no '{tab}' tab", file=sys.stderr)
            return 1
        tabs[tab] = sorted({item for items in subcats.values() for item in items if isinstance(item, int)})
        by_item: Dict[int, List[str]] = {}
        for subcat, items in subcats.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, int):
                    by_item.setdefault(item, []).append(subcat)
        item_subcats[tab] = {item: sorted(set(scs)) for item, scs in by_item.items()}

    lines = [BEGIN, "CATEGORY_ITEMS: Dict[str, List[int]] = {"]
    for tab, ids in tabs.items():
        lines.append(f'    "{tab}": {json.dumps(ids, separators=(",", ":"))},')
    lines += ["}", END]
    block = "\n".join(lines)

    source = TRANSFORM.read_text()
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    match = pattern.search(source)
    if not match:
        print(f"no generated block found in {TRANSFORM}", file=sys.stderr)
        return 1

    existing = parse_existing(match.group(0))
    added = {tab: sorted(set(tabs[tab]) - set(existing.get(tab, []))) for tab in TABS}
    removed = {tab: sorted(set(existing.get(tab, [])) - set(tabs[tab])) for tab in TABS}

    TRANSFORM.write_text(pattern.sub(lambda _: block, source))

    if args.pr_body is not None:
        has_changes = any(added.values()) or any(removed.values())
        item_names = fetch_item_names() if has_changes else {}
        pr_body = format_pr_body(added, removed, item_names, item_subcats)
        args.pr_body.parent.mkdir(parents=True, exist_ok=True)
        args.pr_body.write_text(pr_body)

    summary = ", ".join(f"{tab} {len(ids)}" for tab, ids in tabs.items())
    print(f"updated CATEGORY_ITEMS in {TRANSFORM.relative_to(ROOT)}: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
