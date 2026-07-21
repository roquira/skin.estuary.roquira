from __future__ import annotations

import os
import sys

import xbmc
import xbmcgui

ADDON_PATH = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ADDON_PATH, "resources", "lib"))

from anime import ADDON_ID, configure_sources, generate_playlists, set_playlists_ready  # noqa: E402

if __name__ == "__main__":
    if any(arg.casefold() == "source_settings" for arg in sys.argv[1:]):
        try:
            configure_sources()
        except Exception as exc:
            set_playlists_ready(False)
            xbmc.log(f"[{ADDON_ID}] Source picker failed: {exc}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification(
                "Estuary (roquira)",
                "Could not configure Anime sources; check kodi.log",
                xbmcgui.NOTIFICATION_ERROR,
                7000,
            )
    else:
        silent = any(arg.casefold() == "silent" for arg in sys.argv[1:])
        try:
            generate_playlists(notify=not silent)
        except Exception as exc:
            set_playlists_ready(False)
            xbmc.log(f"[{ADDON_ID}] Manual playlist generation failed: {exc}", xbmc.LOGERROR)
            if not silent:
                xbmcgui.Dialog().notification("Estuary (roquira)", "Could not generate Anime filters; check kodi.log", xbmcgui.NOTIFICATION_ERROR, 7000)
