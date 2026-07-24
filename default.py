from __future__ import annotations

import os
import sys

import xbmc
import xbmcgui

ADDON_PATH = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ADDON_PATH, "resources", "lib"))

from anime import ADDON_ID, configure_sources, generate_playlists, set_playlists_ready  # noqa: E402
from widget_order import configure_widget_order  # noqa: E402

if __name__ == "__main__":
    arguments = [arg.casefold() for arg in sys.argv[1:]]
    if "widget_order" in arguments:
        try:
            argument_index = arguments.index("widget_order")
            category = arguments[argument_index + 1]
            configure_widget_order(category)
        except Exception as exc:
            xbmc.log(f"[{ADDON_ID}] Widget reorder dialog failed: {exc}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification(
                "Estuary (roquira)",
                "Could not update widget order; check kodi.log",
                xbmcgui.NOTIFICATION_ERROR,
                7000,
            )
    elif "source_settings" in arguments:
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
        silent = "silent" in arguments
        try:
            generate_playlists(notify=not silent)
        except Exception as exc:
            set_playlists_ready(False)
            xbmc.log(f"[{ADDON_ID}] Manual playlist generation failed: {exc}", xbmc.LOGERROR)
            if not silent:
                xbmcgui.Dialog().notification("Estuary (roquira)", "Could not generate Anime filters; check kodi.log", xbmcgui.NOTIFICATION_ERROR, 7000)
