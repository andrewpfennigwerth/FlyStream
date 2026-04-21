# LangChain tools for FlyStream agent

from langchain.tools import tool
from tavily import TavilyClient
import os
import re

tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@tool
def search_local_waters(location: str) -> str:
    """
    Search for popular trout fishing waters near a given location.
    Returns a list of water names found in search results.
    """
    try:
        # Search for local fishing waters
        query = f"trout fishing rivers streams near {location}"
        response = tavily_client.search(query=query, search_depth="basic")

        waters = []
        # Extract water names from search results
        for result in response.get("results", [])[:5]:  # Limit to top 5 results
            content = result.get("content", "").lower()

            # Common water name patterns
            water_patterns = [
                r'(\w+ river)', r'(\w+ creek)', r'(\w+ stream)',
                r'(madison river)', r'(yellowstone river)', r'(gallatin river)'  # Specific famous waters
            ]

            for pattern in water_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    clean_name = match.title()
                    if clean_name not in waters and len(clean_name.split()) <= 3:
                        waters.append(clean_name)

        # Remove duplicates and limit to top 5
        waters = list(set(waters))[:5]

        return f"Found waters near {location}: {', '.join(waters)}" if waters else f"No specific waters found near {location}"

    except Exception as e:
        return f"Error searching for waters: {str(e)}"

@tool
def search_fishing_report(water_name: str) -> str:
    """
    Search for current fishing reports for a specific water body.
    Returns the latest fishing conditions and reports.
    """
    try:
        query = f"{water_name} fly fishing report {2026}"
        response = tavily_client.search(query=query, search_depth="basic")

        reports = []
        for result in response.get("results", [])[:3]:
            title = result.get("title", "")
            content = result.get("content", "")[:500]  # Limit content length
            url = result.get("url", "")

            reports.append(f"Title: {title}\nContent: {content}\nSource: {url}\n---")

        return "\n".join(reports) if reports else f"No recent reports found for {water_name}"

    except Exception as e:
        return f"Error getting fishing report: {str(e)}"