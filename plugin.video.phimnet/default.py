# -*- coding: utf-8 -*-

import os
import sys
from urllib.parse import parse_qsl, urlencode, urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs


ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
ADDON_PATH = ADDON.getAddonInfo("path")
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]

LIB_DIR = os.path.join(ADDON_PATH, "resources", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from phimnet_api import ApiError, PhimNetApi, USER_AGENT  # noqa: E402
from standalone_downloader import (  # noqa: E402
    DownloadError,
    download_stream,
    list_downloaded_files,
)


ICON = os.path.join(ADDON_PATH, "resources", "media", "icon-phimnet-v2.png")
FANART = os.path.join(ADDON_PATH, "resources", "media", "fanart-phimnet-v2.png")
PROFILE_DIR = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
DYNAMIC_CONFIG = os.path.join(PROFILE_DIR, "dynamic_config.json")
SOURCE_BADGE = "[COLOR yellow][NÉT][/COLOR] "


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[%s] %s" % (ADDON_ID, message), level)


def notify(message):
    xbmcgui.Dialog().notification(ADDON_NAME, message, xbmcgui.NOTIFICATION_INFO, 4500)


def client():
    return PhimNetApi(timeout=25, config_path=DYNAMIC_CONFIG)


def plugin_url(**kwargs):
    clean = {key: str(value) for key, value in kwargs.items() if value not in (None, "")}
    return BASE_URL + "?" + urlencode(clean)

def add_download_context(item, **params):
    item.addContextMenuItems([
        (
            "[COLOR yellow]Download phim[/COLOR]",
            "RunPlugin({})".format(plugin_url(**params)),
        )
    ])


def download_with_phimnet(stream_url, file_name):
    return download_stream(
        ADDON,
        ADDON_ID,
        ADDON_NAME,
        stream_url,
        file_name,
        headers={"User-Agent": USER_AGENT},
    )


def as_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def art_for(movie=None):
    movie = movie or {}
    poster = movie.get("poster") or ICON
    fanart = movie.get("fanart") or FANART
    return {
        "icon": poster,
        "thumb": poster,
        "poster": poster,
        "fanart": fanart,
    }


def set_video_info(item, movie, title=None, episode=None):
    rating = movie.get("rating") or 0
    try:
        rating = float(rating)
    except Exception:
        rating = 0
    info = {
        "title": title or movie.get("title") or "Phim Nét",
        "plot": movie.get("plot") or "",
        "year": movie.get("year") or 0,
        "genre": movie.get("genre") or "",
        "country": movie.get("country") or "",
        "director": movie.get("director") or "",
        "duration": movie.get("duration") or 0,
        "rating": rating,
        "studio": "Server Nét",
        "mediatype": "episode" if episode else movie.get("mediatype") or "movie",
    }
    if episode:
        info["season"] = episode.get("season_number") or 0
        info["episode"] = episode.get("episode_number") or 0
        info["tvshowtitle"] = movie.get("title") or ""
    item.setInfo("video", info)


def add_folder(label, url, movie=None, plot=""):
    item = xbmcgui.ListItem(label=label)
    art = art_for(movie)
    item.setArt(art)
    item.setProperty("Fanart_Image", art["fanart"])
    if movie:
        set_video_info(item, movie)
    elif plot:
        item.setInfo("video", {"title": label, "plot": plot})
    xbmcplugin.addDirectoryItem(HANDLE, url, item, isFolder=True)


def movie_label(movie):
    details = []
    if movie.get("quality"):
        details.append(movie["quality"])
    if movie.get("year"):
        details.append(str(movie["year"]))
    if movie.get("paid"):
        details.append("VIP")
    suffix = " [COLOR gray](%s)[/COLOR]" % " • ".join(details) if details else ""
    kind = "[COLOR deepskyblue][BỘ][/COLOR] " if movie.get("type") == "tvseries" else ""
    return SOURCE_BADGE + kind + movie.get("title", "Không rõ tên") + suffix


def add_movie(movie):
    if not movie.get("id"):
        return
    item = xbmcgui.ListItem(label=movie_label(movie))
    art = art_for(movie)
    item.setArt(art)
    item.setProperty("Fanart_Image", art["fanart"])
    set_video_info(item, movie)
    if movie.get("type") == "tvseries":
        url = plugin_url(action="episodes", content_type="tvseries", movie_id=movie["id"])
        xbmcplugin.addDirectoryItem(HANDLE, url, item, isFolder=True)
    else:
        item.setProperty("IsPlayable", "true")
        url = plugin_url(action="choose", content_type="movie", movie_id=movie["id"])
        add_download_context(
            item,
            action="choose_download",
            content_type="movie",
            movie_id=movie["id"],
        )
        xbmcplugin.addDirectoryItem(HANDLE, url, item, isFolder=False)


def end_directory(content="movies"):
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True, cacheToDisc=False)


