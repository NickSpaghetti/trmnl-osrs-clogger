# Serverless transform for OSRS Collection Log (TempleOSRS API).
# Combines:
#   IDX_0: player_collection_log.php (player stats + obtained item IDs)
#   IDX_1: player_recent_items.php (latest drops; how many is set by `count` in settings.yml)
#   IDX_2: categories.php (category -> subcategory -> item IDs mapping)
# Outputs a compact, display-ready JSON payload for Liquid templates.
#
# TRMNL prepends its own harness to this file, so `from __future__` imports are not
# allowed here; hints use the typing module to stay compatible with Python 3.8+.

from typing import Any, Dict, List, Optional, Set, Tuple, TypedDict

# Latest Collections icons depend on each player's drops, so they load from RuneLite's CDN.
ICON_BASE = "https://static.runelite.net/cache/item/icon"

# Static icons are inlined into src/shared.liquid (see assets/icons/manifest.json and
# `make inline-icons`); these are their names in the `osrs_icons` lookup.
# Category icons
ELYSIAN_SIGIL = "elysian_sigil"
TWISTED_BOW = "twisted_bow"
CLUE_SCROLL = "clue_scroll"
FIGHTER_TORSO = "fighter_torso"
CHAMPIONS_CAPE = "champions_cape"
# Collection log books, one per rank
COLLECTION_LOG = "collection_log"
COLLECTION_LOG_BRONZE = "collection_log_bronze"
COLLECTION_LOG_IRON = "collection_log_iron"
COLLECTION_LOG_STEEL = "collection_log_steel"
COLLECTION_LOG_BLACK = "collection_log_black"
COLLECTION_LOG_MITHRIL = "collection_log_mithril"
COLLECTION_LOG_ADAMANT = "collection_log_adamant"
COLLECTION_LOG_RUNE = "collection_log_rune"
COLLECTION_LOG_DRAGON = "collection_log_dragon"
COLLECTION_LOG_GILDED = "collection_log_gilded"

# Unique collection log slots; only used if TempleOSRS omits the total.
DEFAULT_TOTAL_SLOTS = 1734
# Gilded rank: 90% of total slots, rounded down to the nearest 25 (https://oldschool.runescape.wiki/w/Collection_log#Ranks).
GILDED_FRACTION = 0.9
GILDED_ROUND_TO = 25
# Current Gilded threshold per the wiki; only used if TempleOSRS omits the total.
GILDED_FALLBACK_THRESHOLD = 1550

JsonDict = Dict[str, Any]


class RankDef(TypedDict):
    tier: str
    name: str
    threshold: int
    icon: str


class Rank(TypedDict):
    tier: str
    name: str
    label: str
    threshold: int
    icon: str


class Category(TypedDict):
    key: str
    name: str
    icon: str
    obtained: int
    total: int
    pct: int


class RecentItem(TypedDict):
    id: int
    name: str
    date: str
    notable: bool
    icon_url: str


CATEGORY_META: List[Tuple[str, str, str]] = [
    ("bosses", "Bosses", ELYSIAN_SIGIL),
    ("raids", "Raids", TWISTED_BOW),
    ("clues", "Clues", CLUE_SCROLL),
    ("minigames", "Minigames", FIGHTER_TORSO),
    ("other", "Other", CHAMPIONS_CAPE),
]

GAME_MODES: Dict[int, str] = {
    0: "Main",
    1: "Ironman",
    2: "UIM",
    3: "HCIM",
}

