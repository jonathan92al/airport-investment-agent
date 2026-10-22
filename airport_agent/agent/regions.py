"""Map free-text region names to US state codes. Deterministic, so the LLM never guesses states."""
import re

STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA",
    "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}

# Informal regions have no official definition; these are stated assumptions, shown to the user.
REGIONS = {
    "new england": ["CT", "ME", "MA", "NH", "RI", "VT"],
    "northeast": ["CT", "ME", "MA", "NH", "RI", "VT", "NY", "NJ", "PA"],
    "mid atlantic": ["NY", "NJ", "PA", "DE", "MD", "DC", "VA", "WV"],
    "southeast": ["AL", "FL", "GA", "KY", "MS", "NC", "SC", "TN", "VA", "WV", "AR", "LA"],
    "midwest": ["IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "SD", "WI"],
    "southwest": ["AZ", "NM", "OK", "TX"],
    "mountain west": ["CO", "ID", "MT", "NV", "UT", "WY"],
    "west coast": ["CA", "OR", "WA"],
    "pacific northwest": ["OR", "WA"],
    "us": sorted(set(STATE_NAMES.values())),
}
REGIONS["usa"] = REGIONS["nationwide"] = REGIONS["united states"] = REGIONS["us"]


def resolve(text: str | None) -> list[str] | None:
    """State codes for a region phrase such as 'New England', 'Texas' or 'CA and NV'. None if unknown."""
    if not text:
        return None
    states: list[str] = []
    for part in re.split(r",|\band\b|&", text.lower()):
        part = part.strip().removeprefix("the ").strip()
        if part in REGIONS:
            states += REGIONS[part]
        elif part in STATE_NAMES:
            states.append(STATE_NAMES[part])
        elif part.upper() in STATE_NAMES.values():
            states.append(part.upper())
        else:
            return None
    return sorted(set(states))
