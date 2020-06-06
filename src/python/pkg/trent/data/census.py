"""Download Census demographics for adding to an ABT.

Goals: Add features (likely Census data) to the ABT to account for:

 - Age
 - Gender
 - Race
 - Other relevant demographic factors re: health outcomes(?)

We're using 2018 ACS5 because it seemsto be more complete for smaller counties. This is
easy to go back and text by changing _API_DATASET.


ACS tables:

| What             | Table        | Fields | Notes                               |
| ---              | ---          | ---    | ---                                 |
| Pop.             | B01003       | 001E   | No errors reported for any measures |
| Age              | B01001       | *      | Calculate marginals from these      |
| Gender           | B01001       | *      | Calculate marginals from these      |
| Race             | B02001       | *      | Cf. C02003 for more categories      |
| Median HH income | B19013[,A-I] | 001E   | Median HH instead of per-capita     |


Output table format:

 | state_fips | county_fips | <cols ...> |


Usage:

    pop = trent.data.census.get_pop()


NB: This product uses the Census Bureau Data API but is not endorsed or certified
by the Census Bureau.
"""

import logging
import os
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

import census
import pandas as pd

__all__ = [
    "check_for_api_key",
    "get_dem_age_gender",
    "get_dem_median_hh_income",
    "get_dem_pop",
    "get_dem_race",
    "get_fields_per_county",
    "get_table_per_county",
    "list_fields",
    "list_tables",
]


_API_KEY_NAME = "CENSUS_API_KEY"

# Tracks the session over time
API_SESSION: Optional[census.core.ACSClient] = None

# Changing these module constants would change the underlying source
API_DATASET = "acs5"
API_YEAR = 2018

# This is a big hack: we load an cache the tables and fields on first run
# b/c they have weird non-local effects with one another later.
_API_TABLES: Dict[str, Dict] = {}
_API_FIELDS: Dict[str, Dict] = {}


logger = logging.getLogger(__name__)


# Private functions ------------------------------------------------------------


def _init_api(key: Optional[str] = None) -> None:
    """Utility function for working in notebooks."""
    _get_api_client(key=key)


def _get_api_key() -> str:
    """Fetch the API key from the environment."""
    logger.info("Getting API key")

    check_for_api_key()
    return os.environ[_API_KEY_NAME]


def _get_api_client(key: Optional[str] = None) -> census.core.ACSClient:
    """Return a Census object, creating a new session if needed.

    Args:
        key (str): API key

    Returns:
        census.Census
    """
    global API_SESSION, _API_FIELDS, _API_TABLES

    if API_SESSION is None:
        if key is None:
            key = _get_api_key()
        else:
            logger.info("Setting API key from string")

        logger.info("Creating new session")
        co = census.Census(key=key, year=API_YEAR)
        API_SESSION = getattr(co, API_DATASET)

        # Get the table and field list upon creation
        if not _API_FIELDS or not _API_TABLES:
            logger.info("Creating API_TABLES and API_FIELDS")
            _API_TABLES = list_tables(fmt="dict")
            _API_FIELDS = list_fields(fmt="dict")
    return API_SESSION


def _get_fields_for_table(tbl: str, api_key: Optional[str] = None) -> List[str]:
    """Collect all fields associated with a Census table."""
    if not _API_FIELDS:
        _init_api(key=api_key)
    return sorted(k for k in _API_FIELDS if _API_FIELDS[k]["group"] == tbl)


