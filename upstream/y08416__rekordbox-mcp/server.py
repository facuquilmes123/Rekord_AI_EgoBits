from mcp.server.fastmcp import FastMCP
from pyrekordbox import Rekordbox6Database

mcp = FastMCP("rekordbox")


def get_db() -> Rekordbox6Database:
    return Rekordbox6Database()


@mcp.tool()
def search_tracks(
    min_bpm: float | None = None,
    max_bpm: float | None = None,
    key: str | None = None,
    genre: str | None = None,
    artist: str | None = None,
    title: str | None = None,
) -> list[dict]:
    """Search tracks by BPM range, key, genre, artist, or title."""
    db = get_db()
    results = []
    for track in db.get_content():
        bpm = track.BPM / 100 if track.BPM else None
        if min_bpm is not None and (bpm is None or bpm < min_bpm):
            continue
        if max_bpm is not None and (bpm is None or bpm > max_bpm):
            continue
        if key is not None and (track.KeyName is None or key.lower() not in track.KeyName.lower()):
            continue
        if genre is not None and (track.Genre is None or genre.lower() not in track.Genre.Name.lower()):
            continue
        if artist is not None and (track.Artist is None or artist.lower() not in track.Artist.Name.lower()):
            continue
        if title is not None and (track.Title is None or title.lower() not in track.Title.lower()):
            continue
        results.append(_track_to_dict(track))
    return results


@mcp.tool()
def get_playlists() -> list[dict]:
    """Get all playlists with their track counts."""
    db = get_db()
    results = []
    for playlist in db.get_playlist():
        results.append({
            "id": int(playlist.ID),
            "name": playlist.Name,
            "track_count": len(list(playlist.Songs)),
        })
    return results


@mcp.tool()
def get_playlist_tracks(playlist_id: int) -> list[dict]:
    """Get all tracks in a specific playlist by playlist ID."""
    db = get_db()
    for playlist in db.get_playlist():
        if str(playlist.ID) == str(playlist_id):
            return [_track_to_dict(entry.Content) for entry in playlist.Songs]
    return []


@mcp.tool()
def get_library_stats() -> dict:
    """Get overall statistics of the rekordbox library."""
    db = get_db()
    tracks = list(db.get_content())

    genres: dict[str, int] = {}
    artists: dict[str, int] = {}

    for track in tracks:
        if track.Genre:
            genres[track.Genre.Name] = genres.get(track.Genre.Name, 0) + 1
        if track.Artist:
            artists[track.Artist.Name] = artists.get(track.Artist.Name, 0) + 1

    top_genres = sorted(genres.items(), key=lambda x: x[1], reverse=True)[:10]
    top_artists = sorted(artists.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_tracks": len(tracks),
        "total_playlists": len(list(db.get_playlist())),
        "top_genres": [{"name": n, "count": c} for n, c in top_genres],
        "top_artists": [{"name": n, "count": c} for n, c in top_artists],
    }


@mcp.tool()
def suggest_genre(track_id: int) -> dict:
    """Return detailed metadata for a track so you can infer the most appropriate genre.
    Use title, artist, remixer, label, BPM, key, release year, comment, and tags to suggest a genre.
    If current_genre is already set, you can confirm or suggest a correction."""
    db = get_db()
    for track in db.get_content():
        if str(track.ID) == str(track_id):
            return {
                "id": track.ID,
                "title": track.Title,
                "artist": track.ArtistName,
                "remixer": track.RemixerName,
                "label": track.LabelName,
                "bpm": track.BPM / 100 if track.BPM else None,
                "key": track.KeyName,
                "current_genre": track.GenreName,
                "release_year": track.ReleaseYear,
                "comment": track.Commnt,
                "my_tags": track.MyTagNames,
            }
    return {"error": f"Track {track_id} not found"}


@mcp.tool()
def tracks_without_genre(limit: int = 50) -> list[dict]:
    """Return tracks that have no genre assigned, up to limit. Useful for finding tracks that need genre inference."""
    db = get_db()
    results = []
    for track in db.get_content():
        if not track.GenreName:
            results.append({
                "id": track.ID,
                "title": track.Title,
                "artist": track.ArtistName,
                "bpm": track.BPM / 100 if track.BPM else None,
                "key": track.KeyName,
                "remixer": track.RemixerName,
                "label": track.LabelName,
                "release_year": track.ReleaseYear,
            })
            if len(results) >= limit:
                break
    return results


@mcp.tool()
def find_duplicates() -> list[dict]:
    """Find tracks with duplicate titles and artists."""
    db = get_db()
    seen: dict[str, list[dict]] = {}
    for track in db.get_content():
        key = f"{(track.Title or '').lower()}||{(track.Artist.Name if track.Artist else '').lower()}"
        if key not in seen:
            seen[key] = []
        seen[key].append(_track_to_dict(track))
    return [group for group in seen.values() if len(group) > 1]


def _track_to_dict(track) -> dict:
    return {
        "id": track.ID,
        "title": track.Title,
        "artist": track.Artist.Name if track.Artist else None,
        "album": track.Album.Name if track.Album else None,
        "genre": track.Genre.Name if track.Genre else None,
        "bpm": track.BPM / 100 if track.BPM else None,
        "key": track.KeyName,
        "duration_sec": track.Length,
        "comment": track.Commnt,
        "date_added": str(track.DateCreated) if track.DateCreated else None,
        "play_count": track.DJPlayCount,
        "rating": track.Rating,
    }


if __name__ == "__main__":
    mcp.run()

