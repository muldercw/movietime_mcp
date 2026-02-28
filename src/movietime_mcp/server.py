"""
movietime-mcp Server — fetch movie showtimes from Fandango by location.

Tools exposed:
  • get_showtimes          — find movies & showtimes near a location
  • get_theater_showtimes  — get all showtimes at a specific theater
  • get_movie_details      — get details about a specific movie
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from movietime_mcp.scraper import (
    get_showtimes as _get_showtimes,
    get_theater_showtimes as _get_theater_showtimes,
    get_movie_details as _get_movie_details,
)

logger = logging.getLogger("movietime_mcp")

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="movietime-mcp",
    instructions=(
        "An MCP server that fetches movie showtimes from Fandango. "
        "Given a location (ZIP code, city/state, or city name), it returns "
        "nearby theaters with their current movies and showtimes. "
        "You can also get details about a specific theater or movie. "
        "Dates default to today if not specified."
    ),
)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_showtimes(
    location: str,
    date: str | None = None,
    page: int = 1,
) -> dict:
    """Get movie showtimes near a location from Fandango.

    Parameters
    ----------
    location : str
        Where to search for theaters and showtimes.
        Accepts:
        - ZIP code: "10001", "90210", "60601"
        - City, State: "New York, NY", "Los Angeles, CA", "Chicago, IL"
        - City name: "Seattle", "Boston", "Miami"
    date : str, optional
        Date to check showtimes for, in YYYY-MM-DD format.
        Defaults to today if not specified.
        Example: "2026-03-15"
    page : int, optional
        Page number for pagination — each page returns ~10 theaters.
        Default: 1.

    Returns
    -------
    dict
        A dict containing:
        - location: the search location
        - date: the date searched
        - page / total_pages: pagination info
        - theater_count: number of theaters returned
        - theaters: list of theaters, each with:
          - name, address, distance_miles, chain, amenities
          - movies: list of movies with title, rating, runtime,
            genres, showtimes, and Fandango ticket URLs
    """
    return _get_showtimes(location=location, date=date, page=page)


@mcp.tool()
def get_theater_showtimes(
    theater_id: str,
    date: str | None = None,
) -> dict:
    """Get all showtimes at a specific Fandango theater.

    Parameters
    ----------
    theater_id : str
        The Fandango theater identifier. Can be any of:
        - Theater slug: "amc-34th-street-14-aaqcr"
        - Theater page path: "/amc-34th-street-14-aaqcr/theater-page"
        - Full URL: "https://www.fandango.com/amc-34th-street-14-aaqcr/theater-page"
        You can get theater slugs/URLs from the get_showtimes results.
    date : str, optional
        Date in YYYY-MM-DD format. Defaults to today.

    Returns
    -------
    dict
        Theater details including name, address, amenities,
        and all movies with their showtimes for the given date.
    """
    return _get_theater_showtimes(theater_id=theater_id, date=date)


@mcp.tool()
def get_movie_details(movie_url: str) -> dict:
    """Get details about a specific movie from Fandango.

    Parameters
    ----------
    movie_url : str
        The Fandango movie URL or slug. Can be any of:
        - Full URL: "https://www.fandango.com/captain-america-2025-233496/movie-overview"
        - Path: "/captain-america-2025-233496/movie-overview"
        - Slug: "captain-america-2025-233496"
        You can get movie URLs from the get_showtimes results.

    Returns
    -------
    dict
        Movie details including:
        - title, rating, runtime, genres
        - synopsis / description
        - cast, director
        - poster image URL
        - release date
    """
    return _get_movie_details(movie_url=movie_url)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(verbose: bool = False) -> None:
    """Start the MCP server."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info("Starting movietime-mcp server v0.1.0")
    mcp.run()
