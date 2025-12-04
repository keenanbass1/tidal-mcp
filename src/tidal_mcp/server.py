#!/usr/bin/env python3
"""
TIDAL MCP Server - Traditional MCP server following official best practices.

A clean API wrapper exposing TIDAL functionality through the Model Context Protocol.
No custom business logic - thin wrappers around tidalapi methods.
"""

import json
import webbrowser
from pathlib import Path
from typing import List, Optional

import anyio
import tidalapi
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .models import (
    # Core entities
    Track,
    Album,
    Artist,
    Playlist,
    # List responses
    TrackList,
    AlbumList,
    ArtistList,
    PlaylistList,
    PlaylistTracks,
    AlbumTracks,
    # Detail responses
    ArtistDetails,
    AlbumDetails,
    RadioTracks,
    # Operation results
    AuthResult,
    CreatePlaylistResult,
    AddTracksResult,
    RemoveTracksResult,
    UpdatePlaylistResult,
    DeletePlaylistResult,
    AddToFavoritesResult,
    RemoveFromFavoritesResult,
)


# =============================================================================
# Server Configuration
# =============================================================================

SERVER_NAME = "TIDAL MCP"
SERVER_INSTRUCTIONS = """MCP server for TIDAL music streaming service.

A traditional MCP server that exposes TIDAL API functionality as clean tool wrappers.

## Authentication
- Use 'login' tool first to authenticate via OAuth browser flow
- Session is persisted and reused across restarts

## Search Tools
- search_tracks: Find tracks by name, artist, or combination
- search_albums: Find albums by name or artist
- search_artists: Find artists by name
- search_playlists: Find public playlists

## Favorites
- get_favorite_tracks: Get your liked tracks
- get_favorite_albums: Get your saved albums
- get_favorite_artists: Get your followed artists
- add_track_to_favorites: Like a track
- remove_track_from_favorites: Unlike a track
- remove_album_from_favorites: Remove a saved album

## Playlist Management
- get_user_playlists: List your playlists
- get_playlist_tracks: Get tracks from a playlist
- create_playlist: Create a new playlist
- add_tracks_to_playlist: Add tracks to a playlist
- remove_tracks_from_playlist: Remove tracks from a playlist
- update_playlist: Update playlist name/description
- delete_playlist: Delete a playlist

## Content Browsing
- get_album_tracks: Get all tracks from an album
- get_album: Get detailed album information
- get_similar_albums: Find albums similar to a given album

## Artist Discovery
- get_artist: Get artist details with biography
- get_artist_albums: Get an artist's discography
- get_artist_top_tracks: Get an artist's most popular tracks
- get_similar_artists: Find artists similar to a given artist

## Recommendations
- get_track_radio: Get tracks similar to a seed track
- get_artist_radio: Get tracks based on an artist's style
"""

# Initialize MCP server
mcp = FastMCP(
    name=SERVER_NAME,
    instructions=SERVER_INSTRUCTIONS,
)

# Session management
PROJECT_ROOT = Path(__file__).parent.parent.parent
SESSION_DIR = PROJECT_ROOT / ".tidal-sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)
SESSION_FILE = SESSION_DIR / "session.json"

# Global session instance (single-user design)
session = tidalapi.Session()


# =============================================================================
# Authentication Helpers
# =============================================================================

async def ensure_authenticated() -> bool:
    """
    Check if user is authenticated with TIDAL.
    Automatically loads persisted session if available.
    """
    if await anyio.Path(SESSION_FILE).exists():
        try:
            async with await anyio.open_file(SESSION_FILE, "r") as f:
                content = await f.read()
                data = json.loads(content)

            # Load OAuth session
            result = await anyio.to_thread.run_sync(
                session.load_oauth_session,
                data["token_type"]["data"],
                data["access_token"]["data"],
                data["refresh_token"]["data"],
                None,  # expiry time
            )

            if result:
                is_valid = await anyio.to_thread.run_sync(session.check_login)
                if not is_valid:
                    await anyio.Path(SESSION_FILE).unlink()
                return is_valid
            return False
        except Exception:
            await anyio.Path(SESSION_FILE).unlink()
            return False

    return await anyio.to_thread.run_sync(session.check_login)


# =============================================================================
# Tool 1: Authentication
# =============================================================================

