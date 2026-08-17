from __future__ import annotations

import os
import sys

import xbmc

ADDON_PATH = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ADDON_PATH, "resources", "lib"))

from anime import ADDON_ID, generate_playlists, playlists_available, set_playlists_ready  # noqa: E402


def main() -> None:
    monitor = xbmc.Monitor()
    # Generate at service start, then periodically refresh in case sources or
    # add-on settings change. Five minutes keeps the service effectively idle.
    try:
        if playlists_available():
            set_playlists_ready(True)
        generate_playlists(notify=False)
    except Exception as exc:
        set_playlists_ready(False)
        xbmc.log(f"[{ADDON_ID}] Initial playlist generation failed: {exc}", xbmc.LOGERROR)
    while not monitor.waitForAbort(300):
        try:
            generate_playlists(notify=False)
        except Exception as exc:  # Kodi must keep running even if setup is bad.
            set_playlists_ready(False)
            xbmc.log(f"[{ADDON_ID}] Playlist refresh failed: {exc}", xbmc.LOGERROR)


if __name__ == "__main__":
    main()
