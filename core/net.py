# -*- coding: utf-8 -*-
"""共享 HTTP 客户端：SSRF 白名单 + DNS 私网拒绝 + 禁重定向 + 429/断连自动重试。"""
import base64, configparser, http.client, ipaddress, json, os, socket, sys, time
import urllib.request, urllib.error
from urllib.parse import urlsplit

API = "https://api.wakatime.com/api/v1"
ALLOWED_SCHEME, ALLOWED_HOST = "https", "api.wakatime.com"


def build_url(path):
    """仅允许 https + 白名单域名，且解析结果必须为公网地址（防 SSRF/DNS rebinding）。"""
    url = API + path
    u = urlsplit(url)
    if u.scheme != ALLOWED_SCHEME or u.hostname != ALLOWED_HOST:
        raise ValueError(f"非法请求地址: {url}")
    for info in socket.getaddrinfo(u.hostname, 443, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f"目标域名解析到受限地址 {ip}，已拒绝请求")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def api_key():
    cfg = configparser.ConfigParser()
    if not cfg.read(os.path.expanduser("~/.wakatime.cfg"), encoding="utf-8"):
        raise RuntimeError("未找到 ~/.wakatime.cfg")
    key = cfg.get("settings", "api_key", fallback=None)
    if not key:
        raise RuntimeError("~/.wakatime.cfg 中没有 api_key")
    return key


def get(path, retry=5):
    """GET {API}{path}，返回解析后的 JSON；失败返回 None（网络层已自动重试）。"""
    auth = base64.b64encode(api_key().encode()).decode()
    req = urllib.request.Request(build_url(path), headers={
        "Authorization": "Basic " + auth, "User-Agent": "local-stats-boards/1.0"})
    for i in range(retry):
        try:
            with _OPENER.open(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", 5))
                print(f"  429 限流，等待 {wait}s ...", file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code >= 500 and i < retry - 1:
                time.sleep(3)
                continue
            print(f"  HTTP {e.code}: {path}", file=sys.stderr)
            return None
        except (urllib.error.URLError, http.client.HTTPException, OSError, TimeoutError) as e:
            if i < retry - 1:
                time.sleep(2 + i * 2)
                continue
            print(f"  网络错误（已重试 {retry} 次）: {e}", file=sys.stderr)
            return None
    return None
