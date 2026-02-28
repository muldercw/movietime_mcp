# movietime-mcp

An MCP (Model Context Protocol) server that retrieves movie showtimes from Fandango. Search by ZIP code, city/state, or city name to find theaters and showtimes near you.

## Features

- **Search by location** – ZIP code, "City, State", or city name
- **Browse showtimes** – see what's playing at nearby theaters with dates and times
- **Theater details** – get showtimes for a specific theater
- **Movie details** – fetch ratings, synopsis, cast, and more for any movie
- **Pagination** – navigate through large result sets

## Quick Start

No installation needed if you have [`uvx`](https://docs.astral.sh/uv/):

```bash
uvx movietime-mcp
```

Or install from the repo:

```bash
uv pip install git+https://github.com/muldercw/movietime_mcp.git
movietime-mcp
```

## Integration

### Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "movietime-mcp": {
      "command": "uvx",
      "args": ["movietime-mcp"]
    }
  }
}
```

### VS Code

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "movietime-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["movietime-mcp"]
    }
  }
}
```

## Tools

### `get_showtimes`

Search for movie showtimes at theaters near a location.

| Parameter  | Type | Required | Description |
|------------|------|----------|-------------|
| `location` | str  | Yes      | ZIP code (e.g. `"10001"`), city + state (e.g. `"Los Angeles, CA"`), or city name |
| `date`     | str  | No       | Date in `YYYY-MM-DD` format (defaults to today) |
| `page`     | int  | No       | Page number for pagination (default `1`) |

### `get_theater_showtimes`

Get showtimes for a specific Fandango theater.

| Parameter    | Type | Required | Description |
|--------------|------|----------|-------------|
| `theater_id` | str  | Yes      | Fandango theater slug (e.g. `"amc-empire-25-aatis"`) |
| `date`       | str  | No       | Date in `YYYY-MM-DD` format (defaults to today) |

### `get_movie_details`

Get detailed information about a movie (synopsis, cast, ratings, etc.).

| Parameter   | Type | Required | Description |
|-------------|------|----------|-------------|
| `movie_url` | str  | Yes      | Fandango movie URL or path (e.g. `"/thunderbolts-2025-234498/movie-overview"`) |

## Example Queries

- "What movies are playing near 90210?"
- "Show me showtimes in Chicago, IL"
- "What's playing at AMC Empire 25 today?"
- "Tell me about the movie Thunderbolts"

## Requirements

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## License

MIT
