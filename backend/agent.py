import datetime
import json
import logging
import os
import re
from typing import Optional
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

try:
    from .tools import search_fishing_report
    from .vector_store import search_fly_patterns
except ImportError:  # Allows running agent.py directly from the backend directory.
    from tools import search_fishing_report
    from vector_store import search_fly_patterns
# You may need to adjust the import for your Anthropic/Claude LLM wrapper
from langchain_anthropic import ChatAnthropic

WATERS_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "waters_by_region.json")
FLY_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "fly_patterns.json")
EXCLUDED_FLY_NAMES = {"Trout Slayer"}
ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_QUOTAS = {"dry": 4, "nymph": 4, "streamer": 4, "junk": 3}
WATERS_REGION_TO_FLY_TAGS = {
    "rocky_mountains_montana_wyoming": ["rocky_mountains", "western_us"],
    "colorado_front_range": ["colorado", "rocky_mountains"],
    "colorado_rockies": ["colorado", "rocky_mountains"],
    "northeast_new_england": ["northeast"],
    "northeast_catskills_delaware": ["northeast", "appalachia"],
    "northeast_new_york_adirondacks": ["northeast"],
    "northeast_pennsylvania": ["northeast", "appalachia"],
    "midwest_great_lakes": ["midwest"],
}
logger = logging.getLogger(__name__)


def load_waters_data():
    """Load curated waters-by-region dataset."""
    with open(WATERS_DATA_PATH, "r") as f:
        return json.load(f)


def load_fly_patterns_data():
    """Load canonical fly pattern catalog."""
    with open(FLY_DATA_PATH, "r") as f:
        return json.load(f)


def normalize_fly_text(text: str) -> str:
    """Normalize text for robust token matching."""
    lowered = text.lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def build_fly_catalog():
    """Build canonical fly lookup and alias map."""
    patterns = load_fly_patterns_data()
    canonical_names = [pattern["fly_name"] for pattern in patterns if pattern.get("fly_name")]
    canonical_set = set(canonical_names)

    alias_to_canonical = {}
    for name in canonical_names:
        normalized_name = normalize_fly_text(name)
        alias_to_canonical[normalized_name] = name

    curated_aliases = {
        "bwo": "Blue-Winged Olive (BWO)",
        "blue wing olive": "Blue-Winged Olive (BWO)",
        "blue winged olive": "Blue-Winged Olive (BWO)",
        "pt": "Pheasant Tail Nymph",
        "pheasant tail": "Pheasant Tail Nymph",
        "hares ear": "Hare's Ear Nymph",
        "hare s ear": "Hare's Ear Nymph",
        "prince": "Prince Nymph",
        "copper john": "Copper John",
        "zebra midge": "Zebra Midge",
        "bugger": "Woolly Bugger",
        "wooly bugger": "Woolly Bugger",
        "woolly bugger": "Woolly Bugger",
        "egg": "Egg Pattern",
        "san juan": "San Juan Worm",
        "pats rubber legs": "Pat's Rubber Legs",
        "pat s rubber legs": "Pat's Rubber Legs",
        "adams": "Parachute Adams",
        "adams dry": "Adams Dry Fly",
        "rs 2": "RS2",
    }
    for alias, canonical in curated_aliases.items():
        if canonical in canonical_set:
            alias_to_canonical[normalize_fly_text(alias)] = canonical

    searchable_phrases = sorted(alias_to_canonical.keys(), key=len, reverse=True)
    return {
        "canonical_set": canonical_set,
        "alias_to_canonical": alias_to_canonical,
        "searchable_phrases": searchable_phrases,
        "patterns": patterns,
    }


