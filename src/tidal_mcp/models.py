"""
Pydantic models for TIDAL MCP Server structured output schemas.

These models provide type-safe, well-documented structures for all tool responses.
Following MCP best practices: minimal transformation, clear descriptions.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Core Entity Models
# =============================================================================

class Track(BaseModel):
    """Structured representation of a TIDAL track."""

    id: str = Field(description="Unique TIDAL track ID")
    title: str = Field(description="Track title")
    artist: str = Field(description="Primary artist name")
    album: str = Field(description="Album name")
    duration_seconds: int = Field(description="Track duration in seconds")
    url: str = Field(description="TIDAL web URL for the track")


class Album(BaseModel):
    """Structured representation of a TIDAL album."""

    id: str = Field(description="Unique TIDAL album ID")
    title: str = Field(description="Album title")
    artist: str = Field(description="Primary artist name")
    release_date: Optional[str] = Field(None, description="Release date (YYYY-MM-DD)")
    num_tracks: int = Field(description="Number of tracks in album")
    duration_seconds: int = Field(description="Total album duration in seconds")
    url: str = Field(description="TIDAL web URL for the album")


class Artist(BaseModel):
    """Structured representation of a TIDAL artist."""

    id: str = Field(description="Unique TIDAL artist ID")
    name: str = Field(description="Artist name")
    url: str = Field(description="TIDAL web URL for the artist")


class Playlist(BaseModel):
    """Structured representation of a TIDAL playlist."""

    id: str = Field(description="Unique playlist ID (UUID)")
    name: str = Field(description="Playlist name")
    description: str = Field(description="Playlist description")
    track_count: int = Field(description="Number of tracks in playlist")
    creator: Optional[str] = Field(None, description="Playlist creator name")
    url: str = Field(description="TIDAL web URL for the playlist")


# =============================================================================
# List Response Models
# =============================================================================

class TrackList(BaseModel):
    """List of tracks with metadata."""

    status: str = Field(description="Operation status (success/error)")
    query: Optional[str] = Field(None, description="Search query used (for search results)")
    count: int = Field(description="Number of tracks returned")
    tracks: List[Track] = Field(description="List of track objects")


class AlbumList(BaseModel):
    """List of albums with metadata."""

    status: str = Field(description="Operation status (success/error)")
    query: Optional[str] = Field(None, description="Search query used (for search results)")
    count: int = Field(description="Number of albums returned")
    albums: List[Album] = Field(description="List of album objects")


class ArtistList(BaseModel):
    """List of artists with metadata."""

    status: str = Field(description="Operation status (success/error)")
    query: Optional[str] = Field(None, description="Search query used (for search results)")
    count: int = Field(description="Number of artists returned")
    artists: List[Artist] = Field(description="List of artist objects")


class PlaylistList(BaseModel):
    """List of playlists with metadata."""

    status: str = Field(description="Operation status (success/error)")
    query: Optional[str] = Field(None, description="Search query used (for search results)")
    count: int = Field(description="Number of playlists returned")
    playlists: List[Playlist] = Field(description="List of playlist objects")


class PlaylistTracks(BaseModel):
    """Tracks from a specific playlist."""

    status: str = Field(description="Operation status (success/error)")
    playlist_name: str = Field(description="Name of the playlist")
    playlist_id: str = Field(description="ID of the playlist")
    count: int = Field(description="Number of tracks returned")
    tracks: List[Track] = Field(description="List of track objects")


class AlbumTracks(BaseModel):
    """Tracks from a specific album."""

    status: str = Field(description="Operation status (success/error)")
    album_title: str = Field(description="Title of the album")
    album_id: str = Field(description="ID of the album")
    artist: str = Field(description="Album artist name")
    count: int = Field(description="Number of tracks returned")
    tracks: List[Track] = Field(description="List of track objects")


# =============================================================================
# Operation Result Models
# =============================================================================

class AuthResult(BaseModel):
    """Result of authentication attempt."""

    status: str = Field(description="Operation status (success/error)")
    message: str = Field(description="Status message")
    authenticated: bool = Field(description="Whether authentication was successful")


class CreatePlaylistResult(BaseModel):
    """Result of creating a new playlist."""

    status: str = Field(description="Operation status (success/error)")
    playlist: Optional[Playlist] = Field(None, description="Created playlist details")
    message: str = Field(description="Status message")


class AddTracksResult(BaseModel):
    """Result of adding tracks to a playlist."""

    status: str = Field(description="Operation status (success/error)")
    playlist_id: str = Field(description="ID of the playlist")
    playlist_name: str = Field(description="Name of the playlist")
    tracks_added: int = Field(description="Number of tracks successfully added")
    playlist_url: str = Field(description="TIDAL web URL for the playlist")
    message: str = Field(description="Status message")


class RemoveTracksResult(BaseModel):
    """Result of removing tracks from a playlist."""

    status: str = Field(description="Operation status (success/error)")
    playlist_id: str = Field(description="ID of the playlist")
    playlist_name: str = Field(description="Name of the playlist")
    tracks_removed: int = Field(description="Number of tracks successfully removed")
    message: str = Field(description="Status message")


class UpdatePlaylistResult(BaseModel):
    """Result of updating a playlist."""

    status: str = Field(description="Operation status (success/error)")
    playlist: Optional[Playlist] = Field(None, description="Updated playlist details")
    message: str = Field(description="Status message")


class DeletePlaylistResult(BaseModel):
    """Result of deleting a playlist."""

    status: str = Field(description="Operation status (success/error)")
    playlist_id: str = Field(description="ID of the deleted playlist")
    message: str = Field(description="Status message")


class AddToFavoritesResult(BaseModel):
    """Result of adding an item to favorites."""

    status: str = Field(description="Operation status (success/error)")
    item_id: str = Field(description="ID of the item added to favorites")
    item_type: str = Field(description="Type of item (track/album/artist)")
    message: str = Field(description="Status message")


class RemoveFromFavoritesResult(BaseModel):
    """Result of removing an item from favorites."""

    status: str = Field(description="Operation status (success/error)")
    item_id: str = Field(description="ID of the item removed from favorites")
    item_type: str = Field(description="Type of item (track/album/artist)")
    message: str = Field(description="Status message")


class ArtistDetails(BaseModel):
    """Detailed artist information including biography."""

    status: str = Field(description="Operation status (success/error)")
    artist: Artist = Field(description="Artist basic information")
    bio: Optional[str] = Field(None, description="Artist biography text")


class AlbumDetails(BaseModel):
    """Detailed album information."""

    status: str = Field(description="Operation status (success/error)")
    album: Album = Field(description="Album information")


class RadioTracks(BaseModel):
    """Radio/recommendation tracks based on a seed track or artist."""

    status: str = Field(description="Operation status (success/error)")
    seed_id: str = Field(description="ID of the seed track or artist")
    seed_type: str = Field(description="Type of seed (track/artist)")
    seed_name: str = Field(description="Name of the seed track or artist")
    count: int = Field(description="Number of tracks returned")
    tracks: List[Track] = Field(description="List of recommended tracks")
