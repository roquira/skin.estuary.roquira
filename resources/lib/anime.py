from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = "skin.estuary.roquira"
DEFAULT_MOVIE_SOURCE = "Anime Movies"
DEFAULT_SHOW_SOURCE = "Anime Shows"
INVALID_PATH = "special://profile/addon_data/skin.estuary.roquira/source-not-found/"
READY_PROPERTY = "EstuaryRoquira.PlaylistsReady"
READY_SKIN_SETTING = "estuaryroquira_playlists_ready"
READY_MIGRATION_PROPERTY = "EstuaryRoquira.PersistentReadyMigration"


def _addon() -> xbmcaddon.Addon:
    return xbmcaddon.Addon(ADDON_ID)


def _raw_setting(setting_id: str) -> str:
    try:
        return (_addon().getSetting(setting_id) or "").strip()
    except Exception as exc:
        xbmc.log(f"[{ADDON_ID}] Cannot read setting {setting_id}: {exc}", xbmc.LOGWARNING)
        return ""


def source_names_for_setting(setting_id: str, default: str) -> list[str]:
    """Read both the old single-name format and the new JSON list format."""
    raw = _raw_setting(setting_id)
    if not raw:
        return [default] if default else []
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        decoded = None
    if isinstance(decoded, list):
        return [name.strip() for name in decoded if isinstance(name, str) and name.strip()]
    return [raw]


def set_source_names(setting_id: str, names: Iterable[str]) -> None:
    values = []
    seen = set()
    for name in names:
        clean_name = str(name).strip()
        folded_name = clean_name.casefold()
        if clean_name and folded_name not in seen:
            values.append(clean_name)
            seen.add(folded_name)
    _addon().setSetting(setting_id, json.dumps(values, ensure_ascii=False))


def _bool_setting(setting_id: str, default: bool) -> bool:
    try:
        raw = _addon().getSetting(setting_id)
    except Exception as exc:
        xbmc.log(f"[{ADDON_ID}] Cannot read setting {setting_id}: {exc}", xbmc.LOGWARNING)
        return default
    if raw == "":
        return default
    return raw.strip().casefold() in {"true", "1", "yes", "on"}


def set_playlists_ready(ready: bool) -> None:
    window = xbmcgui.Window(10000)
    if ready:
        window.setProperty(READY_PROPERTY, "true")
        # Home's conditional includes are selected while Home.xml is built.
        # A window property set later in startup is too late, leaving Anime
        # absent and Movies/TV Shows on their unfiltered fallback branches.
        # Persist readiness so subsequent boots select the filtered branches
        # immediately. Reload once when migrating an existing installation.
        if not xbmc.getCondVisibility(f"Skin.HasSetting({READY_SKIN_SETTING})"):
            reload_required = window.getProperty(READY_MIGRATION_PROPERTY) != "true"
            window.setProperty(READY_MIGRATION_PROPERTY, "true")
            xbmc.executebuiltin(f"Skin.SetBool({READY_SKIN_SETTING})")
            if reload_required:
                xbmc.log(f"[{ADDON_ID}] Migrating Home to persistent playlist readiness", xbmc.LOGINFO)
                xbmc.executebuiltin("ReloadSkin()")
    else:
        # Keep the persistent initialization marker on transient refresh
        # failures. Existing playlists remain usable and should not make Home
        # fall back to unfiltered Movies/TV Shows during an always-on session.
        window.clearProperty(READY_PROPERTY)


def addon_data_dir() -> Path:
    path = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}")
    return Path(path)


def playlist_dir() -> Path:
    path = addon_data_dir() / "playlists"
    path.mkdir(parents=True, exist_ok=True)
    return path


def kodi_playlist_path(filename: str) -> str:
    return f"special://profile/addon_data/{ADDON_ID}/playlists/{filename}"


def _main_movie_exclude_paths() -> list[str]:
    if not _bool_setting("exclude_from_main", True):
        return []
    movie_sources = source_names_for_setting("anime_movies_source", DEFAULT_MOVIE_SOURCE)
    return resolve_source_paths(movie_sources, read_video_sources())


def _is_under_source(file_path: str, source_paths: Iterable[str]) -> bool:
    folded_file = file_path.replace("\\", "/").casefold()
    return any(
        folded_file.startswith(source_path.replace("\\", "/").casefold())
        for source_path in source_paths
        if source_path
    )