BASE_RANKS: List[RankDef] = [
    {"tier": "",     "name": "Unranked", "threshold": 0,    "icon": COLLECTION_LOG},
    {"tier": "I",    "name": "Bronze",   "threshold": 100,  "icon": COLLECTION_LOG_BRONZE},
    {"tier": "II",   "name": "Iron",     "threshold": 300,  "icon": COLLECTION_LOG_IRON},
    {"tier": "III",  "name": "Steel",    "threshold": 500,  "icon": COLLECTION_LOG_STEEL},
    {"tier": "IV",   "name": "Black",    "threshold": 700,  "icon": COLLECTION_LOG_BLACK},
    {"tier": "V",    "name": "Mithril",  "threshold": 900,  "icon": COLLECTION_LOG_MITHRIL},
    {"tier": "VI",   "name": "Adamant",  "threshold": 1000, "icon": COLLECTION_LOG_ADAMANT},
    {"tier": "VII",  "name": "Rune",     "threshold": 1100, "icon": COLLECTION_LOG_RUNE},
    {"tier": "VIII", "name": "Dragon",   "threshold": 1200, "icon": COLLECTION_LOG_DRAGON},
]


def icon_url(item_id: int) -> str:
    return f"{ICON_BASE}/{item_id}.png"


def format_rank(rank_def: RankDef) -> Rank:
    label = f"{rank_def['tier']}: {rank_def['name']}" if rank_def["tier"] else rank_def["name"]
    return {
        "tier": rank_def["tier"],
        "name": rank_def["name"],
        "label": label,
        "threshold": rank_def["threshold"],
        "icon": rank_def["icon"],
    }


