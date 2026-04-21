import datetime
import json
import os
import re
from typing import Optional
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from tools import search_fishing_report
from vector_store import search_fly_patterns
# You may need to adjust the import for your Anthropic/Claude LLM wrapper
from langchain_anthropic import ChatAnthropic

WATERS_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "waters_by_region.json")
FLY_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "fly_patterns.json")


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
        if not fly_name or fly_name in seen_names:
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

def get_seasonal_hint():
    """Return a string describing the current month/season for prompt biasing."""
    now = datetime.datetime.now()
    month = now.strftime("%B")
    # Optionally, map month to season
    return f"Month: {month}"

def recommend_flies(location: str, max_waters=3, max_reports=2, fly_box_size=6):
    """
    Main agent workflow: returns a guide-like fly box recommendation for a location.
    """
    waters_data = load_waters_data()
    fly_catalog = build_fly_catalog()
    region = map_location_to_region(location)
    waters = get_waters(location, waters_data, max_waters=max_waters)
    if not waters:
        return {"error": f"No region mapping or waters found for {location}."}

    # 2. Get recent reports for curated waters
    all_reports = []
    for water in waters:
        report_text = search_fishing_report.invoke(water)
        # Split into individual reports
        reports = report_text.split('---')[:max_reports]
        all_reports.extend(reports)

    # 3. Extract fly names from reports
    fly_names = extract_fly_names_from_reports(all_reports, fly_catalog)
    # 4. Build strong region query + seasonal context
    seasonal_hint = get_seasonal_hint()
    region_data = waters_data.get(region, {})
    query = build_query(region_data, seasonal_hint)
    if fly_names:
        query = f"{query} {' '.join(fly_names)}"

    # 5. Query vector store for recommended flies
    # Pull extra candidates so dedupe/prioritization can still fill fly_box_size.
    raw_patterns = search_fly_patterns(query, k=max(fly_box_size * 3, fly_box_size))
    unique_patterns = unique_fly_patterns(raw_patterns)
    ranked_patterns = prioritize_fly_patterns(unique_patterns, fly_names)
    fly_patterns = ranked_patterns[:fly_box_size]

    # 6. Synthesize a guide-like recommendation with Claude
    llm = ChatAnthropic(model="claude-sonnet-4-6")
    fly_list = "\n".join([f"- {f['fly_name']} ({f['type']})" for f in fly_patterns])
    prompt = (
        f"You are a friendly, seasoned, realistic fly fishing guide. Based on recent reports and the current season, "
        f"here are the flies you should have in your box for {location}. These are commonly mentioned and effective now, "
        f"but conditions can change quickly—so bring a variety!\n\n"
        f"Recommended fly box:\n{fly_list}\n\n"
        f"These recommendations are based on recent reports and typical seasonal hatches, not on exact current water conditions.\n\n"
        f"If you want to add a short tip or encouragement, do so in a single sentence at the end."
    )
    response = llm.invoke(prompt)
    guide_text = response.content if hasattr(response, "content") else str(response)
    return {
        "location": location,
        "region": region,
        "waters": waters,
        "fly_box": [f["fly_name"] for f in fly_patterns],
        "fly_types": [f["type"] for f in fly_patterns],
        "report_fly_mentions": fly_names,
        "raw_reports": all_reports,
        "rag_query": query,
        "guide_message": str(response)
    }

# Example usage for testing
if __name__ == "__main__":
    result = recommend_flies("Farmington, CT")
    print("\nGuide Recommendation:\n", result["guide_message"])
    print("\nFly Box:", result["fly_box"])
    print("\nWaters Considered:", result["waters"])
    
# Placeholder for LangGraph agent
# This will contain the agent logic, tools, and state graph