def generate_movie_country_playlists() -> list[tuple[str, str]]:
    """Return explicit country folders for Home instead of Kodi's broken grouped paths."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "VideoLibrary.GetMovies",
        "params": {"properties": ["country", "file"]},
    }
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    except (TypeError, ValueError) as exc:
        xbmc.log(f"[{ADDON_ID}] Cannot read Movie countries: {exc}", xbmc.LOGERROR)
        return []

    if "error" in response:
        xbmc.log(f"[{ADDON_ID}] Cannot read Movie countries: {response['error']}", xbmc.LOGERROR)
        return []

    exclude_paths = _main_movie_exclude_paths()
    countries: dict[str, str] = {}
    for movie in response.get("result", {}).get("movies", []):
        file_path = movie.get("file", "")
        if not isinstance(file_path, str) or _is_under_source(file_path, exclude_paths):
            continue
        raw_countries = movie.get("country", [])
        if isinstance(raw_countries, str):
            # JSON-RPC normally returns an array. Retain compatibility with
            # older/custom builds that expose Kodi's display separator.
            raw_countries = raw_countries.split(" / ")
        if not isinstance(raw_countries, list):
            continue
        for country in raw_countries:
            if not isinstance(country, str):
                continue
            clean_country = country.strip()
            if clean_country:
                countries.setdefault(clean_country.casefold(), clean_country)

    result = []
    for key in sorted(countries):
        country = countries[key]
        digest = hashlib.sha256(country.encode("utf-8")).hexdigest()[:16]
        filename = f"main_movies_country_{digest}.xsp"
        write_playlist(
            filename,
            "movies",
            country,
            exclude_paths=exclude_paths,
            extra_rules=[("country", "is", country)],
            order="sorttitle",
        )
        result.append((country, filename))
    return result


def read_video_sources() -> dict[str, list[str]]:
    sources_file = Path(xbmcvfs.translatePath("special://profile/sources.xml"))
    if not sources_file.exists():
        return {}
    try:
        root = ET.parse(sources_file).getroot()
    except (ET.ParseError, OSError) as exc:
        xbmc.log(f"[{ADDON_ID}] Cannot parse sources.xml: {exc}", xbmc.LOGERROR)
        return {}

    result: dict[str, list[str]] = {}
    video = root.find("video")
    if video is None:
        return result
    for source in video.findall("source"):
        name = (source.findtext("name") or "").strip()
        paths = [
            (node.text or "").strip()
            for node in source.findall("path")
            if (node.text or "").strip()
        ]
        if name and paths:
            result.setdefault(name.casefold(), [])
            for path in paths:
                if path not in result[name.casefold()]:
                    result[name.casefold()].append(path)
    return result


def read_video_source_names() -> list[str]:
    """Return the display names of configured Kodi video sources."""
    sources_file = Path(xbmcvfs.translatePath("special://profile/sources.xml"))
    if not sources_file.exists():
        return []
    try:
        root = ET.parse(sources_file).getroot()
    except (ET.ParseError, OSError) as exc:
        xbmc.log(f"[{ADDON_ID}] Cannot parse sources.xml: {exc}", xbmc.LOGERROR)
        return []

    video = root.find("video")
    if video is None:
        return []
    names: dict[str, str] = {}
    for source in video.findall("source"):
        name = (source.findtext("name") or "").strip()
        has_path = any((node.text or "").strip() for node in source.findall("path"))
        if name and has_path:
            names.setdefault(name.casefold(), name)
    return [names[key] for key in sorted(names)]


def resolve_source_paths(source_names: str | Iterable[str], sources: dict[str, list[str]]) -> list[str]:
    if isinstance(source_names, str):
        source_names = [source_names]
    paths = []
    seen = set()
    for source_name in source_names:
        for path in sources.get(source_name.strip().casefold(), []):
            if path not in seen:
                paths.append(path)
                seen.add(path)
    return paths


def _select_source_names(title: str, options: list[str], selected: list[str]) -> list[str] | None:
    selected_keys = {name.casefold() for name in selected}
    preselect = [index for index, name in enumerate(options) if name.casefold() in selected_keys]
    choice = xbmcgui.Dialog().multiselect(title, options, preselect=preselect)
    if choice is None:
        return None
    return [options[index] for index in choice]


def configure_sources() -> bool:
    """Let the user map one or more configured video sources to each Anime type."""
    options = read_video_source_names()
    if not options:
        xbmcgui.Dialog().ok("Estuary (roquira)", "No Kodi video sources were found.")
        return False

    movie_names = _select_source_names(
        "Anime Movies sources",
        options,
        source_names_for_setting("anime_movies_source", DEFAULT_MOVIE_SOURCE),
    )
    if movie_names is None:
        return False
    show_names = _select_source_names(
        "Anime Shows sources",
        options,
        source_names_for_setting("anime_shows_source", DEFAULT_SHOW_SOURCE),
    )
    if show_names is None:
        return False

    set_source_names("anime_movies_source", movie_names)
    set_source_names("anime_shows_source", show_names)
    set_playlists_ready(False)
    try:
        generate_playlists(notify=True)
    except Exception as exc:
        set_playlists_ready(False)
        xbmc.log(f"[{ADDON_ID}] Source configuration failed: {exc}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "Estuary (roquira)",
            "Could not regenerate Anime filters; check kodi.log",
            xbmcgui.NOTIFICATION_ERROR,
            7000,
        )
    return True


def _add_rule(parent: ET.Element, field: str, operator: str, values: Iterable[str] | str | None) -> None:
    rule = ET.SubElement(parent, "rule", {"field": field, "operator": operator})
    if values is None:
        return
    if isinstance(values, str):
        values = [values]
    for value in values:
        ET.SubElement(rule, "value").text = str(value)


def _write_playlist_payload(destination: Path, payload: bytes) -> None:
    try:
        if destination.is_file() and destination.read_bytes() == payload:
            return
    except OSError:
        # A later atomic replacement will either succeed or report the real
        # filesystem error to the caller.
        pass

    # Plugin routes and the background service may generate simultaneously.
    # A unique temporary filename prevents one process from moving another
    # process's .tmp file, which caused intermittent category warning entries.
    fd, temporary_name = tempfile.mkstemp(
        prefix=destination.name + ".",
        suffix=".tmp",
        dir=str(destination.parent),
    )
    try:
        with os.fdopen(fd, "wb") as temporary_file:
            temporary_file.write(payload)
            temporary_file.flush()
        os.replace(temporary_name, destination)
    finally:
        try:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        except OSError:
            pass


def write_playlist(
    filename: str,
    media_type: str,
    name: str,
    *,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    extra_rules: list[tuple[str, str, str | None]] | None = None,
    group: str | None = None,
    group_mixed: bool = False,
    limit: int | None = None,
    order: str | None = None,
    direction: str = "ascending",
) -> None:
    root = ET.Element("smartplaylist", {"type": media_type})
    ET.SubElement(root, "name").text = name
    ET.SubElement(root, "match").text = "all"

    # Kodi treats multiple values in one positive rule as alternatives. This
    # permits a single named source to contain more than one physical path.
    if include_paths is not None:
        _add_rule(root, "path", "startswith", include_paths or [INVALID_PATH])
    for path in exclude_paths or []:
        # Separate negative rules guarantee that every anime path is excluded.
        _add_rule(root, "path", "doesnotcontain", path)
    for field, operator, value in extra_rules or []:
        _add_rule(root, field, operator, value)

    if group:
        attrs = {"mixed": "true"} if group_mixed else {}
        ET.SubElement(root, "group", attrs).text = group
    if limit is not None:
        ET.SubElement(root, "limit").text = str(limit)
    if order:
        order_attributes = {"direction": direction}
        # Kodi can expose a movie with multiple video versions as a folder-like
        # item. Without this smart-playlist attribute, folder entries are sorted
        # ahead of ordinary movies before the selected title/date ordering is
        # applied. Native movie library nodes suppress that folders-first split.
        # Match their behaviour for every ungrouped movie playlist so versioned
        # movies sort alongside all other movies.
        if media_type == "movies" and group is None:
            order_attributes["ignorefolders"] = "true"
        ET.SubElement(root, "order", order_attributes).text = order

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    # Build the complete file in memory first. Avoid touching the destination
    # when nothing changed; Kodi can keep reading the existing playlist.
    buffer = io.BytesIO()
    tree.write(buffer, encoding="utf-8", xml_declaration=True)
    payload = buffer.getvalue()

    directory = playlist_dir()
    _write_playlist_payload(directory / filename, payload)



_REQUIRED_PLAYLISTS = (
    "anime_movies_titles.xsp",
    "anime_tvshows_titles.xsp",
    "main_movies_titles.xsp",
    "main_movies_countries.xsp",
    "main_tvshows_titles.xsp",
    "anime_tvshows_recent.xsp",
    "main_tvshows_recent.xsp",
    "main_tvshows_random.xsp",
)


def playlists_available() -> bool:
    directory = playlist_dir()
    return all((directory / filename).is_file() for filename in _REQUIRED_PLAYLISTS)

def generate_playlists(notify: bool = False) -> dict[str, object]:
    movie_sources = source_names_for_setting("anime_movies_source", DEFAULT_MOVIE_SOURCE)
    show_sources = source_names_for_setting("anime_shows_source", DEFAULT_SHOW_SOURCE)
    exclude_from_main = _bool_setting("exclude_from_main", True)

    sources = read_video_sources()
    movie_paths = resolve_source_paths(movie_sources, sources)
    show_paths = resolve_source_paths(show_sources, sources)

    # Anime movie playlists and category groupings.
    write_playlist("anime_movies_titles.xsp", "movies", "Anime Movies", include_paths=movie_paths, order="sorttitle")
    write_playlist("anime_movies_inprogress.xsp", "movies", "Continue Watching Anime Movies", include_paths=movie_paths,
                   extra_rules=[("inprogress", "true", None)], limit=15, order="lastplayed", direction="descending")
    write_playlist("anime_movies_recent.xsp", "movies", "Recently Added Anime Movies", include_paths=movie_paths,
                   extra_rules=[("dateadded", "after", "2012-01-01"), ("playcount", "lessthan", "1")],
                   limit=15, order="dateadded", direction="descending")
    write_playlist("anime_movies_unwatched.xsp", "movies", "Unwatched Anime Movies", include_paths=movie_paths,
                   extra_rules=[("playcount", "is", "0")], limit=15, order="random", direction="descending")
    write_playlist("anime_movies_random.xsp", "movies", "Random Anime Movies", include_paths=movie_paths,
                   limit=15, order="random", direction="descending")
    for suffix, group in [("genres", "genres"), ("years", "years"), ("actors", "actors"),
                          ("directors", "directors"), ("studios", "studios")]:
        write_playlist(f"anime_movies_{suffix}.xsp", "movies", f"Anime Movie {suffix.title()}",
                       include_paths=movie_paths, group=group)
    write_playlist("anime_movies_sets.xsp", "movies", "Anime Movie Sets", include_paths=movie_paths,
                   group="sets", group_mixed=True)

    # Anime TV-show and episode playlists.
    write_playlist("anime_tvshows_titles.xsp", "tvshows", "Anime Shows", include_paths=show_paths, order="title")
    write_playlist("anime_tvshows_inprogress.xsp", "tvshows", "Continue Watching Anime Shows", include_paths=show_paths,
                   extra_rules=[("inprogress", "true", None)], limit=15, order="lastplayed", direction="descending")
    write_playlist("anime_episodes_recent.xsp", "episodes", "Recently Added Anime Episodes", include_paths=show_paths,
                   extra_rules=[("dateadded", "after", "2012-01-01"), ("playcount", "lessthan", "1")],
                   limit=15, order="dateadded", direction="descending")
    write_playlist("anime_tvshows_recent.xsp", "tvshows", "Recently Added Anime Shows", include_paths=show_paths,
                   extra_rules=[("dateadded", "after", "2012-01-01"), ("numepisodes", "greaterthan", "0")],
                   limit=15, order="dateadded", direction="descending")
    write_playlist("anime_tvshows_unwatched.xsp", "tvshows", "Unwatched Anime Shows", include_paths=show_paths,
                   extra_rules=[("numwatched", "is", "0"), ("numepisodes", "greaterthan", "0")],
                   limit=15, order="random")
    write_playlist("anime_tvshows_random.xsp", "tvshows", "Random Anime Shows", include_paths=show_paths,
                   limit=15, order="random")
    for suffix, group in [("genres", "genres"), ("years", "years"), ("actors", "actors"), ("studios", "studios")]:
        write_playlist(f"anime_tvshows_{suffix}.xsp", "tvshows", f"Anime Show {suffix.title()}",
                       include_paths=show_paths, group=group)

    movie_excludes = movie_paths if exclude_from_main else []
    show_excludes = show_paths if exclude_from_main else []

    # Replacement playlists for the normal Movies section.
    write_playlist("main_movies_titles.xsp", "movies", "Movies", exclude_paths=movie_excludes, order="sorttitle")
    write_playlist("main_movies_inprogress.xsp", "movies", "In-progress Movies", exclude_paths=movie_excludes,
                   extra_rules=[("inprogress", "true", None)], limit=15, order="lastplayed", direction="descending")
    write_playlist("main_movies_recent.xsp", "movies", "Recently Added Movies", exclude_paths=movie_excludes,
                   extra_rules=[("dateadded", "after", "2012-01-01"), ("playcount", "lessthan", "1")],
                   limit=15, order="dateadded", direction="descending")
    write_playlist("main_movies_unwatched.xsp", "movies", "Unwatched Movies", exclude_paths=movie_excludes,
                   extra_rules=[("playcount", "is", "0")], limit=15, order="random", direction="descending")
    write_playlist("main_movies_random.xsp", "movies", "Random Movies", exclude_paths=movie_excludes,
                   limit=15, order="random", direction="descending")
    for suffix, group in [("genres", "genres"), ("countries", "countries"), ("years", "years"),
                          ("actors", "actors"), ("directors", "directors"), ("studios", "studios")]:
        write_playlist(f"main_movies_{suffix}.xsp", "movies", f"Movie {suffix.title()}",
                       exclude_paths=movie_excludes, group=group)
    write_playlist("main_movies_sets.xsp", "movies", "Movie Sets", exclude_paths=movie_excludes,
                   group="sets", group_mixed=True)

    # Replacement playlists for the normal TV Shows section.
    write_playlist("main_tvshows_titles.xsp", "tvshows", "TV Shows", exclude_paths=show_excludes, order="title")
    write_playlist("main_tvshows_inprogress.xsp", "tvshows", "In-progress TV Shows", exclude_paths=show_excludes,
                   extra_rules=[("inprogress", "true", None)], limit=15, order="lastplayed", direction="descending")
    write_playlist("main_episodes_recent.xsp", "episodes", "Recently Added Episodes", exclude_paths=show_excludes,
                   extra_rules=[("dateadded", "after", "2012-01-01"), ("playcount", "lessthan", "1")],
                   limit=15, order="dateadded", direction="descending")
    write_playlist("main_tvshows_recent.xsp", "tvshows", "Recently Added TV Shows", exclude_paths=show_excludes,
                   extra_rules=[("dateadded", "after", "2012-01-01"), ("numepisodes", "greaterthan", "0")],
                   limit=15, order="dateadded", direction="descending")
    write_playlist("main_tvshows_unwatched.xsp", "tvshows", "Unwatched TV Shows", exclude_paths=show_excludes,
                   extra_rules=[("numwatched", "is", "0"), ("numepisodes", "greaterthan", "0")],
                   limit=15, order="random")
    write_playlist("main_tvshows_random.xsp", "tvshows", "Random TV Shows", exclude_paths=show_excludes,
                   limit=15, order="random")
    for suffix, group in [("genres", "genres"), ("years", "years"), ("actors", "actors"), ("studios", "studios")]:
        write_playlist(f"main_tvshows_{suffix}.xsp", "tvshows", f"TV Show {suffix.title()}",
                       exclude_paths=show_excludes, group=group)

    status = {
        # Keep the singular keys for callers written against 4.1.7 while
        # exposing the full selections for diagnostics.
        "movie_source": ", ".join(movie_sources),
        "show_source": ", ".join(show_sources),
        "movie_sources": movie_sources,
        "show_sources": show_sources,
        "movie_paths": movie_paths,
        "show_paths": show_paths,
        "exclude_from_main": exclude_from_main,
    }
    xbmc.log(f"[{ADDON_ID}] Anime playlists generated: {status}", xbmc.LOGINFO)
    set_playlists_ready(True)

    if notify:
        missing = []
        if not movie_paths:
            missing.append(", ".join(movie_sources) or "Anime Movies")
        if not show_paths:
            missing.append(", ".join(show_sources) or "Anime Shows")
        if missing:
            import xbmcgui
            xbmcgui.Dialog().notification(
                "Estuary (roquira)",
                "Source not found: " + ", ".join(missing),
                xbmcgui.NOTIFICATION_WARNING,
                7000,
            )
        else:
            import xbmcgui
            xbmcgui.Dialog().notification("Estuary (roquira)", "Anime filters regenerated", xbmcgui.NOTIFICATION_INFO, 4000)
    return status
