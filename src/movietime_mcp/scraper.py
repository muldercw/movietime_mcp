"""
Fandango scraper — fetch movie showtimes, theater info, and movie details.

Uses httpx to query Fandango's internal API and public HTML pages.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("movietime_mcp")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FANDANGO_BASE = "https://www.fandango.com"
FANDANGO_API = f"{FANDANGO_BASE}/napi/theaterswithshowtimes"
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{FANDANGO_BASE}/movietimes",
    "Origin": FANDANGO_BASE,
}

HTML_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _today_str() -> str:
    """Return today's date as YYYY-MM-DD."""
    return date.today().isoformat()


def _validate_date(dt: str | None) -> str:
    """Validate and return a date string, defaulting to today."""
    if not dt:
        return _today_str()
    try:
        datetime.strptime(dt, "%Y-%m-%d")
        return dt
    except ValueError:
        logger.warning("Invalid date '%s', using today", dt)
        return _today_str()


def _parse_location(location: str) -> dict[str, str]:
    """Parse a location string into API parameters.

    Supports:
      - ZIP codes:  "10001", "90210"
      - City, State: "New York, NY", "los angeles, ca"
      - City only:  "Chicago" (state defaults to empty)
    """
    location = location.strip()

    # ZIP code (5 digits, optionally with +4)
    if re.match(r"^\d{5}(-\d{4})?$", location):
        return {"zipCode": location}

    # City, State
    if "," in location:
        parts = [p.strip() for p in location.split(",", 1)]
        return {"city": parts[0], "state": parts[1]}

    # Bare city name
    return {"city": location, "state": ""}