def _translate_state_county_result(
    result: List[Dict],
    map_dict: Optional[Dict[str, str]] = None,
    map_fn: Optional[Callable[[Dict], Dict]] = None,
) -> List[Dict]:
    """Map an API result (list[dict]) to an aggregated/better named version.

    Args:
        result (list[dict]): the API output, including *at least*
            "state" and "county"
        map_dict (dict[str, str]): a mapper from Census fields to usable
            column names
        map_fn (callable, dict->dict): a mapping *function* from a Census
            results dict to some other arbitrary dict (e.g., for column ops)

    Returns:
        (list[dict]) a transformed version of the input list

    NOTE: One and only one of `map_dict` and `map_fn` should be specified.
    """

    # Check that we have reasonable parameters (only one mapper specified)
    if (map_dict is not None) == (map_fn is not None):
        raise ValueError("one of map_dict and map_fn must be given")

    output: List[Dict] = []

    # Simple, dict-based mapper
    if map_dict is not None:
        logger.info("Translating result using map_dict")

        for d in result:
            entry = {"state_fips": d["state"], "county_fips": d["county"]}
            for old, new in map_dict.items():
                entry[new] = d[old]
            output.append(entry)
        return output

    # Functional wrapper
    if map_fn is not None:
        logger.info("Translating result using map_fn")

        for d in result:
            entry = {"state_fips": d["state"], "county_fips": d["county"]}
            for k, v in map_fn(d).items():
                entry[k] = v
            output.append(entry)
        return output

    raise ValueError("unexpected function exit; neither map_dict nor map_fn were used")


def _mark_missings_as_na(
    result: List[Dict], exclude_cols: Iterable[str] = ()
) -> List[Dict]:
    """Selectively mark Census results < 0 or None as NA.

    Census items (e.g., median HH income) seem to return large
    negative values when the data is not available. Sometimes we also
    get None.

    This should be called _before_ any mapping!

    Args:
        result (list[dict]): the Census API output
        exclude_cols (iterable): columns to exclude from this task

    Returns:
        (list[dict])  a transformed version of the input
    """
    cols_to_exclude = {"state", "county"}.union(exclude_cols)
    # Count the values we changed
    missing_counts: Dict[Any, int] = defaultdict(lambda: 0)
    output = []
    for entry in result:
        for field in set(entry).difference(cols_to_exclude):
            if entry[field] is None or entry[field] < 0:
                missing_counts[entry[field]] += 1
                entry[field] = pd.NA
        output.append(entry)

    for k in missing_counts:
        logger.info(f"Marked {missing_counts[k]} {k} results as NA")

    return output


# Public functions -------------------------------------------------------------


def check_for_api_key() -> None:
    """Check for the existence of a Census API key in system variables."""
    if _API_KEY_NAME not in os.environ:
        raise KeyError(f"{_API_KEY_NAME} not found on the environment")


def list_tables(
    api_key: Optional[str] = None, fmt: str = "DataFrame"
) -> Union[pd.DataFrame, Dict[str, Dict]]:
    """List all tables returned by the API using pandas.

    Args:
        api_key (optional str): user's Census API key
        fmt (str): return format; one of "DataFrame" or "dict"

    Returns:
        (DataFrame) table list
    """
    logger.info("Generating table list")

    api = _get_api_client(api_key)
    tables = api.tables()

    # Tables is a list of dict, so reformat and return
    if fmt.lower() == "dict":
        return {d["name"]: d for d in tables}

    return pd.DataFrame([{k: t[k] for k in t if k != "variables"} for t in tables])


def list_fields(
    api_key: Optional[str] = None, fmt: str = "DataFrame"
) -> Union[pd.DataFrame, Dict[str, Dict]]:
    """List all fields returned by the API using pandas.

    Args:
        api_key (optional str): user's Census API key
        fmt (str): return format; one of "DataFrame" or "dict"

    Returns:
        (DataFrame or dict) field list
    """
    logger.info("Generating fields list")

    api = _get_api_client(api_key)
    fields: Dict = api.fields()

    # fields is a dict keyed by the field name
    if fmt.lower() == "dict":
        return fields

    # Unwrap the API result for pandas
    reformatted = []
    if "ucgid" in fields:
        del fields["ucgid"]
    for k in fields:
        dd = {"field": k}
        for j in fields[k]:
            dd[j] = fields[k][j]
        reformatted.append(dd)

    return pd.DataFrame(reformatted)


