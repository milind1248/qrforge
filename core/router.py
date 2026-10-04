"""Smart routing: decides where a dynamic-QR scan goes.
Priority: schedule -> scan limit -> device rule -> A/B split -> base destination (+UTM).
Rules are Pro+ features; if a plan lapses they are ignored and the base destination keeps working
(the 'never-dead' promise)."""
import json
import random
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from core import db
from core.plans import get_plan

DEVICE_KEYS = ("iOS", "Android", "Desktop")


def parse_rules(qr: dict) -> dict:
    try:
        return json.loads(qr.get("rules") or "{}")
    except ValueError:
        return {}


def add_utm(url: str, utm: dict) -> str:
    if not utm or not url.lower().startswith(("http://", "https://")):
        return url
    p = urlparse(url)
    q = dict(parse_qsl(p.query, keep_blank_values=True))
    for k in ("source", "medium", "campaign"):
        if utm.get(k) and f"utm_{k}" not in q:
            q[f"utm_{k}"] = utm[k]
    return urlunparse(p._replace(query=urlencode(q)))


def resolve(qr: dict, owner: dict, device: str, os_: str, today: date | None = None) -> dict:
    """-> {url, outcome, variant}   url=None means 'show inactive message'."""
    plan = get_plan(owner["plan"])
    rules = parse_rules(qr)
    base = qr["dest"] or ""
    today = today or date.today()
    res = {"url": base, "outcome": "redirect", "variant": None}
    if plan.smart_rules:
        fb = rules.get("fallback") or None
        start, end = rules.get("start"), rules.get("end")
        if start and today < date.fromisoformat(start):
            return {"url": fb, "outcome": "not-started", "variant": None}
        if end and today > date.fromisoformat(end):
            return {"url": fb, "outcome": "expired", "variant": None}
        if rules.get("limit") and db.count_scans(qr["id"]) >= int(rules["limit"]):
            return {"url": fb, "outcome": "limit-reached", "variant": None}
        dev = rules.get("device") or {}
        key = "iOS" if os_ == "iOS" else "Android" if os_ == "Android" else "Desktop"
        if dev.get(key):
            res.update(url=dev[key], outcome=f"device:{key}")
        else:
            ab = [v for v in rules.get("ab") or [] if v.get("url")]
            if len(ab) >= 2:
                i = random.choices(range(len(ab)), weights=[max(1, int(v.get("w", 50))) for v in ab])[0]
                res.update(url=ab[i]["url"], outcome="ab", variant="ABCDEF"[i])
    if plan.key != "free":
        res["url"] = add_utm(res["url"], rules.get("utm") or {}) if res["url"] else res["url"]
    return res
