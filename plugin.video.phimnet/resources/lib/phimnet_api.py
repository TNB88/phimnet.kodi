# -*- coding: utf-8 -*-

import base64
import hashlib
import hmac
import html
import json
import os
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from aesgcm import decrypt as aes_gcm_decrypt
from aesgcm import encrypt as aes_gcm_encrypt


DEFAULT_API_HOST = "aa.maclife.dpdns.org"
DEFAULT_RESOLVER_HOST = "sv1.maclife.dpdns.org"
API_KEY = "bbbb411dea44849"
API_BASIC = base64.b64encode(b"admin:1234").decode("ascii")
HMAC_SECRET = "5e8d1b4f9c2a6e730b1f8d4a92c5e3d1"
USER_AGENT = "Mozilla/5.0 (Android; PhimNetClient/1.0)"
CONFIG_USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 13; PhimNetKodi)"
CONFIG_SECRET = "8zP2mN7xR4vW9bQ1eC5yU0sI6tO3pA4f"
CONFIG_URLS = (
    "https://ltv.cryboiz.workers.dev/api/add",
    "https://raw.githubusercontent.com/TNB88/phimnet.kodi/main/config.json",
)
PAGE_SIZE = 24


class ApiError(RuntimeError):
    pass


class DemoStreamError(ApiError):
    pass