def main_menu():
    add_folder("[COLOR yellow]Server Nét - Phim mới cập nhật[/COLOR]", plugin_url(action="list", list_type="latest", page=1))
    add_folder("Phim lẻ Server Nét", plugin_url(action="list", list_type="movies", page=1))
    add_folder("Phim bộ Server Nét", plugin_url(action="list", list_type="tvseries", page=1))
    add_folder("Thể loại", plugin_url(action="taxonomies", kind="genre"))
    add_folder("Quốc gia", plugin_url(action="taxonomies", kind="country"))
    add_folder("[COLOR deepskyblue]Tìm kiếm Server Nét[/COLOR]", plugin_url(action="search"))
    add_folder(
        "[COLOR yellow]Thư mục tải xuống[/COLOR]",
        plugin_url(action="downloads"),
    )
    end_directory("videos")


def format_file_size(value):
    value = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return "{:.1f} {}".format(value, unit)
        value /= 1024.0


def downloads_menu():
    xbmcplugin.setPluginCategory(HANDLE, "Phim Nét - Tải xuống")
    directory, files = list_downloaded_files(ADDON, ADDON_ID)
    settings_item = xbmcgui.ListItem(
        label="[COLOR yellow]Chọn thư mục lưu phim[/COLOR]"
    )
    settings_item.setArt({"icon": ICON, "thumb": ICON})
    xbmcplugin.addDirectoryItem(
        HANDLE,
        plugin_url(action="download_settings"),
        settings_item,
        isFolder=False,
    )
    for path, name, size in files:
        label = name
        if size:
            label += " [COLOR gray]({})[/COLOR]".format(format_file_size(size))
        item = xbmcgui.ListItem(label=label, path=path)
        item.setProperty("IsPlayable", "true")
        item.setInfo("video", {"title": name, "mediatype": "movie"})
        item.setContentLookup(False)
        xbmcplugin.addDirectoryItem(HANDLE, path, item, isFolder=False)
    if not files:
        notify("Chưa có phim tải xuống trong {}".format(directory))
    end_directory("videos")


def open_download_settings():
    ADDON.openSettings()
    xbmc.executebuiltin("Container.Refresh")


def show_movies(movies, page, has_more, next_url=None):
    for movie in movies:
        add_movie(movie)
    if has_more and next_url:
        add_folder("[COLOR yellow]Trang tiếp theo (%s) »[/COLOR]" % (page + 1), next_url)
    if not movies:
        notify("Không tìm thấy phim trên Server Nét")
    end_directory("movies")


def list_movies(params):
    list_type = params.get("list_type", "latest")
    page = max(1, as_int(params.get("page"), 1))
    movies, has_more = client().list_movies(list_type, page)
    next_url = plugin_url(action="list", list_type=list_type, page=page + 1)
    show_movies(movies, page, has_more, next_url)


def taxonomies(params):
    kind = params.get("kind", "genre")
    for entry in client().taxonomies(kind):
        add_folder(
            entry["name"],
            plugin_url(action="taxonomy_movies", kind=kind, entry_id=entry["id"], page=1),
            plot=entry.get("plot") or "",
        )
    end_directory("videos")


