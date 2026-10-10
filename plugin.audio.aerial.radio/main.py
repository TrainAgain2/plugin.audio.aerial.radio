# -*- coding: utf-8 -*-
"""Aerial Radio Catalog for Kodi.

This add-on plays public radio streams listed by Radio Browser and retains the
Aerial v0.7.1 registry as an offline catalogue fallback. It does not bypass
DRM, authentication, or geo-restrictions.
"""
from __future__ import print_function

import gzip
import json
import os
import sys
from collections import Counter

try:
    from urllib.parse import parse_qs, urlencode
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
except ImportError:  # pragma: no cover - Kodi 18 compatibility only
    from urlparse import parse_qs
    from urllib import urlencode
    from urllib2 import Request, urlopen, URLError, HTTPError

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

try:
    import xbmcvfs
except ImportError:  # pragma: no cover - fallback for offline tests
    xbmcvfs = None


ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
ADDON_PATH = ADDON.getAddonInfo("path")
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
BASE_URL = sys.argv[0] if sys.argv else "plugin://%s/" % ADDON_ID
RADIO_BROWSER_BASE = "https://all.api.radio-browser.info/json"
OFFLINE_REGISTRY_PATH = os.path.join(
    ADDON_PATH, "resources", "data", "aerial-v0.7.1-registry.json.gz"
)
FANART_PATH = os.path.join(ADDON_PATH, "fanart.png")
DEFAULT_ICON_PATH = os.path.join(ADDON_PATH, "icon.png")


def addon_profile_path():
    """Return the add-on profile directory as a normal local filesystem path."""
    profile = ADDON.getAddonInfo("profile")
    if profile and xbmcvfs:
        try:
            return xbmcvfs.translatePath(profile)
        except (AttributeError, TypeError):
            pass
    return profile or os.path.join(ADDON_PATH, "profile")


FAVORITES_PATH = os.path.join(addon_profile_path(), "favorites.json")
MENU_ART = {
    "popular": "menu-popular.png",
    "recent": "menu-recent.png",
    "moods": "menu-moods.png",
    "portuguese": "menu-portuguese.png",
    "country_search": "menu-country-search.png",
    "countries": "menu-countries.png",
    "genres": "menu-genres.png",
    "search": "menu-search.png",
    "local": "menu-local.png",
    "favorites": "menu-favorites.png",
}
ACTION_ART = {
    "stations": "popular",
    "moods": "moods",
    "country_search": "country_search",
    "countries": "countries",
    "tags": "genres",
    "search": "search",
    "local_menu": "local",
    "local_countries": "countries",
    "local_tags": "genres",
    "local_stations": "local",
    "local_search": "search",
    "favorites": "favorites",
}
USER_AGENT = "plugin.audio.aerial.radio/0.4.7 (Kodi; public-radio-directory)"

