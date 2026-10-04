"""Offline destination safety heuristics (no third-party calls, nothing leaves the server).
Returns a 0-100 score; this is a risk hint, not a guarantee."""
import re
from urllib.parse import urlparse

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "rebrand.ly", "cutt.ly", "shorturl.at",
              "rb.gy", "tiny.cc", "t.ly"}
RISKY_TLDS = {"zip", "mov", "top", "xyz", "click", "country", "gq", "tk", "ml", "cf", "ga", "work", "support", "rest", "icu"}
BRANDS = {"paypal": "paypal.com", "google": "google.com", "microsoft": "microsoft.com", "apple": "apple.com",
          "amazon": "amazon.com", "netflix": "netflix.com", "facebook": "facebook.com", "instagram": "instagram.com",
          "whatsapp": "whatsapp.com", "sbi": "sbi.co.in", "hdfcbank": "hdfcbank.com", "icicibank": "icicibank.com",
          "paytm": "paytm.com", "phonepe": "phonepe.com", "flipkart": "flipkart.com", "irctc": "irctc.co.in"}
BLOCKED_SCHEMES = ("javascript:", "data:", "file:", "vbscript:", "blob:")
EXEC_EXT = (".apk", ".exe", ".msi", ".bat", ".scr", ".dmg", ".jar")


def registered_domain(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "gov", "ac"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def domain_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def check(url: str) -> dict:
    """-> {score, label, blocked, findings:[(severity, text)]}"""
    url = (url or "").strip()
    out = {"score": 100, "label": "Safe", "blocked": False, "findings": []}
    low = url.lower()
    if low.startswith(BLOCKED_SCHEMES):
        out.update(score=0, label="Blocked", blocked=True)
        out["findings"].append(("high", "This link type can run code in the visitor's browser and is not allowed."))
        return out
    if not low.startswith(("http://", "https://")):
        out["findings"].append(("info", "Not a web link (phone, email, text...). Web safety checks do not apply."))
        return out
    host = domain_of(url)
    if not host:
        out.update(score=10, label="Risky")
        out["findings"].append(("high", "Could not read a valid domain from this link."))
        return out
    pen = 0

    def flag(sev, pts, text):
        nonlocal pen
        pen += pts
        out["findings"].append((sev, text))

    if low.startswith("http://"):
        flag("med", 15, "Uses plain HTTP: visitors' connection is not encrypted. Prefer https.")
    if re.fullmatch(r"[\d.]+|\[[0-9a-f:]+\]", host):
        flag("high", 40, "Points to a raw IP address instead of a domain name.")
    if host.startswith("xn--") or ".xn--" in host:
        flag("high", 35, "Domain uses punycode, often used for look-alike (homograph) attacks.")
    if host in SHORTENERS or registered_domain(host) in SHORTENERS:
        flag("med", 20, "Another link shortener hides the real destination. Use the final URL instead.")
    if host.count(".") >= 4:
        flag("med", 15, "Unusually many sub-domains.")
    if host.rsplit(".", 1)[-1] in RISKY_TLDS:
        flag("med", 20, f"The .{host.rsplit('.', 1)[-1]} extension is frequently abused for scams.")
    if "@" in url.split("//", 1)[1].split("/", 1)[0]:
        flag("high", 40, "Contains '@' before the domain, a classic trick to disguise the real site.")
    reg = registered_domain(host)
    for brand, real in BRANDS.items():
        if brand in host and reg != real and not reg.startswith(real.split(".")[0] + "."):
            flag("high", 40, f"Mentions '{brand}' but is not {real}: possible impersonation.")
            break
    if low.split("?")[0].endswith(EXEC_EXT):
        flag("high", 35, "Links straight to a downloadable program file.")
    if len(url) > 300:
        flag("low", 10, "Very long URL.")
    if re.search(r"(login|signin|verify|account|secure|update).*(login|signin|verify|password)", host):
        flag("med", 20, "Domain looks like a login or verification page.")
    out["score"] = max(0, 100 - pen)
    out["label"] = "Safe" if out["score"] >= 80 else "Caution" if out["score"] >= 50 else "Risky"
    if not out["findings"]:
        out["findings"].append(("ok", "No warning signs found in the link itself."))
    return out