def ordered_unique(items):
    """Dedupe while preserving first-seen order."""
    seen = set()
    ordered = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def map_location_to_region(location: str) -> Optional[str]:
    """Map a user location string to a known region key."""
    normalized = re.sub(r"[^a-z0-9\s,]", " ", location.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    region_keywords = {
        "rocky_mountains_montana_wyoming": [
            "montana", " mt ", ",mt", "wyoming", " wy ", ",wy", "bozeman", "yellowstone",
            "missoula", "big sky", "jackson hole", "teton",
        ],
        "colorado_front_range": [
            "colorado", " co ", ",co", "boulder", "denver", "fort collins", "front range",
            "south platte", "cache la poudre",
        ],
        "colorado_rockies": [
            "aspen", "vail", "gunnison", "salida", "breckenridge", "steamboat",
            "fryingpan", "roaring fork", "arkansas river",
        ],
        "northeast_new_england": [
            "connecticut", " ct ", ",ct", "massachusetts", " ma ", ",ma", "vermont",
            " vt ", ",vt", "maine", " me ", ",me", "new hampshire", " nh ", ",nh", "new england",
        ],
        "northeast_catskills_delaware": [
            "catskills", "delaware", "beaverkill", "willowemoc", "esopus", "neversink",
            "sullivan county", "roscoe",
        ],
        "northeast_new_york_adirondacks": [
            "adirondack", "ausable", "saranac", "st regis", "lake placid",
        ],
        "northeast_pennsylvania": [
            "pennsylvania", " pa ", ",pa", "penns creek", "letort", "yellow breeches",
            "state college", "harrisburg",
        ],
        "midwest_great_lakes": [
            "michigan", " mi ", ",mi", "wisconsin", " wi ", ",wi", "minnesota", " mn ", ",mn",
            "great lakes", "driftless", "au sable", "pere marquette", "manistee",
        ],
    }

    normalized_with_padding = f" {normalized} "
    for region, keywords in region_keywords.items():
        if any(keyword in normalized_with_padding for keyword in keywords):
            return region

    # Fallback: if users enter exact river names, infer region from known waters.
    waters_data = load_waters_data()
    best_region = None
    best_score = 0
    for region, region_data in waters_data.items():
        waters = region_data.get("waters", [])
        score = sum(1 for water in waters if water.lower() in normalized)
        if score > best_score:
            best_region = region
            best_score = score
    return best_region if best_score > 0 else None


def get_waters(location: str, waters_data: dict, max_waters=3):
    """Get curated waters for a location-derived region."""
    region = map_location_to_region(location)
    if not region or region not in waters_data:
        return []
    return waters_data[region]["waters"][:max_waters]


def build_query(region_data: dict, seasonal_hint: str) -> str:
    """Build a richer retrieval query from region context."""
    species = ", ".join(region_data.get("dominant_species", []))
    description = region_data.get("description", "")
    notes = region_data.get("notes", "")
    return f"{species}. {description}. {notes}. {seasonal_hint}"


def extract_fly_names_from_reports(reports, fly_catalog):
    """
    Extract only known catalog flies from reports using canonical + alias matching.
    """
    alias_to_canonical = fly_catalog["alias_to_canonical"]
    searchable_phrases = fly_catalog["searchable_phrases"]
    found_flies = []
    for report in reports:
        normalized_report = f" {normalize_fly_text(report)} "
        for phrase in searchable_phrases:
            if f" {phrase} " in normalized_report:
                found_flies.append(alias_to_canonical[phrase])
    return ordered_unique(found_flies)


def unique_fly_patterns(fly_patterns):
    """Dedupe vector-store patterns by canonical fly_name."""
    unique = []
    seen_names = set()
    for pattern in fly_patterns:
        fly_name = pattern.get("fly_name")
        if not fly_name or fly_name in seen_names or fly_name in EXCLUDED_FLY_NAMES:
            continue
        seen_names.add(fly_name)
        unique.append(pattern)
    return unique


def prioritize_fly_patterns(unique_patterns, mentioned_flies):
    """Prioritize report-confirmed flies while preserving deterministic ordering."""
    if not mentioned_flies:
        return unique_patterns
    mentioned_set = set(mentioned_flies)
    confirmed = [p for p in unique_patterns if p.get("fly_name") in mentioned_set]
    remaining = [p for p in unique_patterns if p.get("fly_name") not in mentioned_set]
    return confirmed + remaining


def group_top_flies_by_type(fly_patterns, top_n_per_type=3):
    """Group patterns by type and keep top N per type."""
    grouped = {}
    for pattern in fly_patterns:
        fly_type = pattern.get("type", "unknown")
        if fly_type not in grouped:
            grouped[fly_type] = []
        if len(grouped[fly_type]) < top_n_per_type:
            grouped[fly_type].append(pattern)
    return grouped


def enforce_type_diversity(
    ranked_patterns,
    base_query,
    top_n_per_type=3,
    target_types=None,
    search_fn=None,
    debug_logs=False,
):
    """Backfill missing core fly types from type-targeted retrieval."""
    if target_types is None:
        target_types = ["dry", "nymph", "streamer", "junk"]
    if search_fn is None:
        search_fn = search_fly_patterns

    selected = []
    seen = set()
    for pattern in ranked_patterns:
        fly_name = pattern.get("fly_name")
        if fly_name and fly_name not in seen and fly_name not in EXCLUDED_FLY_NAMES:
            selected.append(pattern)
            seen.add(fly_name)

    grouped = group_top_flies_by_type(selected, top_n_per_type=top_n_per_type)
    for fly_type in target_types:
        while len(grouped.get(fly_type, [])) < top_n_per_type:
            type_query = f"{base_query}. effective {fly_type} fly patterns"
            candidates = search_fn(type_query, k=max(top_n_per_type * 5, 10))
            if debug_logs:
                candidate_preview = [
                    {
                        "fly_name": candidate.get("fly_name"),
                        "type": candidate.get("type"),
                    }
                    for candidate in candidates[:10]
                ]
                logger.info(
                    "Type backfill query=%s candidate_count=%s candidates=%s",
                    fly_type,
                    len(candidates),
                    candidate_preview,
                )
            added = False
            for candidate in candidates:
                candidate_name = candidate.get("fly_name")
                if (
                    candidate.get("type") == fly_type
                    and candidate_name
                    and candidate_name not in seen
                    and candidate_name not in EXCLUDED_FLY_NAMES
                ):
                    selected.append(candidate)
                    seen.add(candidate_name)
                    added = True
                    break
            if not added:
                break
            grouped = group_top_flies_by_type(selected, top_n_per_type=top_n_per_type)

    return flatten_grouped_flies(grouped)


def flatten_grouped_flies(grouped_flies):
    """Flatten grouped fly patterns preserving grouped order."""
    flat = []
    for fly_type in sorted(grouped_flies.keys()):
        flat.extend(grouped_flies[fly_type])
    return flat


def pattern_matches_region(pattern, region_tags):
    """Return True if the pattern's regions overlap any of the given tags."""
    if not region_tags:
        return False
    raw = pattern.get("regions")
    if not raw:
        return False
    if isinstance(raw, str):
        try:
            regions = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return False
    elif isinstance(raw, list):
        regions = raw
    else:
        return False
    return any(tag in regions for tag in region_tags)


def select_fly_box_with_quotas(
    base_query,
    report_fly_mentions,
    region_tags,
    quotas=None,
    search_fn=None,
    debug_logs=False,
):
    """Pick flies per type, scoring by report mentions + region match + similarity rank."""
    quotas = quotas or DEFAULT_QUOTAS
    if search_fn is None:
        search_fn = search_fly_patterns

    selected = []
    seen_names = set()
    mentioned = set(report_fly_mentions or [])

    for fly_type, target in quotas.items():
        candidates = search_fn(base_query, k=20, type_filter=fly_type)
        scored = []
        for idx, candidate in enumerate(candidates):
            name = candidate.get("fly_name")
            if not name or name in seen_names or name in EXCLUDED_FLY_NAMES:
                continue
            if candidate.get("type") != fly_type:
                continue
            score = 0.0
            if name in mentioned:
                score += 10
            if pattern_matches_region(candidate, region_tags):
                score += 3
            score += (len(candidates) - idx) * 0.1
            scored.append((score, idx, candidate))

        scored.sort(key=lambda s: (-s[0], s[1]))
        picks = []
        for _, _, candidate in scored:
            if len(picks) >= target:
                break
            name = candidate.get("fly_name")
            if name in seen_names:
                continue
            picks.append(candidate)
            seen_names.add(name)

        selected.extend(picks)
        if debug_logs:
            logger.info(
                "Quota fill type=%s filled=%s/%s picks=%s",
                fly_type,
                len(picks),
                target,
                [p.get("fly_name") for p in picks],
            )

    return selected


def _safe_json_object(content):
    """Best-effort extraction of the first JSON object from a string."""
    if not isinstance(content, str):
        return {}
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def verify_and_rerank_with_llm(grouped_flies, fly_names, location, region_tags=None):
    """Reorder-only LLM pass.

    The LLM may only reorder flies within each type. It cannot add, remove, or
    move flies between types. Any parse failure preserves the original order.
    """
    llm = ChatAnthropic(model=ANTHROPIC_MODEL)
    available_by_type = {
        fly_type: [p.get("fly_name") for p in patterns if p.get("fly_name")]
        for fly_type, patterns in grouped_flies.items()
    }
    prompt = (
        "You are reordering a fly fishing fly box.\n"
        "Rules:\n"
        "- Keep exactly the same flies and the same per-type counts.\n"
        "- Only reorder within each type, most likely to be effective first.\n"
        "- Do not invent flies.\n"
        "- Use only the names provided per type.\n\n"
        "Respond with strict JSON only, matching this schema:\n"
        '{"by_type": {"dry": ["..."], "nymph": ["..."], "streamer": ["..."], "junk": ["..."]}}\n\n'
        f"Location: {location}\n"
        f"Region tags: {region_tags or []}\n"
        f"Report mentions: {fly_names}\n"
        f"Flies by type: {available_by_type}\n"
    )
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "".join(
            part.get("text", str(part)) if isinstance(part, dict) else str(part)
            for part in content
        )
    parsed = _safe_json_object(content)
    by_type = parsed.get("by_type", {}) if isinstance(parsed, dict) else {}

    pattern_lookup = {
        p.get("fly_name"): p
        for patterns in grouped_flies.values()
        for p in patterns
        if p.get("fly_name")
    }

    reordered = {}
    for fly_type, patterns in grouped_flies.items():
        original_names = [p.get("fly_name") for p in patterns if p.get("fly_name")]
        proposed = by_type.get(fly_type, []) if isinstance(by_type, dict) else []
        kept = []
        seen = set()
        for name in proposed:
            if name in original_names and name not in seen:
                kept.append(name)
                seen.add(name)
        for name in original_names:
            if name not in seen:
                kept.append(name)
                seen.add(name)
        reordered[fly_type] = [pattern_lookup[name] for name in kept if name in pattern_lookup]

    return reordered

def get_seasonal_hint():
    """Return a string describing the current month/season for prompt biasing."""
    now = datetime.datetime.now()
    month = now.strftime("%B")
    # Optionally, map month to season
    return f"Month: {month}"

def recommend_flies(
    location: str,
    max_waters=3,
    max_reports=2,
    fly_box_size=15,
    use_llm_verification=True,
    quotas=None,
    debug_logs=True,
):
    """Main agent workflow: returns a quota-balanced fly box for a location."""
    quotas = quotas or DEFAULT_QUOTAS
    waters_data = load_waters_data()
    fly_catalog = build_fly_catalog()
    region = map_location_to_region(location)
    waters = get_waters(location, waters_data, max_waters=max_waters)
    region_tags = WATERS_REGION_TO_FLY_TAGS.get(region, [])
    search_call_count = 0

    def tracked_search(query_text, k=3, type_filter=None):
        nonlocal search_call_count
        search_call_count += 1
        return search_fly_patterns(query_text, k=k, type_filter=type_filter)

    if debug_logs:
        logger.info(
            "Recommendation start location=%s region=%s region_tags=%s waters=%s",
            location,
            region,
            region_tags,
            waters,
        )
    if not waters:
        return {"error": f"No region mapping or waters found for {location}."}

    all_reports = []
    for water in waters:
        report_text = search_fishing_report.invoke(water)
        reports = report_text.split('---')[:max_reports]
        all_reports.extend(reports)

    fly_names = extract_fly_names_from_reports(all_reports, fly_catalog)
    seasonal_hint = get_seasonal_hint()
    region_data = waters_data.get(region, {})
    query = build_query(region_data, seasonal_hint)
    if fly_names:
        query = f"{query} {' '.join(fly_names)}"
    if debug_logs:
        logger.info("RAG query=%s", query)
        logger.info("Report fly mentions=%s", fly_names)

    selected = select_fly_box_with_quotas(
        base_query=query,
        report_fly_mentions=fly_names,
        region_tags=region_tags,
        quotas=quotas,
        search_fn=tracked_search,
        debug_logs=debug_logs,
    )

    grouped_patterns = group_top_flies_by_type(
        selected, top_n_per_type=max(quotas.values())
    )

    verification = {"used_llm": False, "fallback_used": False}
    if use_llm_verification:
        try:
            grouped_patterns = verify_and_rerank_with_llm(
                grouped_patterns, fly_names, location, region_tags=region_tags
            )
            verification["used_llm"] = True
        except Exception:
            verification["fallback_used"] = True
    if debug_logs:
        logger.info("Verification=%s", verification)

    flat_final = flatten_grouped_flies(grouped_patterns)[:fly_box_size]
    if debug_logs:
        logger.info("Final flies by type=%s", grouped_patterns)
        logger.info("Vector search calls this request=%s", search_call_count)
    return {
        "location": location,
        "region": region,
        "region_tags": region_tags,
        "waters": waters,
        "flies_by_type": {
            fly_type: [
                {"fly_name": f.get("fly_name"), "type": f.get("type")}
                for f in patterns
            ]
            for fly_type, patterns in grouped_patterns.items()
        },
        "fly_box": [f.get("fly_name") for f in flat_final],
        "fly_types": [f.get("type") for f in flat_final],
        "report_fly_mentions": fly_names,
        "raw_reports": all_reports,
        "rag_query": query,
        "verification": verification,
    }

# Example usage for testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    result = recommend_flies("Boulder, CO")
    print("\nFlies By Type:\n", result["flies_by_type"])
    print("\nFly Box:", result["fly_box"])
    print("\nWaters Considered:", result["waters"])
    print("\nRAG Query:", result["rag_query"])
    print("\nVerification:", result["verification"])
    
# Placeholder for LangGraph agent
# This will contain the agent logic, tools, and state graph