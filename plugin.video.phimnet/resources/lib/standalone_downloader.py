# -*- coding: utf-8 -*-

"""Downloader riêng của addon, không phụ thuộc addon khác."""

import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcgui
import xbmcvfs


VIDEO_EXTENSIONS = {
    ".3gp", ".avi", ".flv", ".m2ts", ".m4v", ".mkv", ".mov",
    ".mp4", ".mpeg", ".mpg", ".mts", ".ts", ".webm", ".wmv",
}


class DownloadError(RuntimeError):
    pass


def _join(directory, name):
    return directory.rstrip("/\\") + "/" + name


def _clean_file_name(value):
    value = urllib.parse.unquote(str(value or ""))
    value = re.sub(r"\[/?COLOR(?:\s+[^\]]+)?\]", "", value, flags=re.I)
    value = os.path.basename(value.replace("\\", "/"))
    value = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", value).strip(" .")
    if len(value) > 180:
        stem, extension = os.path.splitext(value)
        value = stem[:max(1, 180 - len(extension))] + extension
    return value or "video"


def _server_file_name(headers):
    disposition = str(headers.get("Content-Disposition") or "")
    match = re.search(r"filename\*=UTF-8''([^;]+)", disposition, flags=re.I)
    if match:
        return urllib.parse.unquote(match.group(1).strip())
    match = re.search(r'filename="?([^";]+)', disposition, flags=re.I)
    return match.group(1).strip() if match else ""


def _extension(preferred_name, url, headers):
    candidates = (
        preferred_name,
        _server_file_name(headers),
        urllib.parse.urlparse(url).path.rsplit("/", 1)[-1],
    )
    for candidate in candidates:
        extension = os.path.splitext(
            urllib.parse.unquote(str(candidate or ""))
        )[1].lower()
        if extension in VIDEO_EXTENSIONS:
            return extension
    content_type = str(headers.get("Content-Type") or "").lower().split(";", 1)[0]
    return {
        "video/mp4": ".mp4",
        "video/x-matroska": ".mkv",
        "video/webm": ".webm",
        "video/mp2t": ".ts",
        "application/octet-stream": ".mkv",
    }.get(content_type, ".mp4")


def _format_size(value):
    value = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return "{:.1f} {}".format(value, unit)
        value /= 1024.0


def get_download_directory(addon, addon_id):
    configured = str(addon.getSetting("download_path") or "").strip()
    if not configured:
        configured = "special://profile/addon_data/{}/downloads/".format(addon_id)
    directory = xbmcvfs.translatePath(configured)
    if not xbmcvfs.exists(directory) and not xbmcvfs.mkdirs(directory):
        raise DownloadError("Không tạo được thư mục tải xuống: {}".format(directory))
    return directory


def list_downloaded_files(addon, addon_id):
    directory = get_download_directory(addon, addon_id)
    _directories, files = xbmcvfs.listdir(directory)
    results = []
    for name in sorted(files, key=lambda value: value.casefold()):
        if name.lower().endswith(".part"):
            continue
        path = _join(directory, name)
        try:
            size = xbmcvfs.Stat(path).st_size()
        except Exception:
            size = 0
        results.append((path, name, size))
    return directory, results


def download_stream(addon, addon_id, addon_name, url, preferred_name, headers=None):
    if urllib.parse.urlparse(str(url or "")).scheme not in ("http", "https"):
        raise DownloadError("Link tải xuống không hợp lệ")

    directory = get_download_directory(addon, addon_id)
    request_headers = {
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "User-Agent": "Mozilla/5.0 (Kodi; {})".format(addon_name),
    }
    if headers:
        request_headers.update({str(key): str(value) for key, value in headers.items()})

    progress = xbmcgui.DialogProgress()
    progress.create(addon_name, "Đang kết nối máy chủ…")
    response = None
    output = None
    temporary_path = ""
    try:
        request = urllib.request.Request(url, headers=request_headers, method="GET")
        response = urllib.request.urlopen(request, timeout=30)
        response_headers = response.headers
        if str(response_headers.get("X-Proxy-Source") or "").lower() == "demo-proxy":
            raise DownloadError("Máy chủ đang trả clip demo, không phải file phim thật")

        final_url = response.geturl() or url
        file_name = _clean_file_name(preferred_name)
        if os.path.splitext(file_name)[1].lower() not in VIDEO_EXTENSIONS:
            file_name += _extension(file_name, final_url, response_headers)
        destination = _join(directory, file_name)
        temporary_path = destination + ".part"

        if xbmcvfs.exists(destination) and not xbmcgui.Dialog().yesno(
            addon_name,
            "Tệp đã tồn tại:\n{}\n\nBạn có muốn tải lại không?".format(file_name),
        ):
            return False

        try:
            total = int(response_headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            total = 0

        output = xbmcvfs.File(temporary_path, "w")
        downloaded = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            downloaded += len(chunk)
            percent = min(100, int(downloaded * 100 / total)) if total else 0
            progress.update(
                percent,
                "Đã tải {}{}".format(
                    _format_size(downloaded),
                    " / {}".format(_format_size(total)) if total else "",
                ),
            )
            if progress.iscanceled():
                raise DownloadError("Đã hủy tải xuống")

        output.close()
        output = None
        if downloaded <= 0:
            raise DownloadError("Máy chủ không trả dữ liệu phim")
        if total and downloaded != total:
            raise DownloadError(
                "Tệp tải chưa đủ: {} / {}".format(
                    _format_size(downloaded), _format_size(total)
                )
            )

        if xbmcvfs.exists(destination):
            xbmcvfs.delete(destination)
        moved = xbmcvfs.rename(temporary_path, destination)
        if not moved and not xbmcvfs.exists(destination):
            if not xbmcvfs.copy(temporary_path, destination):
                raise DownloadError("Không lưu được tệp vào thư mục tải xuống")
            xbmcvfs.delete(temporary_path)

        xbmcgui.Dialog().notification(
            addon_name,
            "Tải xong: {}".format(file_name),
            xbmcgui.NOTIFICATION_INFO,
            6000,
        )
        return True
    except urllib.error.HTTPError as exc:
        message = "Máy chủ từ chối tải xuống (HTTP {})".format(exc.code)
        xbmc.log("[{}] {}".format(addon_id, message), xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            addon_name, message, xbmcgui.NOTIFICATION_ERROR, 7000
        )
        return False
    except (urllib.error.URLError, socket.timeout, OSError, DownloadError) as exc:
        message = str(getattr(exc, "reason", None) or exc)
        xbmc.log("[{}] Download error: {}".format(addon_id, message), xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            addon_name, message, xbmcgui.NOTIFICATION_ERROR, 7000
        )
        return False
    finally:
        if output is not None:
            output.close()
        if response is not None:
            response.close()
        if temporary_path and xbmcvfs.exists(temporary_path):
            xbmcvfs.delete(temporary_path)
        progress.close()