def _fetch_json(url: str, params: dict[str, Any]) -> dict:
    """Fetch JSON from a URL with query parameters."""
    logger.debug("Fetching API: %s  params=%s", url, params)
    with httpx.Client(
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _fetch_html(url: str) -> str:
    """Fetch an HTML page and return text."""
    logger.debug("Fetching HTML: %s", url)
    with httpx.Client(
        headers=HTML_HEADERS,
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


# ---------------------------------------------------------------------------
# Showtime simplification
# ---------------------------------------------------------------------------

def _simplify_showtime(st: dict) -> dict:
    """Extract the key fields from a raw showtime object."""
    return {
        "time": st.get("ticketingDate", {}).get("localTime", "")
                if isinstance(st.get("ticketingDate"), dict)
                else st.get("dateTime", ""),
        "format": st.get("formatStr", ""),
        "ticket_url": (
            f"{FANDANGO_BASE}{st['ticketingJumpPageURL']}"
            if st.get("ticketingJumpPageURL")
            else None
        ),
        "is_sold_out": st.get("isSoldOut", False),
    }


def _simplify_variant(variant: dict) -> dict:
    """Simplify a movie variant (format grouping) into showtimes."""
    showtimes = []
    for ag in variant.get("amenityGroups", []):
        for st in ag.get("showtimes", []):
            showtimes.append(_simplify_showtime(st))
    return {
        "format": variant.get("filmFormatHeader", "Standard"),
        "showtimes": showtimes,
    }


def _simplify_movie(movie: dict) -> dict:
    """Simplify a movie object from the API response."""
    variants = [_simplify_variant(v) for v in movie.get("variants", [])]
    # Flatten all showtimes for a quick overview
    all_times = []
    for v in variants:
        for st in v["showtimes"]:
            label = st["time"]
            if v["format"] and v["format"] != "Standard":
                label += f" ({v['format']})"
            all_times.append(label)

    return {
        "id": movie.get("id"),
        "title": movie.get("title", "Unknown"),
        "rating": movie.get("rating"),
        "runtime_min": movie.get("runtime"),
        "genres": movie.get("genres", []),
        "release_date": movie.get("releaseDate"),
        "poster": (
            movie.get("poster", {}).get("size", {}).get("200")
            or movie.get("poster", {}).get("size", {}).get("full")
        ),
        "fandango_url": (
            f"{FANDANGO_BASE}{movie['mopURI']}"
            if movie.get("mopURI")
            else None
        ),
        "showtimes": all_times,
        "variants": variants,
    }


def _simplify_theater(theater: dict) -> dict:
    """Simplify a theater object from the API response."""
    movies = [_simplify_movie(m) for m in theater.get("movies", [])]
    return {
        "id": theater.get("id"),
        "name": theater.get("name", "Unknown Theater"),
        "address": theater.get("fullAddress", ""),
        "city": theater.get("city"),
        "state": theater.get("state"),
        "zip": theater.get("zip"),
        "distance_miles": (
            round(theater["distance"], 2)
            if theater.get("distance") is not None
            else None
        ),
        "phone": theater.get("phone"),
        "chain": theater.get("chainName"),
        "amenities": theater.get("amenitiesString", ""),
        "latitude": theater.get("geo", {}).get("latitude"),
        "longitude": theater.get("geo", {}).get("longitude"),
        "fandango_url": (
            f"{FANDANGO_BASE}{theater['theaterPageUrl']}"
            if theater.get("theaterPageUrl")
            else None
        ),
        "map_url": theater.get("mapURI"),
        "date": theater.get("displayDate") or theater.get("date"),
        "movie_count": len(movies),
        "movies": movies,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_showtimes(
    location: str,
    date: str | None = None,
    page: int = 1,
) -> dict:
    """
    Fetch movie showtimes near a location from Fandango.

    Parameters
    ----------
    location : str
        ZIP code, "City, State", or city name.
    date : str, optional
        Date in YYYY-MM-DD format (default: today).
    page : int, optional
        Page number for pagination (default: 1).

    Returns
    -------
    dict
        Theaters with their movies and showtimes.
    """
    dt = _validate_date(date)
    params = {**_parse_location(location), "date": dt, "page": str(page)}

    try:
        data = _fetch_json(FANDANGO_API, params)
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}"}
    except httpx.RequestError as e:
        return {"error": f"Request failed: {e}"}

    if not data or not data.get("theaters"):
        return {
            "location": location,
            "date": dt,
            "theater_count": 0,
            "theaters": [],
            "message": "No theaters or showtimes found for this location and date.",
        }

    theaters = [_simplify_theater(t) for t in data["theaters"]]
    pagination = data.get("pagination", {})

    return {
        "location": location,
        "date": dt,
        "page": page,
        "total_pages": pagination.get("totalPages", 1),
        "theater_count": len(theaters),
        "theaters": theaters,
    }


def get_theater_showtimes(
    theater_id: str,
    date: str | None = None,
) -> dict:
    """
    Fetch showtimes for a specific Fandango theater.

    The theater detail page is fetched via HTML scraping since the API
    returns theaters by location, not by individual ID.  We use the
    theaters-with-showtimes API filtered to a single theater.

    Parameters
    ----------
    theater_id : str
        Fandango theater slug or URL.
        Examples:
          - "amc-34th-street-14-aaqcr"
          - "/amc-34th-street-14-aaqcr/theater-page"
          - "https://www.fandango.com/amc-34th-street-14-aaqcr/theater-page"
    date : str, optional
        Date in YYYY-MM-DD format (default: today).

    Returns
    -------
    dict
        Theater details with movies and showtimes.
    """
    dt = _validate_date(date)

    # Normalise the theater identifier to a URL path
    slug = theater_id.strip().rstrip("/")
    if slug.startswith("http"):
        # Full URL — extract path
        slug = slug.split("fandango.com", 1)[-1]
    if not slug.startswith("/"):
        slug = f"/{slug}"
    if not slug.endswith("/theater-page"):
        slug = f"{slug}/theater-page"

    theater_url = f"{FANDANGO_BASE}{slug}?date={dt}"

    try:
        html = _fetch_html(theater_url)
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}"}
    except httpx.RequestError as e:
        return {"error": f"Request failed: {e}"}

    return _parse_theater_page(html, theater_url, dt)


def _parse_theater_page(html: str, url: str, dt: str) -> dict:
    """Parse a Fandango theater page for basic info and nearby theaters list.

    The actual showtimes on theater pages are loaded dynamically via JS,
    so we extract the theater's ZIP from the page and then call the API
    to get showtimes for that area, filtering to this specific theater.
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, Any] = {"url": url, "date": dt}

    # Theater name — prefer specific selectors, fall back to <title>
    title_el = soup.select_one("h1.subnav__title, .theaterDetailHeader__name")
    if not title_el:
        title_el = soup.select_one("title")
    if title_el:
        name = title_el.get_text(strip=True)
        # Clean common suffixes like " Movie Showtimes & Tickets | City | Fandango"
        name = re.sub(r"\s*Movie Showtimes.*$", "", name, flags=re.IGNORECASE).strip()
        name = re.sub(r"\s*\|.*$", "", name).strip()
        if not name:
            name = title_el.get_text(strip=True)
        result["name"] = name

    # Try to find theater's own ZIP from the page
    # Check JSON-LD postalCode, then context zipCode/zip fields
    zip_match = re.search(r'"postalCode"\s*:\s*"(\d{5})', html)
    if not zip_match:
        zip_match = re.search(r'"zipCode"\s*:\s*"(\d{5})"', html)
    if not zip_match:
        zip_match = re.search(r'"zip"\s*:\s*"(\d{5})"', html)

    if zip_match:
        zip_code = zip_match.group(1)
        # Call the API for this ZIP and filter to this theater
        api_data = _fetch_theater_via_api(zip_code, dt, url)
        if api_data:
            return api_data

    # Fallback: just return what we can parse from HTML
    result["message"] = (
        "Showtimes are loaded dynamically. Use get_showtimes with "
        "the theater's ZIP code to find showtimes."
    )
    return result


def _fetch_theater_via_api(zip_code: str, dt: str, theater_url: str) -> dict | None:
    """Fetch all theaters for a ZIP and filter to the matching theater URL."""
    try:
        data = _fetch_json(FANDANGO_API, {"zipCode": zip_code, "date": dt, "page": "1"})
    except Exception:
        return None

    if not data or not data.get("theaters"):
        return None

    # Try to match the theater by URL slug
    slug_match = re.search(r"/([a-z0-9-]+)/theater-page", theater_url, re.IGNORECASE)
    target_slug = slug_match.group(1).lower() if slug_match else ""

    for theater in data["theaters"]:
        t_slug = (theater.get("theaterPageUrl") or "").lower()
        if target_slug and target_slug in t_slug:
            return _simplify_theater(theater)

    # If no exact match, return the first theater
    if data["theaters"]:
        return _simplify_theater(data["theaters"][0])

    return None


def get_movie_details(movie_url: str) -> dict:
    """
    Fetch details about a specific movie from its Fandango page.

    Parameters
    ----------
    movie_url : str
        Fandango movie overview URL or slug.
        Examples:
          - "https://www.fandango.com/captain-america-brave-new-world-2025-233496/movie-overview"
          - "/captain-america-brave-new-world-2025-233496/movie-overview"
          - "captain-america-brave-new-world-2025-233496"

    Returns
    -------
    dict
        Movie details including title, rating, runtime, synopsis, cast, etc.
    """
    # Normalise URL
    slug = movie_url.strip().rstrip("/")
    if slug.startswith("http"):
        slug = slug.split("fandango.com", 1)[-1]
    if not slug.startswith("/"):
        slug = f"/{slug}"
    if "/movie-overview" not in slug and "/movie-times" not in slug:
        slug = f"{slug}/movie-overview"

    url = f"{FANDANGO_BASE}{slug}"

    try:
        html = _fetch_html(url)
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}", "url": url}
    except httpx.RequestError as e:
        return {"error": f"Request failed: {e}", "url": url}

    return _parse_movie_page(html, url)


def _parse_movie_page(html: str, url: str) -> dict:
    """Parse a Fandango movie overview page."""
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, Any] = {"url": url}

    # Title
    title_el = soup.select_one(
        "h1.subnav__title, .movie-details__title, "
        ".hero-text__title, .mop-detail-header__title, title"
    )
    if title_el:
        result["title"] = title_el.get_text(strip=True)
    else:
        title_tag = soup.select_one("title")
        result["title"] = title_tag.get_text(strip=True) if title_tag else "Unknown"

    # Rating & runtime from structured data or page elements
    rating_el = soup.select_one(
        ".movie-details__rating, .mop-detail-header__badge, "
        ".hero-text__rating, .mop-ratings-row__badge"
    )
    if rating_el:
        result["rating"] = rating_el.get_text(strip=True)

    runtime_el = soup.select_one(
        ".movie-details__runtime, .mop-detail-header__meta, "
        ".hero-text__runtime"
    )
    if runtime_el:
        result["runtime"] = runtime_el.get_text(strip=True)

    # Synopsis
    synopsis_el = soup.select_one(
        ".movie-details__synopsis, .mop-detail-header__synopsis, "
        "#movie-detail-synopsis, .js-mop-synopsis"
    )
    if synopsis_el:
        result["synopsis"] = synopsis_el.get_text(strip=True)

    # Cast
    cast_els = soup.select(
        ".movie-details__cast a, .mop-detail-header__cast a, "
        ".movie-cast__actor-name"
    )
    if cast_els:
        result["cast"] = [c.get_text(strip=True) for c in cast_els]

    # Director
    director_el = soup.select_one(
        ".movie-details__director, .movie-cast__director"
    )
    if director_el:
        result["director"] = director_el.get_text(strip=True)

    # Genre
    genre_els = soup.select(
        ".movie-details__genre a, .mop-detail-header__genre a"
    )
    if genre_els:
        result["genres"] = [g.get_text(strip=True) for g in genre_els]

    # Poster image
    poster_el = soup.select_one(
        ".movie-details__poster img, .hero-image img, "
        ".mop-detail-header__poster img"
    )
    if poster_el:
        result["poster"] = poster_el.get("src") or poster_el.get("data-src")

    # JSON-LD structured data (most reliable source)
    ld_scripts = soup.select('script[type="application/ld+json"]')
    for script in ld_scripts:
        try:
            import json
            ld = json.loads(script.string)
            if isinstance(ld, dict) and ld.get("@type") == "Movie":
                result["title"] = ld.get("name", result.get("title"))
                if ld.get("description"):
                    result["synopsis"] = ld["description"]
                if ld.get("duration"):
                    result["runtime"] = ld["duration"]
                if ld.get("contentRating"):
                    result["rating"] = ld["contentRating"]
                if ld.get("genre"):
                    result["genres"] = (
                        ld["genre"] if isinstance(ld["genre"], list)
                        else [ld["genre"]]
                    )
                if ld.get("image"):
                    result["poster"] = ld["image"]
                if ld.get("datePublished"):
                    result["release_date"] = ld["datePublished"]
                if ld.get("director"):
                    directors = ld["director"]
                    if isinstance(directors, list):
                        result["director"] = ", ".join(
                            d.get("name", "") for d in directors if isinstance(d, dict)
                        )
                    elif isinstance(directors, dict):
                        result["director"] = directors.get("name")
                if ld.get("actor"):
                    result["cast"] = [
                        a.get("name", "")
                        for a in ld["actor"]
                        if isinstance(a, dict)
                    ]
                break
        except Exception:
            continue

    return result
