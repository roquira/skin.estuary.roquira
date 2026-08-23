from __future__ import annotations

import json
import os
import sys
import time

import xbmc
import xbmcgui

ADDON_PATH = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ADDON_PATH, "resources", "lib"))

from anime import ADDON_ID, generate_playlists, playlists_available, set_playlists_ready  # noqa: E402

COUNTRY_FLAG_LIMIT = 5
COUNTRY_FLAG_DBID_PROPERTY = "EstuaryRoquira.CountryFlagDBID"
COUNTRY_FLAG_PROPERTY_PREFIX = "EstuaryRoquira.CountryFlag"
COUNTRY_FLAG_POLL_SECONDS = 0.1


def clear_country_flags(window: xbmcgui.Window) -> None:
    window.clearProperty(COUNTRY_FLAG_DBID_PROPERTY)
    for index in range(1, COUNTRY_FLAG_LIMIT + 1):
        window.clearProperty(f"{COUNTRY_FLAG_PROPERTY_PREFIX}{index}")


def country_flags_enabled() -> bool:
    return not xbmc.getCondVisibility("Skin.HasSetting(hide_movie_country_flags)")


def load_movie_country_cache() -> dict[str, list[str]]:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "VideoLibrary.GetMovies",
        "params": {"properties": ["country"]},
    }
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
        movies = response.get("result", {}).get("movies", [])
    except Exception as exc:
        xbmc.log(f"[{ADDON_ID}] Cannot cache Movie countries: {exc}", xbmc.LOGWARNING)
        return {}

    result = {}
    for movie in movies if isinstance(movies, list) else []:
        db_id = movie.get("movieid")
        countries = movie.get("country", [])
        if not isinstance(db_id, int) or not isinstance(countries, list):
            continue
        clean_countries = [
            country.strip()
            for country in countries
            if isinstance(country, str) and country.strip()
        ]
        if clean_countries:
            result[str(db_id)] = clean_countries
    return result


def update_country_flags(
    window: xbmcgui.Window,
    previous_focus: str,
    country_cache: dict[str, list[str]],
) -> str:
    """Expose a focused movie's country array as separate skin properties."""
    db_type = xbmc.getInfoLabel("ListItem.DBType").strip().casefold()
    db_id = xbmc.getInfoLabel("ListItem.DBID").strip()
    focus = f"{db_type}:{db_id}"
    if focus == previous_focus:
        return previous_focus

    clear_country_flags(window)
    if db_type != "movie" or not db_id.isdigit():
        return focus

    countries = country_cache.get(db_id, [])
    if not countries:
        return focus

    window.setProperty(COUNTRY_FLAG_DBID_PROPERTY, db_id)
    for index, country in enumerate(countries[:COUNTRY_FLAG_LIMIT], start=1):
        window.setProperty(f"{COUNTRY_FLAG_PROPERTY_PREFIX}{index}", country)
    return focus


def main() -> None:
    monitor = xbmc.Monitor()
    home_window = xbmcgui.Window(10000)
    # Generate at service start, then refresh playlists every five minutes in
    # case sources or add-on settings change.
    try:
        if playlists_available():
            set_playlists_ready(True)
        generate_playlists(notify=False)
    except Exception as exc:
        set_playlists_ready(False)
        xbmc.log(f"[{ADDON_ID}] Initial playlist generation failed: {exc}", xbmc.LOGERROR)
    last_playlist_refresh = time.monotonic()
    previous_focus = ""
    flags_are_enabled = country_flags_enabled()
    country_cache = load_movie_country_cache() if flags_are_enabled else {}
    while True:
        poll_seconds = COUNTRY_FLAG_POLL_SECONDS if flags_are_enabled else 0.5
        if monitor.waitForAbort(poll_seconds):
            break

        latest_flag_setting = country_flags_enabled()
        if latest_flag_setting and not flags_are_enabled:
            country_cache = load_movie_country_cache()
            previous_focus = ""
        elif flags_are_enabled and not latest_flag_setting:
            clear_country_flags(home_window)
            country_cache = {}
            previous_focus = ""
        flags_are_enabled = latest_flag_setting

        if flags_are_enabled:
            previous_focus = update_country_flags(home_window, previous_focus, country_cache)

        if time.monotonic() - last_playlist_refresh >= 300:
            try:
                generate_playlists(notify=False)
            except Exception as exc:  # Kodi must keep running even if setup is bad.
                set_playlists_ready(False)
                xbmc.log(f"[{ADDON_ID}] Playlist refresh failed: {exc}", xbmc.LOGERROR)
            if flags_are_enabled:
                country_cache = load_movie_country_cache()
                previous_focus = ""
            last_playlist_refresh = time.monotonic()


if __name__ == "__main__":
    main()