def taxonomy_movies(params):
    kind = params.get("kind", "genre")
    entry_id = params.get("entry_id", "")
    page = max(1, as_int(params.get("page"), 1))
    movies, has_more = client().taxonomy_movies(kind, entry_id, page)
    next_url = plugin_url(action="taxonomy_movies", kind=kind, entry_id=entry_id, page=page + 1)
    show_movies(movies, page, has_more, next_url)


def search(params):
    keyword = params.get("keyword", "").strip()
    if not keyword:
        keyword = xbmcgui.Dialog().input("Nhập tên phim cần tìm", type=xbmcgui.INPUT_ALPHANUM).strip()
    if not keyword:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False, cacheToDisc=False)
        return
    page = max(1, as_int(params.get("page"), 1))
    movies, has_more = client().search(keyword, page)
    next_url = plugin_url(action="search", keyword=keyword, page=page + 1)
    show_movies(movies, page, has_more, next_url)


def block_paid(movie):
    if not movie.get("paid"):
        return False
    notify("Phim VIP cần tài khoản thuê bao đang hoạt động trong ứng dụng gốc")
    return True


def choose(params, download_only=False):
    api = client()
    movie, detail = api.detail("movie", params.get("movie_id", ""))
    if block_paid(movie):
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    variants = api.movie_variants(detail)
    if not variants:
        raise ApiError("Phim này chưa có bản phát trên Server Nét")
    labels = [SOURCE_BADGE + variant["label"] for variant in variants]
    selected = xbmcgui.Dialog().select("Chọn bản phim / dung lượng Server Nét", labels)
    if selected < 0:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    variant = variants[selected]
    if download_only:
        resolve_download(
            api,
            variant["url"],
            movie["title"],
            variant["label"],
        )
    else:
        resolve_play(
            api,
            variant["url"],
            movie["title"],
            variant["label"],
            variant.get("file_type"),
        )


def episodes(params):
    api = client()
    movie, detail = api.detail("tvseries", params.get("movie_id", ""))
    if block_paid(movie):
        end_directory("episodes")
        return
    entries = api.tv_episodes(detail)
    for episode in entries:
        label = "%s[COLOR yellow]%s[/COLOR] — %s" % (SOURCE_BADGE, episode["season"], episode["name"])
        item = xbmcgui.ListItem(label=label)
        art = art_for(movie)
        if episode.get("thumb"):
            art["thumb"] = episode["thumb"]
            art["icon"] = episode["thumb"]
        item.setArt(art)
        item.setProperty("Fanart_Image", art["fanart"])
        item.setProperty("IsPlayable", "true")
        set_video_info(item, movie, "%s - %s" % (movie["title"], episode["name"]), episode=episode)
        url = plugin_url(
            action="play",
            url=episode["url"],
            title=movie["title"],
            label="%s — %s" % (episode["season"], episode["name"]),
            file_type=episode.get("file_type"),
        )
        add_download_context(
            item,
            action="download",
            url=episode["url"],
            title=movie["title"],
            label="%s — %s" % (episode["season"], episode["name"]),
        )
        xbmcplugin.addDirectoryItem(HANDLE, url, item, isFolder=False)
    if not entries:
        notify("Phim bộ này chưa có tập trên Server Nét")
    end_directory("episodes")