@mcp.tool(
    annotations={
        "title": "Authenticate with TIDAL",
        "readOnlyHint": False,
        "openWorldHint": True,
        "idempotentHint": False,
    }
)
async def login() -> AuthResult:
    """
    Authenticate with TIDAL using OAuth browser flow.
    Opens browser automatically for secure login.
    Session is persisted for future use.
    """
    if await ensure_authenticated():
        return AuthResult(
            status="success",
            message="Already authenticated with TIDAL",
            authenticated=True,
        )

    try:
        # Start OAuth device code flow
        login_obj, future = await anyio.to_thread.run_sync(session.login_oauth)

        auth_url = login_obj.verification_uri_complete
        if not auth_url.startswith("http"):
            auth_url = "https://" + auth_url

        # Try to open browser automatically
        try:
            await anyio.to_thread.run_sync(webbrowser.open, auth_url)
        except Exception:
            pass

        # Wait for user to complete authentication (polls TIDAL's server)
        # This blocks until auth completes or the link expires (~5 minutes)
        await anyio.to_thread.run_sync(future.result)

        # Check if login succeeded
        if await anyio.to_thread.run_sync(session.check_login):
            # Save session for future use
            session_data = {
                "token_type": {"data": session.token_type or "Bearer"},
                "session_id": {"data": session.session_id or ""},
                "access_token": {"data": session.access_token},
                "refresh_token": {"data": session.refresh_token},
                "is_pkce": {"data": session.is_pkce},
            }
            async with await anyio.open_file(SESSION_FILE, "w") as f:
                await f.write(json.dumps(session_data))

            return AuthResult(
                status="success",
                message="Successfully authenticated with TIDAL",
                authenticated=True,
            )
        else:
            raise ToolError("Authentication failed - please try again")
    except ToolError:
        raise
    except Exception as e:
        error_msg = str(e)
        if "too long" in error_msg.lower() or "timeout" in error_msg.lower():
            raise ToolError(
                f"Authentication timed out. Please authenticate using the helper script:\n\n"
                f"  cd /home/ubuntu/code/personal/tidal/tidal-mcp && uv run python authenticate.py\n\n"
                f"After authenticating, all MCP tools will work automatically."
            )
        raise ToolError(f"Authentication error: {error_msg}")


# =============================================================================
# Tools 2-5: Search
# =============================================================================

@mcp.tool()
async def search_tracks(query: str, limit: int = 10) -> TrackList:
    """
    Search for tracks on TIDAL.

    Args:
        query: Search query - artist name, song title, or combination
        limit: Maximum results (1-50, default: 10)

    Returns:
        List of matching tracks with id, title, artist, album, duration, and URL
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        limit = min(max(1, limit), 50)
        results = await anyio.to_thread.run_sync(
            lambda: session.search(query, models=[tidalapi.Track], limit=limit)
        )

        tracks = []
        for track in results.get("tracks", []):
            tracks.append(
                Track(
                    id=str(track.id),
                    title=track.name,
                    artist=track.artist.name if track.artist else "Unknown Artist",
                    album=track.album.name if track.album else "Unknown Album",
                    duration_seconds=track.duration,
                    url=f"https://tidal.com/browse/track/{track.id}",
                )
            )

        return TrackList(status="success", query=query, count=len(tracks), tracks=tracks)
    except Exception as e:
        raise ToolError(f"Track search failed: {str(e)}")


@mcp.tool()
async def search_albums(query: str, limit: int = 10) -> AlbumList:
    """
    Search for albums on TIDAL.

    Args:
        query: Search query - album name, artist name, or combination
        limit: Maximum results (1-50, default: 10)

    Returns:
        List of matching albums with id, title, artist, release date, track count, and URL
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        limit = min(max(1, limit), 50)
        results = await anyio.to_thread.run_sync(
            lambda: session.search(query, models=[tidalapi.Album], limit=limit)
        )

        albums = []
        for album in results.get("albums", []):
            release_date = None
            if hasattr(album, "release_date") and album.release_date:
                release_date = str(album.release_date)

            albums.append(
                Album(
                    id=str(album.id),
                    title=album.name,
                    artist=album.artist.name if album.artist else "Unknown Artist",
                    release_date=release_date,
                    num_tracks=getattr(album, "num_tracks", 0),
                    duration_seconds=getattr(album, "duration", 0),
                    url=f"https://tidal.com/browse/album/{album.id}",
                )
            )

        return AlbumList(status="success", query=query, count=len(albums), albums=albums)
    except Exception as e:
        raise ToolError(f"Album search failed: {str(e)}")


