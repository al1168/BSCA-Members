"""Google Places address autocomplete widget (native Qt, async via QtNetwork).

`parse_place_location` is pure and unit-tested. The widget (added below) degrades
to a plain text field when no API key is configured.
"""

AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def parse_place_location(details_json) -> str:
    """Extract 'lng,lat' from a Place Details response, or '' if absent.

    Reads result.geometry.location.{lng,lat}. Never raises.
    """
    try:
        loc = details_json["result"]["geometry"]["location"]
        return f"{loc['lng']},{loc['lat']}"
    except (KeyError, TypeError):
        return ""
