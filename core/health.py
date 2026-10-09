"""Destination health check with SSRF protection (never fetches private / local addresses)."""
import ipaddress
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

UA = "QR Sugi-HealthCheck/1.0"


def _public_host(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _public_host(newurl):
            raise urllib.error.URLError("redirect to a non-public address blocked")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check(url: str, timeout: float = 6.0) -> dict:
    """-> {ok, status, ms, final, error}"""
    if not (url or "").lower().startswith(("http://", "https://")):
        return {"ok": None, "status": None, "ms": None, "final": url, "error": "Not a web link"}
    if not _public_host(url):
        return {"ok": False, "status": None, "ms": None, "final": url, "error": "Host not reachable or not public"}
    opener = urllib.request.build_opener(_SafeRedirect)
    t0 = time.time()
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
            with opener.open(req, timeout=timeout) as r:
                return {"ok": r.status < 400, "status": r.status, "ms": int((time.time() - t0) * 1000),
                        "final": r.geturl(), "error": None}
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue
            return {"ok": False, "status": e.code, "ms": int((time.time() - t0) * 1000), "final": url,
                    "error": f"HTTP {e.code}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "status": None, "ms": None, "final": url, "error": str(getattr(e, "reason", e))[:120]}
    return {"ok": False, "status": None, "ms": None, "final": url, "error": "No response"}
