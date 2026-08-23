from __future__ import annotations

import os
import sys
from urllib.parse import parse_qs

import xbmc
import xbmcgui
import xbmcplugin

ADDON_PATH = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ADDON_PATH, "resources", "lib"))

from anime import (  # noqa: E402
    ADDON_ID,
    generate_movie_country_playlists,
    generate_playlists,
    kodi_playlist_path,
    playlists_available,
    set_playlists_ready,
)

HANDLE = int(sys.argv[1])
PARAMS = parse_qs(sys.argv[2][1:] if len(sys.argv) > 2 and sys.argv[2].startswith("?") else "")
MODE = PARAMS.get("mode", ["anime_hub"])[0]


def add_path_folder(label: str, path: str, icon: str) -> None:
    item = xbmcgui.ListItem(label=label)
    item.setArt({"icon": icon, "thumb": icon})
    item.setProperty("IsPlayable", "false")
    xbmcplugin.addDirectoryItem(HANDLE, path, item, isFolder=True)


def add_folder(label: str, playlist: str, icon: str) -> None:
    add_path_folder(label, kodi_playlist_path(playlist), icon)


def anime_hub() -> None:
    xbmcplugin.setPluginCategory(HANDLE, "Anime")
    xbmcplugin.setContent(HANDLE, "files")
    add_folder("Anime Movies", "anime_movies_titles.xsp", "DefaultMovies.png")
    add_folder("Anime Shows", "anime_tvshows_titles.xsp", "DefaultTVShows.png")


def anime_categories() -> None:
    xbmcplugin.setPluginCategory(HANDLE, "Anime Categories")
    xbmcplugin.setContent(HANDLE, "files")
    add_folder("Anime Movies", "anime_movies_titles.xsp", "DefaultMovies.png")
    add_folder("Anime Shows", "anime_tvshows_titles.xsp", "DefaultTVShows.png")
    add_folder("Movie Genres", "anime_movies_genres.xsp", "DefaultGenre.png")
    add_folder("Show Genres", "anime_tvshows_genres.xsp", "DefaultGenre.png")
    add_folder("Movie Years", "anime_movies_years.xsp", "DefaultYear.png")
    add_folder("Show Years", "anime_tvshows_years.xsp", "DefaultYear.png")
    add_folder("Movie Studios", "anime_movies_studios.xsp", "DefaultStudios.png")
    add_folder("Show Studios", "anime_tvshows_studios.xsp", "DefaultStudios.png")


def movie_categories() -> None:
    xbmcplugin.setPluginCategory(HANDLE, "Movie Categories")
    xbmcplugin.setContent(HANDLE, "files")
    add_folder("Titles", "main_movies_titles.xsp", "DefaultMovieTitle.png")
    add_folder("Genres", "main_movies_genres.xsp", "DefaultGenre.png")
    add_path_folder("Countries", f"plugin://{ADDON_ID}/?mode=movie_countries", "DefaultCountry.png")
    add_folder("Years", "main_movies_years.xsp", "DefaultYear.png")
    add_folder("Actors", "main_movies_actors.xsp", "DefaultActor.png")
    add_folder("Directors", "main_movies_directors.xsp", "DefaultDirector.png")
    add_folder("Studios", "main_movies_studios.xsp", "DefaultStudios.png")
    add_folder("Sets", "main_movies_sets.xsp", "DefaultSets.png")


def movie_countries() -> None:
    xbmcplugin.setPluginCategory(HANDLE, "Countries")
    xbmcplugin.setContent(HANDLE, "countries")
    for country, playlist in generate_movie_country_playlists():
        add_folder(country, playlist, f"special://skin/media/flags/countries/{country}.png")


def tv_categories() -> None:
    xbmcplugin.setPluginCategory(HANDLE, "TV Show Categories")
    xbmcplugin.setContent(HANDLE, "files")
    add_folder("Titles", "main_tvshows_titles.xsp", "DefaultTVShowTitle.png")
    add_folder("Genres", "main_tvshows_genres.xsp", "DefaultGenre.png")
    add_folder("Years", "main_tvshows_years.xsp", "DefaultYear.png")
    add_folder("Actors", "main_tvshows_actors.xsp", "DefaultActor.png")
    add_folder("Studios", "main_tvshows_studios.xsp", "DefaultStudios.png")


def main() -> None:
    # The service owns routine regeneration. Only self-heal here when the
    # required files are actually absent; otherwise three Home category
    # widgets could all regenerate concurrently.
    try:
        if not playlists_available():
            generate_playlists(notify=False)
        else:
            set_playlists_ready(True)
    except Exception as exc:
        set_playlists_ready(False)
        xbmc.log(f"[{ADDON_ID}] Plugin playlist generation failed: {exc}", xbmc.LOGERROR)
        item = xbmcgui.ListItem(label="Anime filters could not be generated — check kodi.log")
        item.setArt({"icon": "DefaultWarning.png", "thumb": "DefaultWarning.png"})
        xbmcplugin.addDirectoryItem(HANDLE, "", item, isFolder=False)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True, cacheToDisc=False)
        return
    routes = {
        "anime_hub": anime_hub,
        "anime_categories": anime_categories,
        "movie_categories": movie_categories,
        "movie_countries": movie_countries,
        "tv_categories": tv_categories,
    }
    routes.get(MODE, anime_hub)()
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True, cacheToDisc=False)


if __name__ == "__main__":
    main()