@mcp.tool()
async def search_artists(query: str, limit: int = 10) -> ArtistList:
    """
    Search for artists on TIDAL.

    Args:
        query: Search query - artist name
        limit: Maximum results (1-50, default: 10)

    Returns:
        List of matching artists with id, name, and URL
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        limit = min(max(1, limit), 50)
        results = await anyio.to_thread.run_sync(
            lambda: session.search(query, models=[tidalapi.Artist], limit=limit)
        )

        artists = []
        for artist in results.get("artists", []):
            artists.append(
                Artist(
                    id=str(artist.id),
                    name=artist.name,
                    url=f"https://tidal.com/browse/artist/{artist.id}",
                )
            )

        return ArtistList(status="success", query=query, count=len(artists), artists=artists)
    except Exception as e:
        raise ToolError(f"Artist search failed: {str(e)}")


@mcp.tool()
async def search_playlists(query: str, limit: int = 10) -> PlaylistList:
    """
    Search for public playlists on TIDAL.

    Args:
        query: Search query - playlist name or theme
        limit: Maximum results (1-50, default: 10)

    Returns:
        List of matching playlists with id, name, description, track count, and URL
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        limit = min(max(1, limit), 50)
        results = await anyio.to_thread.run_sync(
            lambda: session.search(query, models=[tidalapi.Playlist], limit=limit)
        )

        playlists = []
        for playlist in results.get("playlists", []):
            creator_name = None
            if hasattr(playlist, "creator") and playlist.creator:
                creator_name = getattr(playlist.creator, "name", None)

            playlists.append(
                Playlist(
                    id=str(playlist.id),
                    name=playlist.name,
                    description=getattr(playlist, "description", "") or "",
                    track_count=getattr(playlist, "num_tracks", 0),
                    creator=creator_name,
                    url=f"https://tidal.com/browse/playlist/{playlist.id}",
                )
            )

        return PlaylistList(status="success", query=query, count=len(playlists), playlists=playlists)
    except Exception as e:
        raise ToolError(f"Playlist search failed: {str(e)}")


# =============================================================================
# Tools 6-7: Favorites
# =============================================================================

@mcp.tool()
async def get_favorite_tracks(limit: int = 50) -> TrackList:
    """
    Get user's favorite (liked) tracks from TIDAL.

    Args:
        limit: Maximum tracks to retrieve (default: 50)

    Returns:
        List of favorite tracks
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        favorites = await anyio.to_thread.run_sync(
            lambda: session.user.favorites.tracks(limit=limit)
        )

        tracks = []
        for track in favorites:
            tracks.append(
                Track(
                    id=str(track.id),
                    title=track.name,
                    artist=track.artist.name if track.artist else "Unknown Artist",
                    album=track.album.name if track.album else "Unknown Album",
                    duration_seconds=track.duration,
                    url=f"https://tidal.com/browse/track/{track.id}",
                )
            )

        return TrackList(status="success", count=len(tracks), tracks=tracks)
    except Exception as e:
        raise ToolError(f"Failed to get favorites: {str(e)}")


@mcp.tool()
async def add_track_to_favorites(track_id: str) -> AddToFavoritesResult:
    """
    Add a track to user's favorites (like a track).

    Args:
        track_id: ID of the track to add to favorites

    Returns:
        Success status and confirmation
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        track_id_int = int(track_id)
        await anyio.to_thread.run_sync(
            session.user.favorites.add_track, track_id_int
        )

        return AddToFavoritesResult(
            status="success",
            item_id=track_id,
            item_type="track",
            message=f"Track {track_id} added to favorites",
        )
    except ValueError:
        raise ToolError(f"Invalid track ID format: {track_id}")
    except Exception as e:
        raise ToolError(f"Failed to add track to favorites: {str(e)}")


# =============================================================================
# Tools 8-14: Playlist Management
# =============================================================================