# The exact thematic selections shipped by Aerial v0.7.1. UUID references are
# stable Radio Browser station IDs; name-only entries point at curated records
# included in Aerial's bundled registry.
MOODS = (
    (
        "relax",
        "Relaxar",
        (
            {"id": "3fd18c3f-8157-11e9-aa30-52543be04c81"},
            {"name": "ABC Lounge"},
            {"id": "2ee81587-dba9-4d68-82b3-a7b32aafc525", "label": "Nordic Lodge Copenhagen"},
            {"name": "Bossa Jazz Brasil"},
            {"name": "Radio Paradise Mellow Mix"},
            {"id": "24273571-703e-4373-b715-d7e7680d7599"},
            {"name": "OneLuvFM"},
            {"name": "FIP"},
            {"id": "9766d47a-68a3-4a30-8aec-c026f1ec6020"},
            {"id": "86468748-3045-4b88-97ef-e6d266c901f5"},
        ),
    ),
    (
        "focus",
        "Foco",
        (
            {"id": "60ede1ca-d7fa-4a36-a047-aec873b9be41"},
            {"id": "d5468df4-e6d0-11e9-a96c-52543be04c81"},
            {"id": "1e0ad463-0dbc-4913-b12d-7d0b7300882b"},
            {"id": "37e6772a-5ab7-429d-84bc-fedc606cc8c4"},
            {"id": "960eb232-0601-11e8-ae97-52543be04c81"},
           {"name": "A Strangely Isolated Place"},
           {"id": "a5213a32-d614-47bc-8d52-70a2b6eed8e1"},
            {"id": "960cf833-0601-11e8-ae97-52543be04c81"},
           {"id": "58d3cce6-62b5-43f1-8f41-8d024998aabc"},
           {"name": "Radio Swiss Jazz"},
       ),
    ),
    (
        "morning",
        "Manhã",
        (
            {"id": "1c41c07b-b995-11e8-aaf2-52543be04c81"},
            {"id": "d210ac34-0fee-4586-b9d6-24b84e2c0c4e"},
            {"id": "7babd377-ed7c-4a63-9778-47b0fd94983b"},
            {"id": "c5955cee-2cdf-40b2-8b5f-aa55bafddbef"},
            {"id": "26edc6b6-d221-4814-a6a9-0dd5d5d365d2"},
            {"name": "Veneno"},
            {"id": "450a5177-1752-11ea-a620-52543be04c81"},
            {"id": "a1c99f81-f8d1-4f6d-b9e3-714763a72b7d"},
            {"id": "b830f77b-cb54-431d-9bdb-0af9bc6af301"},
            {"id": "434e9a4b-018a-4557-8ca1-8c328bb1e09d"},
        ),
    ),
    (
        "driving",
        "Na estrada",
        (
            {"id": "d62fa52b-7c1c-492c-9861-cd2c0ec02f00"},
            {"name": "Rinse FM"},
            {"id": "edb81cbf-0645-4944-a376-554b8299ff27"},
            {"id": "1651c32f-55d8-4429-995d-872ea0dcf520"},
            {"id": "0957a107-50fc-435e-a402-ddfa5cdda777"},
            {"id": "961fe58c-0601-11e8-ae97-52543be04c81"},
            {"name": "Radio Paradise Main Mix"},
            {"name": "KEXP 90.3 Seattle"},
            {"id": "356a337d-4552-4b2d-bfdb-d381a6d85a9d"},
            {"name": "Triple J"},
        ),
    ),
    (
        "late_night",
        "Noite",
        (
            {"id": "960eb2e9-0601-11e8-ae97-52543be04c81"},
            {"name": "Dinamo.fm Sleep"},
            {"id": "0042e94c-55d6-4ff4-a3a7-46136e703424", "label": "SomaFM Deep Space One"},
            {"name": "Cryosleep"},
            {"id": "b69fe610-1522-47b1-a784-e7025d11f884"},
            {"id": "95277bca-2c9a-4c08-b2e7-0854e5793f8e"},
            {"id": "4b4d1308-9fdb-42a7-b92d-6370bc3284fe", "label": "Ambient Sleeping Pill"},
            {"name": "White Noise Radio"},
            {"name": "Pink Noise Radio"},
            {"name": "Brown Noise Radio"},
        ),
    ),
    (
        "workout",
        "Treino",
        (
            {"name": "BBC Radio 1 Dance (International)", "label": "BBC Radio 1 Dance"},
            {"id": "b8148b29-09d0-4aa1-8bfe-43d236260170"},
            {"id": "960cc332-0601-11e8-ae97-52543be04c81"},
            {"id": "2100610c-13c2-4536-879f-6a88ccb07dc8"},
            {"name": "Kool FM"},
            {"id": "a20e7f55-661e-4f4c-b87f-a087c64633f8"},
            {"id": "b294bf46-7c1d-45ba-b852-71c5b26298ac"},
            {"name": "Techno.FM"},
            {"id": "4a1bbe28-0675-43bb-98dc-fae037b0b026"},
            {"id": "6eef88eb-396c-4393-86aa-1ba04ff91918"},
        ),
    ),
)

_OFFLINE_REGISTRY = None


def log(message, level=None):
    if level is None:
        level = getattr(xbmc, "LOGINFO", 1)
    xbmc.log("[%s] %s" % (ADDON_ID, message), level)