def get_fields_per_county(
    fields: Iterable[str],
    state_fips: str = "*",
    county_fips: str = "*",
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Collect arbitrary fields at the county level.

    Args:
        fields (list[str]): fields to collect
        state_fips (str): state FIPS codes, default to all
        county_fips (str): county FIPS codes, default to all
        api_key (optional str): API key

    Returns:
        a list of ACS disctionary entries
    """
    logger.info("Gathering fields per county")

    api = _get_api_client(api_key)
    return api.state_county(
        fields=fields, state_fips=state_fips, county_fips=county_fips
    )


def get_table_per_county(
    table: str,
    state_fips: str = "*",
    county_fips: str = "*",
    api_key: Optional[str] = None,
) -> List[Dict]:
    """Collect all fields from a table at the county level.

    Args:
        table (str): table identifier, e.g., "B01003"
        state_fips (str): state FIPS codes, default to all
        county_fips (str): county FIPS codes, default to all
        api_key (optional str): API key

    Returns:
        a list of ACS disctionary entries
    """
    logger.info("Gathering table per county")

    fields = _get_fields_for_table(table, api_key=api_key)
    return get_fields_per_county(
        fields, state_fips=state_fips, county_fips=county_fips, api_key=api_key
    )


def get_dem_pop(api_key: Optional[str] = None,) -> List[Dict]:
    """Collect per-county population.

    Args:
        api_key (optional str): API key

    Returns:
        (list[dict]) rows of a data frame, keys are
            'state_fips' and 'county_fips'
    """
    result = get_fields_per_county(["B01003_001E"], api_key=api_key)
    result = _mark_missings_as_na(result)
    result = _translate_state_county_result(
        result, map_dict={"B01003_001E": "acs_pop_total"}
    )
    return result


def get_dem_race(api_key: Optional[str] = None,) -> List[Dict]:
    """Collect a racial demographics by county.

    Args:
        api_key (optional str): API key

    Returns:
        (list[dict]) rows of a data frame, keys are
            'state_fips' and 'county_fips'
    """
    FIELDS_MAP = {
        "B02001_001E": "acs_race_total",
        "B02001_002E": "acs_race_white",
        "B02001_003E": "acs_race_black",
        "B02001_004E": "acs_race_am_ind",
        "B02001_005E": "acs_race_asian",
        "B02001_006E": "acs_race_hawaiian",
        "B02001_007E": "acs_race_other_single",
        "B02001_008E": "acs_race_two_or_more",
        "B02001_009E": "acs_race_two_or_more_incl_other",
        "B02001_010E": "acs_race_two_or_more_excl_other_three_or_more",
    }

    output = get_table_per_county("B02001", api_key=api_key)
    output = _mark_missings_as_na(output)
    result = _translate_state_county_result(output, map_dict=FIELDS_MAP)
    return result


def get_dem_age_gender(api_key: Optional[str] = None,) -> List[Dict]:
    """Collect age & gender demographics by county.

    Args:
        api_key (optional str): API key

    Returns:
        (list[dict]) rows of a data frame, keys are
            'state_fips' and 'county_fips'
    """

    def _mapper(d: Dict) -> Dict:
        """Custom mapper to aggregate per-gender age brackets."""
        o = {}
        # Add in the total gender populations
        o["acs_gender_total"] = d["B01001_001E"]
        o["acs_gender_male"] = d["B01001_002E"]
        o["acs_gender_female"] = d["B01001_026E"]
        # Compute per-bucket totals for each age range
        o["acs_age_lt_05"] = d["B01001_003E"] + d["B01001_027E"]
        o["acs_age_05_09"] = d["B01001_004E"] + d["B01001_028E"]
        o["acs_age_10_14"] = d["B01001_005E"] + d["B01001_029E"]
        o["acs_age_15_17"] = d["B01001_006E"] + d["B01001_030E"]
        o["acs_age_18_19"] = d["B01001_007E"] + d["B01001_031E"]
        o["acs_age_20"] = d["B01001_008E"] + d["B01001_032E"]
        o["acs_age_21"] = d["B01001_009E"] + d["B01001_033E"]
        o["acs_age_22_24"] = d["B01001_010E"] + d["B01001_034E"]
        o["acs_age_25_29"] = d["B01001_011E"] + d["B01001_035E"]
        o["acs_age_30_34"] = d["B01001_012E"] + d["B01001_036E"]
        o["acs_age_35_39"] = d["B01001_013E"] + d["B01001_037E"]
        o["acs_age_40_44"] = d["B01001_014E"] + d["B01001_038E"]
        o["acs_age_45_49"] = d["B01001_015E"] + d["B01001_039E"]
        o["acs_age_50_54"] = d["B01001_016E"] + d["B01001_040E"]
        o["acs_age_55_59"] = d["B01001_017E"] + d["B01001_041E"]
        o["acs_age_60_61"] = d["B01001_018E"] + d["B01001_042E"]
        o["acs_age_62_64"] = d["B01001_019E"] + d["B01001_043E"]
        o["acs_age_65_66"] = d["B01001_020E"] + d["B01001_044E"]
        o["acs_age_67_69"] = d["B01001_021E"] + d["B01001_045E"]
        o["acs_age_70_74"] = d["B01001_022E"] + d["B01001_046E"]
        o["acs_age_75_79"] = d["B01001_023E"] + d["B01001_047E"]
        o["acs_age_80_84"] = d["B01001_024E"] + d["B01001_048E"]
        o["acs_age_85_up"] = d["B01001_025E"] + d["B01001_049E"]
        return o

    table = get_table_per_county("B01001", api_key=api_key)
    result = _mark_missings_as_na(table)
    result = _translate_state_county_result(result, map_fn=_mapper)
    return result


def get_dem_median_hh_income(api_key: Optional[str] = None,) -> List[Dict]:
    """Collect median household income by county.

    This data is spread across multiple tables, as we might want to
    collect per-demographic numbers.

    B19013	median HH income, last 12 mos (2018 inflation-adjusted $)
    B19013A	median HH income, "", white alone householder
    B19013B	median HH income, "", black or african american alone ""
    B19013C	median HH income, "", american indian and alaska native alone ""
    B19013D	median HH income, "", asian alone ""
    B19013E	median HH income, "", native hawaiian and other pacific islander alone ""
    B19013F	median HH income, "", some other race alone ""
    B19013G	median HH income, "", two or more races ""
    B19013H	median HH income, "", white alone, not hispanic or latino ""
    B19013I	median HH income, "", hispanic or latino ""

    Args:
        api_key (optional str): API key

    Returns:
        (list[dict]) rows of a data frame, keys are
            'state_fips' and 'county_fips'
    """
    FIELDS = {
        "B19013_001E": "acs_median_hh_inc_total",
        "B19013A_001E": "acs_median_hh_inc_white",
        "B19013B_001E": "acs_median_hh_inc_black",
        "B19013C_001E": "acs_median_hh_inc_am_ind",
        "B19013D_001E": "acs_median_hh_inc_asian",
        "B19013E_001E": "acs_median_hh_inc_hawaiian",
        "B19013F_001E": "acs_median_hh_inc_other_single",
        "B19013G_001E": "acs_median_hh_inc_two_or_more_races",
        "B19013H_001E": "acs_median_hh_inc_white_non_hispanic",
        "B19013I_001E": "acs_median_hh_inc_hispanic",
    }
    result = get_fields_per_county(list(FIELDS.keys()), api_key=api_key)
    result = _mark_missings_as_na(result)
    result = _translate_state_county_result(result, map_dict=FIELDS)

    return result