@mcp.tool()
async def get_user_playlists(limit: int = 50) -> PlaylistList:
    """
    Get list of user's own playlists from TIDAL.

    Args:
        limit: Maximum playlists to return (default: 50)

    Returns:
        List of user's playlists
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        all_playlists = await anyio.to_thread.run_sync(session.user.playlists)
        limited_playlists = all_playlists[:limit] if limit else all_playlists

        playlists = []
        for playlist in limited_playlists:
            playlists.append(
                Playlist(
                    id=str(playlist.id),
                    name=playlist.name,
                    description=getattr(playlist, "description", "") or "",
                    track_count=getattr(playlist, "num_tracks", 0),
                    creator=None,  # User's own playlists
                    url=f"https://tidal.com/browse/playlist/{playlist.id}",
                )
            )

        return PlaylistList(status="success", count=len(playlists), playlists=playlists)
    except Exception as e:
        raise ToolError(f"Failed to get playlists: {str(e)}")


@mcp.tool()
async def get_playlist_tracks(playlist_id: str, limit: int = 100) -> PlaylistTracks:
    """
    Get tracks from a specific playlist.

    Args:
        playlist_id: ID of the playlist
        limit: Maximum tracks to return (default: 100)

    Returns:
        List of tracks in the playlist
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        playlist = await anyio.to_thread.run_sync(session.playlist, playlist_id)
        if not playlist:
            raise ToolError(f"Playlist with ID '{playlist_id}' not found")

        all_tracks = await anyio.to_thread.run_sync(playlist.tracks)
        limited_tracks = all_tracks[:limit] if limit else all_tracks

        tracks = []
        for track in limited_tracks:
            tracks.append(
                Track(
                    id=str(track.id),
                    title=track.name,
                    artist=track.artist.name if track.artist else "Unknown Artist",
                    album=track.album.name if track.album else "Unknown Album",
                    duration_seconds=track.duration,
                    url=f"https://tidal.com/browse/track/{track.id}",
                )
            )

        return PlaylistTracks(
            status="success",
            playlist_name=playlist.name,
            playlist_id=playlist_id,
            count=len(tracks),
            tracks=tracks,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to get playlist tracks: {str(e)}")


@mcp.tool()
async def create_playlist(name: str, description: str = "") -> CreatePlaylistResult:
    """
    Create a new playlist in user's TIDAL account.

    Args:
        name: Name for the playlist
        description: Optional description

    Returns:
        Created playlist details including ID and URL
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        playlist = await anyio.to_thread.run_sync(
            session.user.create_playlist, name, description
        )

        return CreatePlaylistResult(
            status="success",
            playlist=Playlist(
                id=str(playlist.id),
                name=playlist.name,
                description=playlist.description or "",
                track_count=0,
                creator=None,
                url=f"https://tidal.com/browse/playlist/{playlist.id}",
            ),
            message=f"Created playlist '{name}'",
        )
    except Exception as e:
        raise ToolError(f"Failed to create playlist: {str(e)}")


@mcp.tool()
async def add_tracks_to_playlist(playlist_id: str, track_ids: List[str]) -> AddTracksResult:
    """
    Add tracks to an existing playlist.

    Args:
        playlist_id: ID of the playlist
        track_ids: List of track IDs to add

    Returns:
        Success status and number of tracks added
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        playlist = await anyio.to_thread.run_sync(session.playlist, playlist_id)
        if not playlist:
            raise ToolError(f"Playlist with ID '{playlist_id}' not found")

        track_ids_int = [int(tid) for tid in track_ids]
        await anyio.to_thread.run_sync(playlist.add, track_ids_int)

        return AddTracksResult(
            status="success",
            playlist_id=playlist_id,
            playlist_name=playlist.name,
            tracks_added=len(track_ids),
            playlist_url=f"https://tidal.com/browse/playlist/{playlist_id}",
            message=f"Added {len(track_ids)} tracks to playlist '{playlist.name}'",
        )
    except ValueError as e:
        raise ToolError(f"Invalid track ID format: {str(e)}")
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to add tracks: {str(e)}")


@mcp.tool()
async def remove_tracks_from_playlist(
    playlist_id: str, track_ids: Optional[List[str]] = None, indices: Optional[List[int]] = None
) -> RemoveTracksResult:
    """
    Remove tracks from a playlist by track ID or position index.

    Args:
        playlist_id: ID of the playlist
        track_ids: List of track IDs to remove (optional)
        indices: List of position indices to remove, 0-based (optional)
        Note: Provide either track_ids OR indices, not both

    Returns:
        Success status and number of tracks removed
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    if not track_ids and not indices:
        raise ToolError("Must provide either track_ids or indices to remove")

    if track_ids and indices:
        raise ToolError("Provide either track_ids or indices, not both")

    try:
        playlist = await anyio.to_thread.run_sync(session.playlist, playlist_id)
        if not playlist:
            raise ToolError(f"Playlist with ID '{playlist_id}' not found")

        if indices:
            # Remove by index position
            await anyio.to_thread.run_sync(playlist.remove_by_indices, indices)
            removed_count = len(indices)
        else:
            # Remove by track ID
            track_ids_int = [int(tid) for tid in track_ids]
            await anyio.to_thread.run_sync(playlist.remove_by_id, track_ids_int)
            removed_count = len(track_ids)

        return RemoveTracksResult(
            status="success",
            playlist_id=playlist_id,
            playlist_name=playlist.name,
            tracks_removed=removed_count,
            message=f"Removed {removed_count} tracks from playlist '{playlist.name}'",
        )
    except ValueError as e:
        raise ToolError(f"Invalid ID format: {str(e)}")
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to remove tracks: {str(e)}")


@mcp.tool()
async def update_playlist(
    playlist_id: str, name: Optional[str] = None, description: Optional[str] = None
) -> UpdatePlaylistResult:
    """
    Update a playlist's name and/or description.

    Args:
        playlist_id: ID of the playlist to update
        name: New name for the playlist (optional)
        description: New description (optional)

    Returns:
        Updated playlist details
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    if not name and description is None:
        raise ToolError("Must provide at least name or description to update")

    try:
        playlist = await anyio.to_thread.run_sync(session.playlist, playlist_id)
        if not playlist:
            raise ToolError(f"Playlist with ID '{playlist_id}' not found")

        # Update the playlist
        if name:
            await anyio.to_thread.run_sync(playlist.edit, name, description)
        elif description is not None:
            await anyio.to_thread.run_sync(playlist.edit, playlist.name, description)

        # Fetch updated playlist
        updated_playlist = await anyio.to_thread.run_sync(session.playlist, playlist_id)

        return UpdatePlaylistResult(
            status="success",
            playlist=Playlist(
                id=str(updated_playlist.id),
                name=updated_playlist.name,
                description=updated_playlist.description or "",
                track_count=getattr(updated_playlist, "num_tracks", 0),
                creator=None,
                url=f"https://tidal.com/browse/playlist/{playlist_id}",
            ),
            message=f"Updated playlist '{updated_playlist.name}'",
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to update playlist: {str(e)}")


@mcp.tool()
async def delete_playlist(playlist_id: str) -> DeletePlaylistResult:
    """
    Delete a playlist from user's account.

    Args:
        playlist_id: ID of the playlist to delete

    Returns:
        Confirmation of deletion
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        playlist = await anyio.to_thread.run_sync(session.playlist, playlist_id)
        if not playlist:
            raise ToolError(f"Playlist with ID '{playlist_id}' not found")

        playlist_name = playlist.name
        await anyio.to_thread.run_sync(playlist.delete)

        return DeletePlaylistResult(
            status="success",
            playlist_id=playlist_id,
            message=f"Deleted playlist '{playlist_name}'",
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to delete playlist: {str(e)}")


# =============================================================================
# Tool 15: Content Browsing
# =============================================================================

@mcp.tool()
async def get_album_tracks(album_id: str) -> AlbumTracks:
    """
    Get all tracks from a specific album.

    Args:
        album_id: ID of the album

    Returns:
        List of tracks in the album with album metadata
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        album = await anyio.to_thread.run_sync(session.album, album_id)
        if not album:
            raise ToolError(f"Album with ID '{album_id}' not found")

        album_tracks = await anyio.to_thread.run_sync(album.tracks)

        tracks = []
        for track in album_tracks:
            tracks.append(
                Track(
                    id=str(track.id),
                    title=track.name,
                    artist=track.artist.name if track.artist else "Unknown Artist",
                    album=album.name,
                    duration_seconds=track.duration,
                    url=f"https://tidal.com/browse/track/{track.id}",
                )
            )

        return AlbumTracks(
            status="success",
            album_title=album.name,
            album_id=album_id,
            artist=album.artist.name if album.artist else "Unknown Artist",
            count=len(tracks),
            tracks=tracks,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to get album tracks: {str(e)}")


# =============================================================================
# Tools 16-17: Recommendations
# =============================================================================

@mcp.tool()
async def get_track_radio(track_id: str, limit: int = 20) -> RadioTracks:
    """
    Get tracks similar to a seed track (track radio).

    This returns TIDAL's native recommendations based on the specified track,
    useful for music discovery and creating "similar music" playlists.

    Args:
        track_id: ID of the seed track
        limit: Maximum tracks to return (default: 20, max: 100)

    Returns:
        List of similar tracks with seed track info
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        limit = min(max(1, limit), 100)

        # Get the seed track first
        track = await anyio.to_thread.run_sync(session.track, track_id)
        if not track:
            raise ToolError(f"Track with ID '{track_id}' not found")

        seed_name = f"{track.name} by {track.artist.name if track.artist else 'Unknown Artist'}"

        # Get radio tracks
        radio_tracks = await anyio.to_thread.run_sync(
            lambda: track.get_track_radio(limit=limit)
        )

        tracks = []
        for t in radio_tracks:
            tracks.append(
                Track(
                    id=str(t.id),
                    title=t.name,
                    artist=t.artist.name if t.artist else "Unknown Artist",
                    album=t.album.name if t.album else "Unknown Album",
                    duration_seconds=t.duration,
                    url=f"https://tidal.com/browse/track/{t.id}",
                )
            )

        return RadioTracks(
            status="success",
            seed_id=track_id,
            seed_type="track",
            seed_name=seed_name,
            count=len(tracks),
            tracks=tracks,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to get track radio: {str(e)}")


@mcp.tool()
async def get_artist_radio(artist_id: str, limit: int = 20) -> RadioTracks:
    """
    Get tracks similar to an artist's style (artist radio).

    This returns TIDAL's native recommendations based on the specified artist,
    useful for discovering music in a similar style.

    Args:
        artist_id: ID of the seed artist
        limit: Maximum tracks to return (default: 20, max: 100)

    Returns:
        List of similar tracks with seed artist info
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        limit = min(max(1, limit), 100)

        # Get the seed artist first
        artist = await anyio.to_thread.run_sync(session.artist, artist_id)
        if not artist:
            raise ToolError(f"Artist with ID '{artist_id}' not found")

        # Get radio tracks
        radio_tracks = await anyio.to_thread.run_sync(
            lambda: artist.get_radio(limit=limit)
        )

        tracks = []
        for t in radio_tracks:
            tracks.append(
                Track(
                    id=str(t.id),
                    title=t.name,
                    artist=t.artist.name if t.artist else "Unknown Artist",
                    album=t.album.name if t.album else "Unknown Album",
                    duration_seconds=t.duration,
                    url=f"https://tidal.com/browse/track/{t.id}",
                )
            )

        return RadioTracks(
            status="success",
            seed_id=artist_id,
            seed_type="artist",
            seed_name=artist.name,
            count=len(tracks),
            tracks=tracks,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to get artist radio: {str(e)}")


# =============================================================================
# Tools 18-21: Artist Discovery
# =============================================================================

@mcp.tool()
async def get_artist(artist_id: str) -> ArtistDetails:
    """
    Get detailed information about an artist including biography.

    Args:
        artist_id: ID of the artist

    Returns:
        Artist details including name, URL, and biography
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        artist = await anyio.to_thread.run_sync(session.artist, artist_id)
        if not artist:
            raise ToolError(f"Artist with ID '{artist_id}' not found")

        # Try to get biography
        bio = None
        try:
            bio = await anyio.to_thread.run_sync(artist.get_bio)
        except Exception:
            pass  # Bio may not be available for all artists

        return ArtistDetails(
            status="success",
            artist=Artist(
                id=str(artist.id),
                name=artist.name,
                url=f"https://tidal.com/browse/artist/{artist.id}",
            ),
            bio=bio,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to get artist: {str(e)}")


@mcp.tool()
async def get_artist_albums(artist_id: str, limit: int = 20) -> AlbumList:
    """
    Get albums by an artist (discography).

    Args:
        artist_id: ID of the artist
        limit: Maximum albums to return (default: 20, max: 50)

    Returns:
        List of albums by the artist
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        limit = min(max(1, limit), 50)

        artist = await anyio.to_thread.run_sync(session.artist, artist_id)
        if not artist:
            raise ToolError(f"Artist with ID '{artist_id}' not found")

        artist_albums = await anyio.to_thread.run_sync(
            lambda: artist.get_albums(limit=limit)
        )

        albums = []
        for album in artist_albums:
            release_date = None
            if hasattr(album, "release_date") and album.release_date:
                release_date = str(album.release_date)

            albums.append(
                Album(
                    id=str(album.id),
                    title=album.name,
                    artist=album.artist.name if album.artist else artist.name,
                    release_date=release_date,
                    num_tracks=getattr(album, "num_tracks", 0),
                    duration_seconds=getattr(album, "duration", 0),
                    url=f"https://tidal.com/browse/album/{album.id}",
                )
            )

        return AlbumList(
            status="success",
            count=len(albums),
            albums=albums,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to get artist albums: {str(e)}")


@mcp.tool()
async def get_artist_top_tracks(artist_id: str, limit: int = 10) -> TrackList:
    """
    Get an artist's most popular tracks.

    Args:
        artist_id: ID of the artist
        limit: Maximum tracks to return (default: 10, max: 50)

    Returns:
        List of the artist's top tracks
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        limit = min(max(1, limit), 50)

        artist = await anyio.to_thread.run_sync(session.artist, artist_id)
        if not artist:
            raise ToolError(f"Artist with ID '{artist_id}' not found")

        top_tracks = await anyio.to_thread.run_sync(
            lambda: artist.get_top_tracks(limit=limit)
        )

        tracks = []
        for track in top_tracks:
            tracks.append(
                Track(
                    id=str(track.id),
                    title=track.name,
                    artist=track.artist.name if track.artist else artist.name,
                    album=track.album.name if track.album else "Unknown Album",
                    duration_seconds=track.duration,
                    url=f"https://tidal.com/browse/track/{track.id}",
                )
            )

        return TrackList(
            status="success",
            count=len(tracks),
            tracks=tracks,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to get artist top tracks: {str(e)}")


@mcp.tool()
async def get_similar_artists(artist_id: str, limit: int = 10) -> ArtistList:
    """
    Get artists similar to the specified artist.

    Args:
        artist_id: ID of the seed artist
        limit: Maximum artists to return (default: 10, max: 50)

    Returns:
        List of similar artists
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        limit = min(max(1, limit), 50)

        artist = await anyio.to_thread.run_sync(session.artist, artist_id)
        if not artist:
            raise ToolError(f"Artist with ID '{artist_id}' not found")

        similar = await anyio.to_thread.run_sync(artist.get_similar)
        limited_similar = similar[:limit] if similar else []

        artists = []
        for a in limited_similar:
            artists.append(
                Artist(
                    id=str(a.id),
                    name=a.name,
                    url=f"https://tidal.com/browse/artist/{a.id}",
                )
            )

        return ArtistList(
            status="success",
            count=len(artists),
            artists=artists,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to get similar artists: {str(e)}")


# =============================================================================
# Tools 22-25: Extended Favorites
# =============================================================================

@mcp.tool()
async def get_favorite_albums(limit: int = 50) -> AlbumList:
    """
    Get user's favorite (saved) albums from TIDAL.

    Args:
        limit: Maximum albums to retrieve (default: 50)

    Returns:
        List of favorite albums
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        favorites = await anyio.to_thread.run_sync(
            lambda: session.user.favorites.albums(limit=limit)
        )

        albums = []
        for album in favorites:
            release_date = None
            if hasattr(album, "release_date") and album.release_date:
                release_date = str(album.release_date)

            albums.append(
                Album(
                    id=str(album.id),
                    title=album.name,
                    artist=album.artist.name if album.artist else "Unknown Artist",
                    release_date=release_date,
                    num_tracks=getattr(album, "num_tracks", 0),
                    duration_seconds=getattr(album, "duration", 0),
                    url=f"https://tidal.com/browse/album/{album.id}",
                )
            )

        return AlbumList(status="success", count=len(albums), albums=albums)
    except Exception as e:
        raise ToolError(f"Failed to get favorite albums: {str(e)}")


@mcp.tool()
async def get_favorite_artists(limit: int = 50) -> ArtistList:
    """
    Get user's favorite (followed) artists from TIDAL.

    Args:
        limit: Maximum artists to retrieve (default: 50)

    Returns:
        List of followed artists
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        favorites = await anyio.to_thread.run_sync(
            lambda: session.user.favorites.artists(limit=limit)
        )

        artists = []
        for artist in favorites:
            artists.append(
                Artist(
                    id=str(artist.id),
                    name=artist.name,
                    url=f"https://tidal.com/browse/artist/{artist.id}",
                )
            )

        return ArtistList(status="success", count=len(artists), artists=artists)
    except Exception as e:
        raise ToolError(f"Failed to get favorite artists: {str(e)}")


@mcp.tool()
async def remove_track_from_favorites(track_id: str) -> RemoveFromFavoritesResult:
    """
    Remove a track from user's favorites (unlike a track).

    Args:
        track_id: ID of the track to remove from favorites

    Returns:
        Success status and confirmation
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        track_id_int = int(track_id)
        await anyio.to_thread.run_sync(
            session.user.favorites.remove_track, track_id_int
        )

        return RemoveFromFavoritesResult(
            status="success",
            item_id=track_id,
            item_type="track",
            message=f"Track {track_id} removed from favorites",
        )
    except ValueError:
        raise ToolError(f"Invalid track ID format: {track_id}")
    except Exception as e:
        raise ToolError(f"Failed to remove track from favorites: {str(e)}")


@mcp.tool()
async def remove_album_from_favorites(album_id: str) -> RemoveFromFavoritesResult:
    """
    Remove an album from user's favorites.

    Args:
        album_id: ID of the album to remove from favorites

    Returns:
        Success status and confirmation
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        album_id_int = int(album_id)
        await anyio.to_thread.run_sync(
            session.user.favorites.remove_album, album_id_int
        )

        return RemoveFromFavoritesResult(
            status="success",
            item_id=album_id,
            item_type="album",
            message=f"Album {album_id} removed from favorites",
        )
    except ValueError:
        raise ToolError(f"Invalid album ID format: {album_id}")
    except Exception as e:
        raise ToolError(f"Failed to remove album from favorites: {str(e)}")


# =============================================================================
# Tools 26-27: Album Details
# =============================================================================

@mcp.tool()
async def get_album(album_id: str) -> AlbumDetails:
    """
    Get detailed information about an album.

    Args:
        album_id: ID of the album

    Returns:
        Album details including title, artist, release date, and track count
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        album = await anyio.to_thread.run_sync(session.album, album_id)
        if not album:
            raise ToolError(f"Album with ID '{album_id}' not found")

        release_date = None
        if hasattr(album, "release_date") and album.release_date:
            release_date = str(album.release_date)

        return AlbumDetails(
            status="success",
            album=Album(
                id=str(album.id),
                title=album.name,
                artist=album.artist.name if album.artist else "Unknown Artist",
                release_date=release_date,
                num_tracks=getattr(album, "num_tracks", 0),
                duration_seconds=getattr(album, "duration", 0),
                url=f"https://tidal.com/browse/album/{album.id}",
            ),
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to get album: {str(e)}")


@mcp.tool()
async def get_similar_albums(album_id: str, limit: int = 10) -> AlbumList:
    """
    Get albums similar to the specified album.

    Args:
        album_id: ID of the seed album
        limit: Maximum albums to return (default: 10, max: 50)

    Returns:
        List of similar albums
    """
    if not await ensure_authenticated():
        raise ToolError("Not authenticated. Please run the 'login' tool first.")

    try:
        limit = min(max(1, limit), 50)

        album = await anyio.to_thread.run_sync(session.album, album_id)
        if not album:
            raise ToolError(f"Album with ID '{album_id}' not found")

        similar = await anyio.to_thread.run_sync(album.similar)
        limited_similar = similar[:limit] if similar else []

        albums = []
        for a in limited_similar:
            release_date = None
            if hasattr(a, "release_date") and a.release_date:
                release_date = str(a.release_date)

            albums.append(
                Album(
                    id=str(a.id),
                    title=a.name,
                    artist=a.artist.name if a.artist else "Unknown Artist",
                    release_date=release_date,
                    num_tracks=getattr(a, "num_tracks", 0),
                    duration_seconds=getattr(a, "duration", 0),
                    url=f"https://tidal.com/browse/album/{a.id}",
                )
            )

        return AlbumList(
            status="success",
            count=len(albums),
            albums=albums,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to get similar albums: {str(e)}")


# =============================================================================
# Server Entry Point
# =============================================================================

def run_server() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    run_server()
