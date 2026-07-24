from __future__ import annotations

import xbmc
import xbmcgui


SKIN_STRING_PREFIX = "estuaryroquira_widget_order"
CUSTOM_ORDER_PREFIX = "estuaryroquira_custom_widget_order"

WIDGETS = {
    "movies": (
        ("categories", "Categories", "home_no_movies_categories_widget"),
        ("inprogress", "In Progress Movies", "home_no_movies_inprogress_widget"),
        ("recent", "Recently Added Movies", "home_no_movies_recentlyadded_widget"),
        ("unwatched", "Unwatched Movies", "home_no_movies_unwatched_widget"),
        ("random", "Random Movies", "home_no_movies_random_widget"),
        ("genres", "Genres", "home_no_movies_genres_widget"),
        ("sets", "Movie Sets", "home_no_movies_sets_widget"),
    ),
    "tvshows": (
        ("categories", "Categories", "home_no_tvshows_categories_widget"),
        ("inprogress", "In Progress TV Shows", "home_no_tvshows_inprogress_widget"),
        ("recentepisodes", "Recently Added Episodes", "home_no_tvshows_recentlyaddedepisodes_widget"),
        ("recent", "Recently Added TV Shows", "home_no_tvshows_recentlyadded_widget"),
        ("unwatched", "Unwatched TV Shows", "home_no_tvshows_unwatched_widget"),
        ("random", "Random TV Shows", "home_no_tvshows_random_widget"),
        ("genres", "Genres", "home_no_tvshows_genres_widget"),
        ("studios", "Studios", "home_no_tvshows_studios_widget"),
    ),
    "anime": (
        ("categories", "Categories", "home_no_anime_categories_widget"),
        ("movieinprogress", "Continue Watching Anime Movies", "home_no_anime_movies_inprogress_widget"),
        ("showinprogress", "Continue Watching Anime Shows", "home_no_anime_tvshows_inprogress_widget"),
        ("recentmovies", "Recently Added Anime Movies", "home_no_anime_movies_recentlyadded_widget"),
        ("recentepisodes", "Recently Added Anime Episodes", "home_no_anime_episodes_recentlyadded_widget"),
        ("recentshows", "Recently Added Anime Shows", "home_no_anime_tvshows_recentlyadded_widget"),
        ("unwatchedmovies", "Unwatched Anime Movies", "home_no_anime_movies_unwatched_widget"),
        ("unwatchedshows", "Unwatched Anime Shows", "home_no_anime_tvshows_unwatched_widget"),
        ("randommovies", "Random Anime Movies", "home_no_anime_movies_random_widget"),
        ("randomshows", "Random Anime Shows", "home_no_anime_tvshows_random_widget"),
    ),
}

CATEGORY_LABELS = {
    "movies": "Movie",
    "tvshows": "TV Show",
    "anime": "Anime",
}


def _order_setting(category: str, position: int) -> str:
    return f"{SKIN_STRING_PREFIX}_{category}_{position}"


def _custom_setting(category: str) -> str:
    return f"{CUSTOM_ORDER_PREFIX}_{category}"


def _set_skin_string(name: str, value: str) -> None:
    # Names and values come only from the constants above, so they cannot
    # contain commas or parentheses that would alter the Kodi built-in call.
    xbmc.executebuiltin(f"Skin.SetString({name},{value})")


def _save_order(category: str, order: list[str]) -> None:
    for position, key in enumerate(order, start=1):
        _set_skin_string(_order_setting(category, position), key)


def default_order(category: str) -> list[str]:
    return [key for key, _label, _disabled_setting in WIDGETS[category]]


def current_order(category: str) -> list[str]:
    defaults = default_order(category)
    valid = set(defaults)
    result = []
    for position in range(1, len(defaults) + 1):
        key = xbmc.getInfoLabel(f"Skin.String({_order_setting(category, position)})").strip()
        if key in valid and key not in result:
            result.append(key)
    result.extend(key for key in defaults if key not in result)
    return result


def configure_widget_order(category: str) -> bool:
    """Show a TV-remote-friendly picker and persist a custom widget sequence."""
    if category not in WIDGETS:
        raise ValueError(f"Unknown widget category: {category}")

    metadata = {key: (label, disabled) for key, label, disabled in WIDGETS[category]}
    order = current_order(category)
    changed = False
    title = f"Reorder {CATEGORY_LABELS[category]} Widgets"

    while True:
        rows = []
        for position, key in enumerate(order, start=1):
            label, disabled_setting = metadata[key]
            disabled = xbmc.getCondVisibility(f"Skin.HasSetting({disabled_setting})")
            suffix = " [Disabled]" if disabled else ""
            rows.append(f"{position}. {label}{suffix}")
        rows.append("Reset to Default Order")

        selected = xbmcgui.Dialog().select(title, rows)
        if selected < 0:
            break
        if selected == len(order):
            if xbmcgui.Dialog().yesno(title, "Restore the default widget order?"):
                order = default_order(category)
                _save_order(category, order)
                xbmc.executebuiltin(f"Skin.Reset({_custom_setting(category)})")
                changed = True
            continue

        key = order[selected]
        label = metadata[key][0]
        destinations = [f"{position}. {metadata[item][0]}" for position, item in enumerate(order, start=1)]
        destination = xbmcgui.Dialog().select(f"Move {label} to Position", destinations, preselect=selected)
        if destination < 0 or destination == selected:
            continue
        order.pop(selected)
        order.insert(destination, key)
        _save_order(category, order)
        xbmc.executebuiltin(f"Skin.SetBool({_custom_setting(category)})")
        changed = True

    if changed:
        xbmcgui.Dialog().notification(
            "Estuary (roquira)",
            f"{CATEGORY_LABELS[category]} widget order updated",
            xbmcgui.NOTIFICATION_INFO,
            3000,
        )
        xbmc.executebuiltin("ReloadSkin()")
    return changed
