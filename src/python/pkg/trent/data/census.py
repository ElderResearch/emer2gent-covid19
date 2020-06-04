"""Download Census demographics for adding to an ABT.

Goals: Add features (likely Census data) to the ABT to account for:

 - [ ] Age
 - [ ] Gender
 - [ ] Race
 - [ ] Other relevant demographic factors re: health outcomes

 NB: This product uses the Census Bureau Data API but is not endorsed or certified
 by the Census Bureau.
"""

import os
from typing import Any, Dict, List, Optional

import census

__all__ = ["check_api_key", "get_pop_by_county"]


_API_KEY_NAME = "CENSUS_API_KEY"
_API_SESSION: Optional[census.core.Census] = None
_API_YEAR = 2018


def _get_api_key() -> str:
    """Fetch the API key from the environment."""
    check_api_key()
    return os.environ[_API_KEY_NAME]


def check_api_key() -> None:
    """Check for the existence of a Census API key in system variables."""
    if _API_KEY_NAME not in os.environ:
        raise ValueError(f"{_API_KEY_NAME} not found on the environment")


def _get_census_object(key: Optional[str]) -> census.core.Census:
    """Return a Census object, creating a new session if needed.

    Args:
        key (str): API key

    Returns:
        census.Census
    """
    global _API_SESSION
    if _API_SESSION is None:
        if key is None:
            key = _get_api_key()
        _API_SESSION = census.Census(key=key, year=_API_YEAR)
    return _API_SESSION


def get_pop_by_county(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return population for all US counties.

    Args:
        api_key (str): optional API key (searches for system variable if not given)

    Returns:
        (list[dict]) population measures per state and county
    """
    co = _get_census_object(api_key)
    return co.acs5.state_county(["B01003_001E"], state_fips="*", county_fips="*")