def resolve_play(api, source_url, title, label="", file_type=""):
    resolved = api.resolve_stream_url(source_url)
    # Keep byte offsets stable through HTTP proxies. The signed media worker
    # serves direct files as chunked responses but still honours Range.
    #
    # FFmpeg Direct maps the reconnect options below to libavformat. Railway
    # workers occasionally close a long response before the movie is over;
    # without these options FFmpeg reports a normal EOF and Kodi closes the
    # player. Reconnecting at EOF makes FFmpeg issue a new byte-range request
    # from the current offset instead, while preserving seek support.
    headers = urlencode({
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "seekable": "1",
        "reconnect": "1",
        "reconnect_at_eof": "1",
        "reconnect_streamed": "1",
        "reconnect_delay_max": "15",
    })
    kodi_url = resolved + "|" + headers
    item = xbmcgui.ListItem(label=(title + " - " + label).strip(" -"), path=kodi_url)
    item.setProperty("IsPlayable", "true")
    extension = urlparse(resolved).path.lower()
    is_hls = extension.endswith(".m3u8") or str(file_type).lower() in ("hls", "m3u8")
    if is_hls:
        mime_type = "application/vnd.apple.mpegurl"
    elif extension.endswith(".mp4"):
        mime_type = "video/mp4"
    elif (
        extension.endswith(".mkv")
        or str(file_type).lower() == "mkv"
        or ".mkv" in label.lower()
    ):
        mime_type = "video/x-matroska"
    else:
        mime_type = "video/mp4"
    item.setMimeType(mime_type)

    if not is_hls:
        # The worker omits Content-Length on its initial chunked response. Kodi's
        # native cURL reader then exposes the file as non-seekable even though
        # later byte-range requests return Content-Range. FFmpeg Direct opens the
        # VOD with libavformat, learns the real size and restores timeline seek.
        # This is the actual binary add-on id; the old "inputstream.ffmpeg" value
        # used by 1.0.9/1.0.10 was not valid on Kodi 21.
        item.setProperty("inputstream", "inputstream.ffmpegdirect")
        item.setProperty("inputstream.ffmpegdirect.open_mode", "ffmpeg")
        item.setProperty("inputstream.ffmpegdirect.is_realtime_stream", "false")
        item.setProperty("inputstream.ffmpegdirect.mime_type", mime_type)

    item.setContentLookup(False)
    item.setInfo("video", {"title": title, "plot": label, "mediatype": "movie"})
    xbmcplugin.setResolvedUrl(HANDLE, True, item)


def resolve_download(api, source_url, title, label=""):
    resolved = api.resolve_stream_url(source_url)
    file_name = (title + " - " + label).strip(" -")
    download_with_phimnet(resolved, file_name or "Phim Nét")


def play(params):
    resolve_play(
        client(),
        params.get("url", ""),
        params.get("title", "Phim Nét"),
        params.get("label", ""),
        params.get("file_type", ""),
    )


def download(params):
    resolve_download(
        client(),
        params.get("url", ""),
        params.get("title", "Phim Nét"),
        params.get("label", ""),
    )


def route():
    raw = sys.argv[2][1:] if len(sys.argv) > 2 and sys.argv[2].startswith("?") else ""
    params = dict(parse_qsl(raw))
    action = params.get("action", "root")
    try:
        if action == "root":
            main_menu()
        elif action == "list":
            list_movies(params)
        elif action == "taxonomies":
            taxonomies(params)
        elif action == "taxonomy_movies":
            taxonomy_movies(params)
        elif action == "search":
            search(params)
        elif action == "choose":
            choose(params)
        elif action == "choose_download":
            choose(params, download_only=True)
        elif action == "episodes":
            episodes(params)
        elif action == "play":
            play(params)
        elif action == "download":
            download(params)
        elif action == "downloads":
            downloads_menu()
        elif action == "download_settings":
            open_download_settings()
        else:
            raise ApiError("Chức năng Phim Nét không hợp lệ")
    except (ApiError, DownloadError) as exc:
        log(str(exc), xbmc.LOGERROR)
        notify(str(exc))
        if action in ("choose", "play"):
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        elif action not in ("choose_download", "download"):
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False, cacheToDisc=False)
    except Exception as exc:
        log("Unhandled error: %s" % exc, xbmc.LOGERROR)
        notify("Lỗi Phim Nét: %s" % exc)
        if action in ("choose", "play"):
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        elif action not in ("choose_download", "download"):
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False, cacheToDisc=False)


if __name__ == "__main__":
    route()