def setting_int(key, default):
    try:
        return max(1, int(ADDON.getSetting(key) or default))
    except (TypeError, ValueError):
        return default


def page_size():
    return min(200, setting_int("page_size", 75))


def clean_text(value, fallback=""):
    value = value if value is not None else fallback
    value = str(value).replace("\r", " ").replace("\n", " ").strip()
    return " ".join(value.split())


def safe_label(value, limit=180):
    value = clean_text(value)
    return value[:limit] + ("…" if len(value) > limit else "")


def favorite_key(station):
    """Use the stream URL as the stable unique key for a saved radio."""
    return clean_text((station or {}).get("url"))


def normal_favorite(station):
    """Keep only the portable fields needed to replay a favorite station."""
    station = station or {}
    return {
        "name": safe_label(station.get("name") or "Rádio sem nome"),
        "url": favorite_key(station),
        "favicon": clean_text(station.get("favicon")),
        "country": safe_label(station.get("country")),
        "tags": safe_label(station.get("tags")),
    }


def load_favorites():
    """Load saved favorites safely; an invalid local file starts as empty."""
    try:
        with open(FAVORITES_PATH, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (IOError, OSError, ValueError):
        return []
    favorites = []
    seen = set()
    for item in data if isinstance(data, list) else []:
        favorite = normal_favorite(item)
        key = favorite_key(favorite)
        if key and key not in seen:
            favorites.append(favorite)
            seen.add(key)
    return favorites


def save_favorites(favorites):
    """Persist user favorites in the Kodi add-on profile directory."""
    folder = os.path.dirname(FAVORITES_PATH)
    try:
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        temporary_path = FAVORITES_PATH + ".tmp"
        with open(temporary_path, "w", encoding="utf-8") as stream:
            json.dump(favorites, stream, ensure_ascii=False, indent=2, sort_keys=True)
        try:
            os.replace(temporary_path, FAVORITES_PATH)
        except AttributeError:  # pragma: no cover - Kodi Python 2 compatibility only
            if os.path.exists(FAVORITES_PATH):
                os.remove(FAVORITES_PATH)
            os.rename(temporary_path, FAVORITES_PATH)
        return True
    except (IOError, OSError, ValueError) as error:
        log("Não foi possível guardar favoritos: %s" % error, getattr(xbmc, "LOGERROR", 4))
        return False


def is_favorite(station):
    key = favorite_key(station)
    return bool(key and any(favorite_key(item) == key for item in load_favorites()))


def add_favorite(station):
    favorite = normal_favorite(station)
    key = favorite_key(favorite)
    if not key:
        return False, "URL de emissão inválida."
    favorites = load_favorites()
    if any(favorite_key(item) == key for item in favorites):
        return True, "Esta rádio já está nos favoritos."
    favorites.append(favorite)
    return (True, "Adicionada aos favoritos.") if save_favorites(favorites) else (False, "Não foi possível guardar o favorito.")


def remove_favorite(station):
    key = favorite_key(station)
    favorites = [item for item in load_favorites() if favorite_key(item) != key]
    return (True, "Removida dos favoritos.") if save_favorites(favorites) else (False, "Não foi possível alterar os favoritos.")


def parse_params():
    if len(sys.argv) < 3 or not sys.argv[2]:
        return {}
    return {key: values[-1] for key, values in parse_qs(sys.argv[2].lstrip("?")).items() if values}


def build_url(action, **params):
    query = {"action": action}
    query.update({key: value for key, value in params.items() if value not in (None, "")})
    return "%s?%s" % (BASE_URL, urlencode(query))


def api_get(endpoint, params=None):
    """Return JSON from Radio Browser, or None after a recoverable failure."""
    url = "%s/%s" % (RADIO_BROWSER_BASE, endpoint.lstrip("/"))
    if params:
        url = "%s?%s" % (url, urlencode(params))
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        response = urlopen(request, timeout=15)
        try:
            payload = response.read().decode("utf-8")
        finally:
            response.close()
        value = json.loads(payload)
        return value if isinstance(value, list) else None
    except (HTTPError, URLError, ValueError, OSError) as error:
        log("Radio Browser indisponível: %s" % error, getattr(xbmc, "LOGWARNING", 2))
        return None


def load_offline_registry():
    """Load the registry bundled by Aerial v0.7.1 only when it is needed."""
    global _OFFLINE_REGISTRY
    if _OFFLINE_REGISTRY is not None:
        return _OFFLINE_REGISTRY
    try:
        with gzip.open(OFFLINE_REGISTRY_PATH, "rt", encoding="utf-8") as stream:
            data = json.load(stream)
        _OFFLINE_REGISTRY = data if isinstance(data, list) else []
        return _OFFLINE_REGISTRY
    except (IOError, OSError, ValueError) as error:
        log("Não foi possível carregar o catálogo local: %s" % error, getattr(xbmc, "LOGERROR", 4))
        _OFFLINE_REGISTRY = []
        return _OFFLINE_REGISTRY


def normalize_station(raw):
    """Normalize current Radio Browser and Aerial v0.7.1 registry schemas."""
    raw = raw or {}
    url = raw.get("url_resolved") or raw.get("stream_url") or raw.get("url") or ""
    return {
        "id": clean_text(raw.get("stationuuid") or raw.get("provider_id") or raw.get("id")),
        "name": safe_label(raw.get("name") or "Rádio sem nome"),
        "url": clean_text(url),
        "favicon": clean_text(raw.get("favicon") or raw.get("logo_url")),
        "country": safe_label(raw.get("country") or ""),
        "countrycode": clean_text(raw.get("countrycode") or raw.get("country_code")).upper(),
        "tags": safe_label(raw.get("tags") or ""),
        "codec": safe_label(raw.get("codec") or ""),
        "bitrate": clean_text(raw.get("bitrate") or ""),
        "homepage": clean_text(raw.get("homepage") or ""),
        "provider": clean_text(raw.get("provider") or ""),
    }


def tag_words(tags):
    return {word.strip().lower() for word in clean_text(tags).replace(",", " ").split() if word.strip()}


def offline_stations(name="", countrycode="", tag="", offset=0, limit=None):
    """Query the Aerial snapshot when the live directory is unavailable."""
    name = clean_text(name).lower()
    countrycode = clean_text(countrycode).upper()
    tag = clean_text(tag).lower()
    matches = []
    for raw in load_offline_registry():
        station = normalize_station(raw)
        if not station["url"]:
            continue
        if name and name not in station["name"].lower():
            continue
        if countrycode and station["countrycode"] != countrycode:
            continue
        if tag and tag not in tag_words(station["tags"]):
            continue
        matches.append(station)
    matches.sort(key=lambda station: station["name"].casefold())
    limit = limit or page_size()
    return matches[offset:offset + limit]


def live_or_offline_stations(name="", countrycode="", tag="", order="clickcount", offset=0):
    params = {
        "hidebroken": "true",
        "limit": str(page_size()),
        "offset": str(max(0, int(offset))),
        "order": order or "name",
        "reverse": "true" if order in ("clickcount", "clicktimestamp") else "false",
    }
    if name:
        params["name"] = name
    if countrycode:
        params["countrycode"] = countrycode
        params["countrycodeExact"] = "true"
    if tag:
        params["tag"] = tag
        params["tagExact"] = "true"
    data = api_get("stations/search", params)
    if data is not None:
        return [normalize_station(item) for item in data if normalize_station(item)["url"]], "live"
    return offline_stations(name, countrycode, tag, int(offset), page_size()), "offline"


def offline_countries():
    counts = Counter()
    names = {}
    for raw in load_offline_registry():
        station = normalize_station(raw)
        if station["countrycode"]:
            counts[station["countrycode"]] += 1
            names.setdefault(station["countrycode"], station["country"] or station["countrycode"])
    return [(code, names[code], counts[code]) for code in sorted(counts, key=lambda item: (-counts[item], names[item]))]


def offline_tags():
    counts = Counter()
    for raw in load_offline_registry():
        station = normalize_station(raw)
        for tag in tag_words(station["tags"]):
            if len(tag) >= 3:
                counts[tag] += 1
    return [(tag, counts[tag]) for tag in sorted(counts, key=lambda item: (-counts[item], item))]


def menu_art_path(art_key):
    filename = MENU_ART.get(art_key)
    return os.path.join(ADDON_PATH, "resources", "media", filename) if filename else DEFAULT_ICON_PATH


def add_folder(label, action, art_key=None, **params):
    art_path = menu_art_path(art_key or ACTION_ART.get(action))
    item = xbmcgui.ListItem(label=safe_label(label))
    item.setArt({"icon": art_path, "thumb": art_path, "poster": art_path, "fanart": FANART_PATH})
    item.setProperty("fanart_image", FANART_PATH)
    xbmcplugin.addDirectoryItem(HANDLE, build_url(action, **params), item, isFolder=True)


def add_station(station, label_override=None, in_favorites=False):
    station = station or {}
    label = safe_label(label_override or station.get("name") or "Rádio sem nome")
    stream_url = clean_text(station.get("url"))
    item = xbmcgui.ListItem(label=label, path=stream_url)
    item.setProperty("IsPlayable", "true")
    info = {
        "title": label,
        "genre": safe_label(station.get("tags")),
        "artist": safe_label(station.get("country")),
        "mediatype": "song",
    }
    codec = safe_label(station.get("codec"))
    bitrate = clean_text(station.get("bitrate"))
    if codec:
        info["comment"] = "%s%s" % (codec, (" · %s kbps" % bitrate) if bitrate else "")
    item.setInfo("music", info)
    art = {
        "icon": clean_text(station.get("favicon")) or DEFAULT_ICON_PATH,
        "thumb": clean_text(station.get("favicon")) or DEFAULT_ICON_PATH,
        "fanart": FANART_PATH,
    }
    item.setArt(art)
    item.setProperty("fanart_image", FANART_PATH)
    favorite = normal_favorite(station)
    favorite["name"] = label
    if in_favorites or is_favorite(favorite):
        menu_label = "Remover dos favoritos"
        menu_action = "favorite_remove"
    else:
        menu_label = "Adicionar aos favoritos"
        menu_action = "favorite_add"
    item.addContextMenuItems([(menu_label, "RunPlugin(%s)" % build_url(menu_action, **favorite))])
    xbmcplugin.addDirectoryItem(HANDLE, build_url("play", url=stream_url, title=label, thumb=station.get("favicon", ""), genre=station.get("tags", ""), country=station.get("country", "")), item, isFolder=False)


def finish(content="music"):
    set_plugin_fanart = getattr(xbmcplugin, "setPluginFanart", None)
    if callable(set_plugin_fanart):
        set_plugin_fanart(HANDLE, FANART_PATH)
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def root_directory():
    add_folder("Favoritos", "favorites", art_key="favorites")
    add_folder("Mais ouvidas agora", "stations", art_key="popular", order="clickcount")
    add_folder("Adicionadas recentemente", "stations", art_key="recent", order="clicktimestamp")
    add_folder("Catálogos temáticos Aerial", "moods", art_key="moods")
    add_folder("Rádios em português", "language_menu", art_key="portuguese")
    add_folder("Buscar por país", "country_search", art_key="country_search")
    add_folder("Por país", "countries", art_key="countries")
    add_folder("Por género / tema", "tags", art_key="genres")
    add_folder("Procurar no catálogo", "search", art_key="search")
    add_folder("Catálogo offline", "local_menu", art_key="local")
    finish("files")


def favorites_directory():
    favorites = load_favorites()
    if not favorites:
        xbmcgui.Dialog().notification(ADDON_NAME, "Ainda não há rádios favoritas.", xbmcgui.NOTIFICATION_INFO, 3500)
    for station in favorites:
        add_station(station, in_favorites=True)
    finish("songs")


def refresh_directory():
    refresh = getattr(xbmc, "executebuiltin", None)
    if callable(refresh):
        refresh("Container.Refresh")


def favorite_action(params, adding):
    station = normal_favorite(params)
    success, message = add_favorite(station) if adding else remove_favorite(station)
    icon = xbmcgui.NOTIFICATION_INFO if success else xbmcgui.NOTIFICATION_ERROR
    xbmcgui.Dialog().notification(ADDON_NAME, message, icon, 3500)
    if success:
        refresh_directory()
    finish("songs")


def station_directory(params):
    name = params.get("name", "")
    countrycode = params.get("countrycode", "")
    tag = params.get("tag", "")
    order = params.get("order", "clickcount")
    offset = int(params.get("offset", "0") or 0)
    stations, source = live_or_offline_stations(name, countrycode, tag, order, offset)
    if not stations:
        xbmcgui.Dialog().notification(ADDON_NAME, "Nenhuma rádio encontrada.", xbmcgui.NOTIFICATION_INFO, 4000)
    for station in stations:
        add_station(station)
    if len(stations) >= page_size():
        add_folder("Próxima página", "stations", name=name, countrycode=countrycode, tag=tag, order=order, offset=offset + page_size())
    if source == "offline":
        xbmcgui.Dialog().notification(ADDON_NAME, "A usar o catálogo offline.", xbmcgui.NOTIFICATION_INFO, 3500)
    finish("songs")


def mood_directory(params=None):
    params = params or {}
    mood_id = params.get("mood")
    if not mood_id:
        for identifier, label, _ in MOODS:
            add_folder(label, "moods", mood=identifier)
        finish("files")
        return
    mood = next((entry for entry in MOODS if entry[0] == mood_id), None)
    if not mood:
        root_directory()
        return
    registry = [normalize_station(raw) for raw in load_offline_registry()]
    by_id = {station["id"]: station for station in registry if station["id"]}
    for reference in mood[2]:
        station = by_id.get(reference.get("id", ""))
        if station is None and reference.get("name"):
            station = next((item for item in registry if item["name"].casefold() == reference["name"].casefold()), None)
        if station and station["url"]:
            add_station(station, reference.get("label"))
    finish("songs")


def available_countries():
    data = api_get("countries", {"order": "stationcount", "reverse": "true", "hidebroken": "true"})
    if data is not None:
        countries = []
        for item in data:
            code = clean_text(item.get("iso_3166_1") or item.get("countrycode")).upper()
            label = safe_label(item.get("name") or code)
            if code:
                countries.append((code, label, int(item.get("stationcount") or 0)))
    else:
        countries = offline_countries()
    return countries


def matching_countries(countries, query):
    query = clean_text(query).casefold()
    if not query:
        return countries
    return [
        (code, label, count)
        for code, label, count in countries
        if query in code.casefold() or query in label.casefold()
    ]


def add_country_folders(countries):
    for code, label, count in countries:
        add_folder("%s (%d)" % (label, count), "stations", art_key="countries", countrycode=code, order="clickcount")


def countries_directory(params=None):
    add_country_folders(available_countries())
    finish("files")


def country_search_directory():
    query = clean_text(xbmcgui.Dialog().input("Buscar país", type=xbmcgui.INPUT_ALPHANUM))
    if not query:
        root_directory()
        return
    matches = matching_countries(available_countries(), query)
    if not matches:
        xbmcgui.Dialog().notification(ADDON_NAME, "Nenhum país encontrado.", xbmcgui.NOTIFICATION_INFO, 4000)
    add_country_folders(matches)
    finish("files")


def tags_directory(params=None):
    data = api_get("tags", {"order": "stationcount", "reverse": "true", "limit": "250", "hidebroken": "true"})
    if data is not None:
        tags = []
        for item in data:
            label = safe_label(item.get("name"))
            if len(label) >= 3:
                tags.append((label, int(item.get("stationcount") or 0)))
    else:
        tags = offline_tags()[:250]
    for label, count in tags:
        add_folder("%s (%d)" % (label.title(), count), "stations", art_key="genres", tag=label, order="clickcount")
    finish("files")


def search_directory():
    query = xbmcgui.Dialog().input("Pesquisar rádios", type=xbmcgui.INPUT_ALPHANUM)
    query = clean_text(query)
    if query:
        station_directory({"name": query, "order": "clickcount"})
    else:
        root_directory()


def language_menu():
    add_folder("Brasil", "stations", art_key="portuguese", countrycode="BR", order="clickcount")
    add_folder("Portugal", "stations", art_key="portuguese", countrycode="PT", order="clickcount")
    add_folder("Angola", "stations", art_key="portuguese", countrycode="AO", order="clickcount")
    add_folder("Moçambique", "stations", art_key="portuguese", countrycode="MZ", order="clickcount")
    add_folder("Cabo Verde", "stations", art_key="portuguese", countrycode="CV", order="clickcount")
    add_folder("Guiné-Bissau", "stations", art_key="portuguese", countrycode="GW", order="clickcount")
    add_folder("São Tomé e Príncipe", "stations", art_key="portuguese", countrycode="ST", order="clickcount")
    finish("files")


def local_menu():
    add_folder("Destaques temáticos locais", "moods", art_key="moods")
    add_folder("Rádios locais por país", "local_countries", art_key="countries")
    add_folder("Rádios locais por tema", "local_tags", art_key="genres")
    add_folder("Pesquisar no catálogo local", "local_search", art_key="search")
    finish("files")


def local_countries_directory():
    for code, label, count in offline_countries():
        add_folder("%s (%d)" % (label, count), "local_stations", art_key="countries", countrycode=code)
    finish("files")


def local_tags_directory():
    for label, count in offline_tags()[:250]:
        add_folder("%s (%d)" % (label.title(), count), "local_stations", art_key="genres", tag=label)
    finish("files")


def local_station_directory(params):
    offset = int(params.get("offset", "0") or 0)
    stations = offline_stations(params.get("name", ""), params.get("countrycode", ""), params.get("tag", ""), offset, page_size())
    for station in stations:
        add_station(station)
    if len(stations) >= page_size():
        add_folder("Próxima página", "local_stations", name=params.get("name", ""), countrycode=params.get("countrycode", ""), tag=params.get("tag", ""), offset=offset + page_size())
    finish("songs")


def local_search_directory():
    query = clean_text(xbmcgui.Dialog().input("Pesquisar no catálogo Aerial", type=xbmcgui.INPUT_ALPHANUM))
    if query:
        local_station_directory({"name": query})
    else:
        local_menu()


def play(params):
    url = clean_text(params.get("url"))
    title = safe_label(params.get("title") or "Rádio")
    if not url:
        xbmcgui.Dialog().notification(ADDON_NAME, "URL de emissão inválida.", xbmcgui.NOTIFICATION_ERROR, 5000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    item = xbmcgui.ListItem(label=title, path=url)
    item.setProperty("IsPlayable", "true")
    item.setProperty("fanart_image", FANART_PATH)
    item.setProperty("Fanart_Image", FANART_PATH)
    item.setInfo("music", {"title": title, "genre": safe_label(params.get("genre", "")), "artist": safe_label(params.get("country", "")), "mediatype": "song"})
    thumb = clean_text(params.get("thumb"))
    item.setArt({
        "thumb": thumb or DEFAULT_ICON_PATH,
        "icon": thumb or DEFAULT_ICON_PATH,
        "fanart": FANART_PATH,
        "landscape": FANART_PATH,
    })
    xbmcplugin.setResolvedUrl(HANDLE, True, item)


def run():
    params = parse_params()
    action = params.get("action", "root")
    log("A iniciar ação: %s" % action)
    if action == "favorites":
        favorites_directory()
    elif action == "favorite_add":
        favorite_action(params, True)
    elif action == "favorite_remove":
        favorite_action(params, False)
    elif action == "stations":
        station_directory(params)
    elif action == "moods":
        mood_directory(params)
    elif action == "countries":
        countries_directory(params)
    elif action == "country_search":
        country_search_directory()
    elif action == "tags":
        tags_directory(params)
    elif action == "search":
        search_directory()
    elif action == "language_menu":
        language_menu()
    elif action == "local_menu":
        local_menu()
    elif action == "local_countries":
        local_countries_directory()
    elif action == "local_tags":
        local_tags_directory()
    elif action == "local_stations":
        local_station_directory(params)
    elif action == "local_search":
        local_search_directory()
    elif action == "play":
        play(params)
    else:
        root_directory()


if __name__ == "__main__":
    run()
