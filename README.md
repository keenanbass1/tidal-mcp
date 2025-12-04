# TIDAL MCP Server

A traditional MCP (Model Context Protocol) server for TIDAL music streaming service. Clean API wrapper following official MCP best practices - thin wrappers around tidalapi methods with no custom business logic.

## Features

### 27 Tools

| Category | Tool | Description |
|----------|------|-------------|
| **Auth** | `login` | OAuth browser authentication |
| **Search** | `search_tracks` | Find tracks by name/artist |
| | `search_albums` | Find albums |
| | `search_artists` | Find artists |
| | `search_playlists` | Find public playlists |
| **Favorites** | `get_favorite_tracks` | Get liked tracks |
| | `get_favorite_albums` | Get saved albums |
| | `get_favorite_artists` | Get followed artists |
| | `add_track_to_favorites` | Like a track |
| | `remove_track_from_favorites` | Unlike a track |
| | `remove_album_from_favorites` | Remove saved album |
| **Playlists** | `get_user_playlists` | List your playlists |
| | `get_playlist_tracks` | Get tracks from playlist |
| | `create_playlist` | Create new playlist |
| | `add_tracks_to_playlist` | Add tracks to playlist |
| | `remove_tracks_from_playlist` | Remove tracks from playlist |
| | `update_playlist` | Update name/description |
| | `delete_playlist` | Delete a playlist |
| **Albums** | `get_album_tracks` | Get all album tracks |
| | `get_album` | Get album details |
| | `get_similar_albums` | Find similar albums |
| **Artists** | `get_artist` | Get artist details with bio |
| | `get_artist_albums` | Get artist discography |
| | `get_artist_top_tracks` | Get popular tracks |
| | `get_similar_artists` | Find similar artists |
| **Recommendations** | `get_track_radio` | Similar tracks to seed |
| | `get_artist_radio` | Tracks based on artist style |

## Installation

### Requirements
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Setup

```bash
# Clone and enter directory
cd tidal-mcp

# Install with uv
uv sync

# Or with pip
pip install -e .
```

## Usage

### With Claude Desktop

Add to your Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tidal": {
      "command": "/path/to/uv",
      "args": [
        "--directory", "/path/to/tidal-mcp",
        "run", "tidal-mcp"
      ]
    }
  }
}
```

> **Note**: Use full path to `uv` (find with `which uv`)

### With MCP Inspector

```bash
npx @modelcontextprotocol/inspector uv run tidal-mcp
```

### Direct Usage

```bash
uv run tidal-mcp
```

## Authentication

```bash
python authenticate.py
```

## Example Workflows

### Create a Playlist from Search Results

1. `login` - Authenticate with TIDAL
2. `search_tracks("Radiohead Creep")` - Find tracks
3. `create_playlist("My Playlist", "A collection of favorites")` - Create playlist
4. `add_tracks_to_playlist(playlist_id, [track_ids...])` - Add tracks

### Browse and Add Album to Playlist

1. `search_albums("OK Computer")` - Find album
2. `get_album_tracks(album_id)` - Get all tracks
3. `add_tracks_to_playlist(playlist_id, [all_track_ids...])` - Add to playlist

### Manage Existing Playlist

1. `get_user_playlists()` - List your playlists
2. `get_playlist_tracks(playlist_id)` - View tracks
3. `remove_tracks_from_playlist(playlist_id, track_ids=[...])` - Remove tracks
4. `update_playlist(playlist_id, name="New Name")` - Rename

## Development

### Project Structure

```
tidal-mcp/
├── pyproject.toml           # Project configuration
├── README.md                 # This file
├── CLAUDE.md                # AI development guidance
└── src/
    └── tidal_mcp/
        ├── __init__.py      # Package init
        ├── models.py        # Pydantic response models
        └── server.py        # MCP server with 27 tools
```

### Dependencies

- `fastmcp>=2.12.0` - MCP protocol framework
- `tidalapi>=0.8.6` - TIDAL API client (v0.8.6+ required for working OAuth)
- `anyio>=4.0.0` - Async utilities

### Testing

```bash
# Test with MCP Inspector
npx @modelcontextprotocol/inspector uv run tidal-mcp

# Quick protocol test
echo '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0.0"}}, "id": 1}' | uv run tidal-mcp
```

## Troubleshooting

### Authentication Fails
- Ensure tidalapi >= 0.8.6 (older versions have invalid OAuth credentials)
- Delete `.tidal-sessions/` and re-authenticate

### Search Returns No Results
- Simplify query (single artist or song name)
- Check spelling

### Port Conflicts (Inspector)
```bash
pkill -f "inspector|tidal-mcp"
```

## Future Roadmap

The server currently has 27 tools covering core TIDAL functionality. Potential future additions:

- **Remote Server**: HTTP/SSE transport for Claude.ai and mobile apps (see `docs/REMOTE-DEPLOYMENT.md`)
- **Advanced Search**: ISRC/UPC lookup for precise track/album identification
- **Playback**: Queue management and now-playing info (requires TIDAL Connect)
- **Social**: Following users, collaborative playlists

## License

MIT

## Credits

Built with [FastMCP](https://github.com/jlowin/fastmcp) and [tidalapi](https://github.com/tamland/python-tidal).