def _clean_text(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n", value)
    return value.strip()


def _names(value):
    if not isinstance(value, list):
        return _clean_text(value)
    names = []
    for item in value:
        if isinstance(item, dict):
            name = item.get("name") or item.get("title") or ""
        else:
            name = item
        name = _clean_text(name)
        if name:
            names.append(name)
    return " / ".join(names)


def _year(item):
    release = _clean_text(item.get("release"))
    match = re.search(r"(?:19|20)\d{2}", release or _clean_text(item.get("title")))
    return int(match.group(0)) if match else 0


def _duration_seconds(value):
    value = _clean_text(value).lower()
    if not value:
        return 0
    hours = re.search(r"(\d+)\s*(?:h|giờ)", value)
    minutes = re.search(r"(\d+)\s*(?:m|phút)", value)
    if hours or minutes:
        return (int(hours.group(1)) if hours else 0) * 3600 + (int(minutes.group(1)) if minutes else 0) * 60
    if value.isdigit():
        return int(value) * 60
    return 0


def normalize_movie(item, type_hint=""):
    item = item or {}
    media_type = "tvshow" if type_hint == "tvseries" or str(item.get("is_tvseries")) == "1" else "movie"
    movie_id = str(item.get("videos_id") or item.get("id") or "").strip()
    return {
        "id": movie_id,
        "title": _clean_text(item.get("title")) or "Không rõ tên",
        "plot": _clean_text(item.get("description")),
        "slug": _clean_text(item.get("slug")),
        "year": _year(item),
        "release": _clean_text(item.get("release")),
        "duration": _duration_seconds(item.get("runtime")),
        "runtime": _clean_text(item.get("runtime")),
        "quality": _clean_text(item.get("video_quality")),
        "rating": item.get("imdb_rating") or 0,
        "poster": _clean_text(item.get("thumbnail_url")) or _clean_text(item.get("poster_url")),
        "fanart": _clean_text(item.get("poster_url")) or _clean_text(item.get("thumbnail_url")),
        "genre": _names(item.get("genre")),
        "country": _names(item.get("country")),
        "director": _names(item.get("director")),
        "mediatype": media_type,
        "type": "tvseries" if media_type == "tvshow" else "movie",
        "paid": str(item.get("is_paid") or "0") == "1",
    }


class PhimNetApi(object):
    def __init__(self, timeout=25, config_path=""):
        self.timeout = timeout
        self._signing_cache = {}
        self._server_time_offset = 0.0
        self.config_path = config_path
        self.api_host = DEFAULT_API_HOST
        self.resolver_host = DEFAULT_RESOLVER_HOST
        self.api_key = API_KEY
        self._load_dynamic_config()

    @property
    def api_base(self):
        return "https://%s/rest-api/v130/" % self.api_host

    @property
    def resolver_base(self):
        return "https://%s/" % self.resolver_host

    @staticmethod
    def _normalize_host(value):
        value = str(value or "").strip()
        if not value:
            return ""
        parsed = urlparse(value if "://" in value else "https://" + value)
        host = (parsed.hostname or "").strip().lower()
        if not host or not re.match(r"^[a-z0-9.-]+$", host) or "." not in host:
            return ""
        return host

    @staticmethod
    def _decode_urlsafe(value):
        value = str(value or "").strip()
        return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))

    def _parse_dynamic_config(self, payload):
        root = json.loads(payload) if isinstance(payload, str) else payload
        if not isinstance(root, dict):
            raise ValueError("Dynamic config is not an object")
        if root.get("iv") and root.get("ciphertext"):
            key = hashlib.sha256(CONFIG_SECRET.encode("utf-8")).digest()
            decrypted = aes_gcm_decrypt(
                key,
                self._decode_urlsafe(root["iv"]),
                self._decode_urlsafe(root["ciphertext"]),
            )
            root = json.loads(decrypted.decode("utf-8"))
        data = root.get("data") if isinstance(root, dict) else None
        return data if isinstance(data, dict) else root

    def _apply_dynamic_config(self, data):
        if not isinstance(data, dict):
            return False
        api_host = self._normalize_host(data.get("api"))
        resolver_host = self._normalize_host(data.get("cdn"))
        if not api_host or not resolver_host:
            return False
        self.api_host = api_host
        self.resolver_host = resolver_host
        token = str(data.get("tokens") or "").strip()
        if re.match(r"^[A-Za-z0-9_-]{8,128}$", token):
            self.api_key = token
        return True

    def _read_cached_config(self):
        if not self.config_path or not os.path.isfile(self.config_path):
            return None
        try:
            with open(self.config_path, "r", encoding="utf-8") as stream:
                return json.load(stream)
        except (OSError, ValueError):
            return None

    def _write_cached_config(self):
        if not self.config_path:
            return
        try:
            folder = os.path.dirname(self.config_path)
            if folder and not os.path.isdir(folder):
                os.makedirs(folder)
            with open(self.config_path, "w", encoding="utf-8") as stream:
                json.dump({"api": self.api_host, "cdn": self.resolver_host}, stream)
        except OSError:
            pass

    def _load_dynamic_config(self):
        headers = {"User-Agent": CONFIG_USER_AGENT, "Accept": "application/json"}
        for url in CONFIG_URLS:
            try:
                with urlopen(Request(url, headers=headers), timeout=min(self.timeout, 10)) as response:
                    payload = response.read().decode("utf-8", "replace")
                if self._apply_dynamic_config(self._parse_dynamic_config(payload)):
                    self._write_cached_config()
                    return
            except (HTTPError, URLError, ValueError, KeyError, TypeError):
                continue
        self._apply_dynamic_config(self._read_cached_config())

    def _capture_server_time(self, headers):
        """Use the server Date header so a Kodi box with a bad clock can still sign."""
        if not headers:
            return
        try:
            values = headers.get_all("Date") or []
        except AttributeError:
            values = []
        if not values:
            value = headers.get("Date")
            values = [value] if value else []
        for value in reversed(values):
            try:
                server_time = parsedate_to_datetime(value)
                self._server_time_offset = server_time.timestamp() - time.time()
                return
            except (TypeError, ValueError, OverflowError):
                continue

    def _now(self):
        return time.time() + self._server_time_offset

    def _headers(self):
        return {
            "API-KEY": self.api_key,
            "Authorization": "Basic " + API_BASIC,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

    def _json(self, path_or_url, query=None, authenticated=True):
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            url = path_or_url
        else:
            url = self.api_base + path_or_url.lstrip("/")
        if query:
            url += ("&" if "?" in url else "?") + urlencode(query)
        headers = self._headers() if authenticated else {"User-Agent": USER_AGENT, "Accept": "application/json"}
        try:
            with urlopen(Request(url, headers=headers), timeout=self.timeout) as response:
                self._capture_server_time(response.headers)
                payload = response.read().decode("utf-8", "replace")
            return json.loads(payload)
        except HTTPError as exc:
            raise ApiError("Server Nét báo lỗi HTTP %s" % getattr(exc, "code", ""))
        except URLError as exc:
            raise ApiError("Không kết nối được Server Nét: %s" % getattr(exc, "reason", exc))
        except ValueError:
            raise ApiError("Server Nét trả dữ liệu không hợp lệ")

    def list_movies(self, list_type, page=1):
        page = max(1, int(page))
        if list_type == "tvseries":
            path = "tvseries"
            hint = "tvseries"
            query = {"page": page}
        elif list_type == "latest":
            path = "latest_movies"
            hint = "movie"
            query = {"limit": PAGE_SIZE, "page": page}
        else:
            path = "movies"
            hint = "movie"
            query = {"page": page}
        data = self._json(path, query)
        items = data if isinstance(data, list) else []
        return [normalize_movie(item, hint) for item in items], len(items) >= PAGE_SIZE

    def search(self, keyword, page=1):
        keyword = _clean_text(keyword)
        if not keyword:
            return [], False
        results = []
        has_more = False
        for search_type, field in (("movie", "movie"), ("tvseries", "tvseries")):
            data = self._json("search", {"q": keyword, "page": max(1, int(page)), "type": search_type})
            items = data.get(field) if isinstance(data, dict) else []
            items = items if isinstance(items, list) else []
            results.extend(normalize_movie(item, search_type) for item in items)
            has_more = has_more or len(items) >= PAGE_SIZE
        seen = set()
        unique = []
        for movie in results:
            key = (movie.get("type"), movie.get("id"))
            if not movie.get("id") or key in seen:
                continue
            seen.add(key)
            unique.append(movie)
        return unique, has_more

    def taxonomies(self, kind):
        path = "all_country" if kind == "country" else "all_genre"
        id_key = "country_id" if kind == "country" else "genre_id"
        data = self._json(path)
        entries = []
        for item in data if isinstance(data, list) else []:
            entry_id = str(item.get(id_key) or item.get("id") or "").strip()
            name = _clean_text(item.get("name"))
            if entry_id and name:
                entries.append({"id": entry_id, "name": name, "plot": _clean_text(item.get("description"))})
        return entries

    def taxonomy_movies(self, kind, entry_id, page=1):
        path = "content_by_country_id" if kind == "country" else "content_by_genre_id"
        data = self._json(path, {"id": entry_id, "page": max(1, int(page))})
        items = data if isinstance(data, list) else []
        movies = [normalize_movie(item, "tvseries" if str(item.get("is_tvseries")) == "1" else "movie") for item in items]
        return movies, len(items) >= PAGE_SIZE

    def detail(self, content_type, movie_id):
        content_type = "tvseries" if content_type == "tvseries" else "movie"
        data = self._json("single_details", {"type": content_type, "id": movie_id})
        if not isinstance(data, dict) or not data.get("videos_id"):
            raise ApiError("Không lấy được chi tiết phim từ Server Nét")
        return normalize_movie(data, content_type), data

    @staticmethod
    def movie_variants(detail):
        variants = []
        for video in detail.get("videos") or []:
            file_type = _clean_text(video.get("file_type")).lower()
            url = _clean_text(video.get("file_url"))
            if not url or file_type == "embed":
                continue
            variants.append({
                "id": str(video.get("video_file_id") or ""),
                "label": _clean_text(video.get("label")) or "Bản Server Nét",
                "url": url,
                "file_type": file_type or "mp4",
                "subtitles": video.get("subtitle") or [],
            })
        return variants

    @staticmethod
    def tv_episodes(detail):
        episodes = []
        for season_index, season in enumerate(detail.get("season") or [], 1):
            season_name = _clean_text(season.get("seasons_name")) or "Phần %s" % season_index
            for episode_index, episode in enumerate(season.get("episodes") or [], 1):
                url = _clean_text(episode.get("file_url"))
                if not url:
                    continue
                name = _clean_text(episode.get("episodes_name")) or "Tập %s" % episode_index
                episodes.append({
                    "id": str(episode.get("episodes_id") or ""),
                    "season": season_name,
                    "season_number": season_index,
                    "episode_number": episode_index,
                    "name": name,
                    "url": url,
                    "file_type": _clean_text(episode.get("file_type")).lower() or "mp4",
                    "thumb": _clean_text(episode.get("image_url")),
                    "subtitles": episode.get("subtitle") or [],
                })
        return episodes

    def _signing_secret(self):
        date = datetime.utcfromtimestamp(self._now()).strftime("%Y%m%d")
        cached = self._signing_cache.get(date)
        if cached:
            return cached
        secret = HMAC_SECRET.encode("utf-8")
        key = hashlib.sha256(secret).digest()
        nonce = hashlib.sha256(b"iv:" + secret).digest()[:12]
        encrypted = aes_gcm_encrypt(key, nonce, secret + b":" + date.encode("ascii"))
        signing_secret = HMAC_SECRET + ":" + encrypted.hex()
        self._signing_cache = {date: signing_secret}
        return signing_secret

    def _refresh_server_time(self):
        try:
            self._json("latest_movies", {"limit": 1, "page": 1})
        except ApiError:
            pass

    def _resolve_signed_stream(self, filename):
        signing_secret = self._signing_secret()
        timestamp = int(self._now())
        timestamp_bytes = (timestamp & 0xFFFFFFFF).to_bytes(4, "big")
        mask = hmac.new(signing_secret.encode("utf-8"), b"otp-ts-mask", hashlib.sha256).digest()[:4]
        obscured_timestamp = bytes(left ^ right for left, right in zip(timestamp_bytes, mask)).hex()
        token_payload = (filename + ":" + str(timestamp)).encode("utf-8")
        token = hmac.new(signing_secret.encode("utf-8"), token_payload, hashlib.sha256).hexdigest()
        resolver_url = self.resolver_base + quote(filename, safe="")
        payload = self._json(resolver_url, {"token": token, "ts": obscured_timestamp}, authenticated=False)
        resolved = _clean_text(payload.get("url") if isinstance(payload, dict) else "")
        final = urlparse(resolved)
        if final.scheme not in ("http", "https"):
            raise ApiError("Server Nét không trả về link phát")
        # Phim4K 2.6.5 hands the signed URL straight to the player. A blocking
        # Range probe here can outlive Kodi's resolver timeout even when the
        # media URL is valid, causing a false "source error".
        return resolved

    def resolve_stream_url(self, source_url):
        source_url = _clean_text(source_url)
        parsed = urlparse(source_url)
        if parsed.scheme not in ("http", "https"):
            raise ApiError("Link Server Nét không hợp lệ")
        if (parsed.hostname or "").lower() != "cdn.phim4k.lol":
            return source_url
        filename = parsed.path.rsplit("/", 1)[-1].strip()
        if not filename:
            raise ApiError("Link Server Nét thiếu mã tập tin")

        try:
            return self._resolve_signed_stream(filename)
        except DemoStreamError:
            # A wrong device clock produces a formally valid resolver response
            # that points to demo.mp4. Refresh server time and sign once more.
            self._refresh_server_time()
            self._signing_cache = {}
            return self._resolve_signed_stream(filename)

    def _reject_demo_stream(self, resolved_url):
        """Reject the small warning clip currently returned for unavailable movies."""
        request = Request(
            resolved_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                "Range": "bytes=0-1023",
            },
        )
        try:
            with urlopen(request, timeout=min(self.timeout, 12)) as response:
                headers = response.headers
                proxy_source = _clean_text(headers.get("X-Proxy-Source")).lower()
                disposition = _clean_text(headers.get("Content-Disposition")).lower()
                content_type = _clean_text(headers.get("Content-Type")).lower()
                content_range = _clean_text(headers.get("Content-Range"))
                content_length = 0
                total_match = re.search(r"/(\d+)\s*$", content_range)
                if total_match:
                    content_length = int(total_match.group(1))
                else:
                    try:
                        content_length = int(headers.get("Content-Length") or 0)
                    except (TypeError, ValueError):
                        content_length = 0
                is_demo = (
                    proxy_source == "demo-proxy"
                    or "demo.mp4" in disposition
                    or (content_type.startswith("video/mp4") and 0 < content_length <= 1400000)
                )
                if is_demo:
                    raise DemoStreamError(
                        "Server Nét đang trả clip demo thay cho file phim. "
                        "Đã đồng bộ giờ máy chủ và ký lại nhưng vẫn không có file thật."
                    )
        except ApiError:
            raise
        except (HTTPError, URLError, OSError) as exc:
            raise ApiError("Không kiểm tra được link phát Server Nét: %s" % getattr(exc, "reason", exc))