def compute_ranks(total_finished: int, total_available: int) -> Tuple[Rank, Rank, int, int, bool]:
    gilded_threshold = (
        (int(total_available * GILDED_FRACTION) // GILDED_ROUND_TO) * GILDED_ROUND_TO
        if total_available > 0
        else GILDED_FALLBACK_THRESHOLD
    )
    ranks: List[RankDef] = list(BASE_RANKS) + [
        {"tier": "IX", "name": "Gilded", "threshold": gilded_threshold, "icon": COLLECTION_LOG_GILDED},
    ]

    current_idx = 0
    for idx, r in enumerate(ranks):
        if total_finished >= r["threshold"]:
            current_idx = idx

    current_rank = format_rank(ranks[current_idx])
    next_rank: Rank
    if current_idx + 1 < len(ranks):
        next_rank = format_rank(ranks[current_idx + 1])
        span = max(1, next_rank["threshold"] - current_rank["threshold"])
        progress_in_tier = max(0, total_finished - current_rank["threshold"])
        rank_pct = min(100, round((progress_in_tier / span) * 100))
        bar_target = next_rank["threshold"]
        is_max_rank = False
    else:
        next_rank = {
            "tier": "MAX",
            "name": "Complete",
            "label": "Complete",
            "threshold": total_available,
            "icon": COLLECTION_LOG_GILDED,
        }
        rank_pct = min(100, round((total_finished / max(1, total_available)) * 100))
        bar_target = total_available
        is_max_rank = True

    return current_rank, next_rank, rank_pct, bar_target, is_max_rank


def compute_categories(obtained_ids: Set[int], categories_map: Any) -> List[Category]:
    result: List[Category] = []
    for key, label, icon in CATEGORY_META:
        subcats = categories_map.get(key) if isinstance(categories_map, dict) else None
        unique_items: Set[int] = set()
        if isinstance(subcats, dict):
            for items in subcats.values():
                if isinstance(items, list):
                    for item_id in items:
                        if isinstance(item_id, int):
                            unique_items.add(item_id)
        total = len(unique_items)
        obtained = len(unique_items & obtained_ids) if total > 0 else 0
        pct = min(100, round((obtained / total) * 100)) if total > 0 else 0
        result.append({
            "key": key,
            "name": label,
            "icon": icon,
            "obtained": obtained,
            "total": total,
            "pct": pct,
        })
    return result


def parse_recent_items(raw_recent: Any) -> List[RecentItem]:
    items: List[RecentItem] = []
    data = raw_recent.get("data") if isinstance(raw_recent, dict) else None
    if not isinstance(data, list):
        return items

    for entry in data:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        if not isinstance(item_id, int):
            continue
        date_str = str(entry.get("date") or "")
        short_date = date_str[:10] if len(date_str) >= 10 else date_str
        items.append({
            "id": item_id,
            "name": str(entry.get("name") or ""),
            "date": short_date,
            "notable": bool(entry.get("notable_item")),
            "icon_url": icon_url(item_id),
        })
    return items


def as_dict(value: Any) -> JsonDict:
    return value if isinstance(value, dict) else {}


def run(input: JsonDict) -> JsonDict:
    trmnl_meta = as_dict(input.get("trmnl"))
    plugin_settings = as_dict(trmnl_meta.get("plugin_settings"))
    custom_fields = as_dict(plugin_settings.get("custom_fields_values"))
    requested_rsn = str(custom_fields.get("rsn") or "Player").strip() or "Player"
    only_notable = str(custom_fields.get("only_notable") or "0") == "1"

    clog_resp = as_dict(input.get("IDX_0"))
    recent_resp: Any = input.get("IDX_1")
    categories_resp: Any = input.get("IDX_2")

    player_data = clog_resp.get("data")
    if not isinstance(player_data, dict) or "total_collections_finished" not in player_data:
        err_msg: Optional[str] = None
        error = clog_resp.get("error")
        if isinstance(error, dict):
            err_msg = error.get("Message") or error.get("message")
        return {
            "ok": False,
            "error": err_msg or f"No synced Collection Log found for '{requested_rsn}'.",
            "player_name": requested_rsn,
            "book_icon": COLLECTION_LOG,
            "only_notable": only_notable,
            "trmnl": trmnl_meta,
        }

    player_name = str(
        player_data.get("player_name_with_capitalization")
        or player_data.get("player")
        or requested_rsn
    )
    game_mode_id = player_data.get("game_mode", 0)
    game_mode = GAME_MODES.get(game_mode_id, "Main") if isinstance(game_mode_id, int) else "Main"

    total_finished = int(player_data.get("total_collections_finished") or 0)
    total_available = int(player_data.get("total_collections_available") or DEFAULT_TOTAL_SLOTS)
    overall_pct = min(100, round((total_finished / max(1, total_available)) * 100, 1))

    cats_finished = int(player_data.get("total_categories_finished") or 0)
    cats_available = int(player_data.get("total_categories_available") or 0)

    hiscores_rank = player_data.get("collections_hiscores_rank")
    hiscores_rank_fmt: Optional[str] = (
        f"#{int(hiscores_rank):,}" if isinstance(hiscores_rank, (int, float)) and hiscores_rank > 0 else None
    )

    ehc_raw = player_data.get("ehc")
    ehc_fmt: Optional[str] = f"{float(ehc_raw):,.0f}" if isinstance(ehc_raw, (int, float)) else None

    last_changed = str(player_data.get("last_changed") or "")
    last_updated = last_changed[:10] if len(last_changed) >= 10 else ""

    raw_items = player_data.get("items") or []
    obtained_ids: Set[int] = set()
    if isinstance(raw_items, list):
        for it in raw_items:
            if isinstance(it, dict) and isinstance(it.get("id"), int):
                obtained_ids.add(it["id"])
            elif isinstance(it, int):
                obtained_ids.add(it)

    categories = compute_categories(obtained_ids, categories_resp)
    current_rank, next_rank, rank_pct, bar_target, is_max_rank = compute_ranks(
        total_finished, total_available
    )
    recent_items = parse_recent_items(recent_resp)

    return {
        "ok": True,
        "player_name": player_name,
        "game_mode": game_mode,
        "book_icon": COLLECTION_LOG,
        "total_finished": total_finished,
        "total_available": total_available,
        "overall_pct": overall_pct,
        "cats_finished": cats_finished,
        "cats_available": cats_available,
        "hiscores_rank": hiscores_rank_fmt,
        "ehc": ehc_fmt,
        "last_updated": last_updated,
        "only_notable": only_notable,
        "current_rank": current_rank,
        "next_rank": next_rank,
        "rank_pct": rank_pct,
        "bar_target": bar_target,
        "is_max_rank": is_max_rank,
        "categories": categories,
        "recent_items": recent_items,
        "recent_count": len(recent_items),
        "trmnl": trmnl_meta,
    }
