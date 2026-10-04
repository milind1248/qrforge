import json
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from core import auth, db, health, qr_engine as qe, router, safety
from core.config import BASE_URL
from core.plans import get_plan
from core.ui import lock_note

user = auth.current_user()
plan = get_plan(user["plan"])

st.title(f"Hello, {user['name'].split()[0]} 👋")
if msg := st.session_state.pop("flash", None):
    st.success(msg)

qrs = db.list_qrs(user["id"])
dyn = [q for q in qrs if q["is_dynamic"]]
c = st.columns(4)
c[0].metric("QR codes", len(qrs))
c[1].metric("Dynamic used", f"{len(dyn)} / {plan.dynamic_limit}")
c[2].metric("Total scans", sum(q["scans"] for q in qrs))
c[3].metric("Plan", plan.name)

st.info("**Never-dead promise:** your printed dynamic codes keep redirecting even if you cancel or hit a limit. "
        "Premium routing rules pause, but your base destination stays live.", icon=":material/verified_user:")

h1, h2, h3 = st.columns([3, 1.3, 1.1])
h1.subheader("My QR codes")
campaigns = sorted({q["campaign"] for q in qrs if q["campaign"]})
flt = h2.selectbox("Campaign", ["All"] + campaigns, label_visibility="collapsed")
h3.page_link("views/home.py", label="New QR code", icon=":material/add:", width="stretch")

if qrs:
    backup = pd.DataFrame([{"name": q["name"], "type": q["qr_type"], "dynamic": q["is_dynamic"],
                            "short_link": f"{BASE_URL}/?r={q['short_code']}" if q["is_dynamic"] else "",
                            "destination": q["dest"] or q["content"], "campaign": q["campaign"] or "",
                            "scans": q["scans"], "created": q["created_at"]} for q in qrs])
    st.download_button("Backup all codes (CSV)", backup.to_csv(index=False), "qrforge_backup.csv", "text/csv",
                       icon=":material/cloud_download:", help="Your data is always portable.")
else:
    st.info("You have not created any QR codes yet. Make your first one from the generator.", icon=":material/qr_code_2:")

DEV_LABEL = {"iOS": "iPhone / iPad", "Android": "Android", "Desktop": "Desktop / other"}


def safety_badge(url: str):
    r = safety.check(url)
    if r["label"] == "Safe" and r["findings"][0][0] == "info":
        return
    icon = {"Safe": "✅", "Caution": "⚠️", "Risky": "🚨", "Blocked": "⛔"}[r["label"]]
    st.caption(f"{icon} Safety score **{r['score']}/100** ({r['label']})")
    for sev, txt in r["findings"]:
        if sev in ("high", "med", "low"):
            st.caption(f"• {txt}")


for q in qrs:
    if flt != "All" and q["campaign"] != flt:
        continue
    data = f"{BASE_URL}/?r={q['short_code']}" if q["is_dynamic"] else q["content"]
    badge = ":green-badge[Dynamic]" if q["is_dynamic"] else ":gray-badge[Static]"
    state = "" if q["active"] else " :orange-badge[Paused]"
    camp = f" :blue-badge[{q['campaign']}]" if q["campaign"] else ""
    with st.expander(f"{q['name']}  ·  {qe.TYPES.get(q['qr_type'], ('QR',))[0]}  ·  {q['scans']} scans"):
        st.markdown(f"{badge}{state}{camp}  · created {q['created_at'][:10]}")
        style = dict(q["style"])
        t_main, t_rules, t_hist = st.tabs(["Destination & downloads", "Smart routing", "Recent scans"]) if q["is_dynamic"] \
            else (st.container(), None, None)

        with t_main:
            a, b = st.columns([1, 2], gap="large")
            with a:
                st.image(qe.render(data, style, plan.watermark, box=8), width=220)
            with b:
                if q["is_dynamic"]:
                    st.code(data, language=None)
                    new_dest = st.text_area("Destination (editable any time)", q["dest"], key=f"dest_{q['id']}", height=70)
                    safety_badge(new_dest)
                    c1, c2, c3 = st.columns(3)
                    if c1.button("Save changes", key=f"sv_{q['id']}", type="primary", width="stretch"):
                        if safety.check(new_dest)["blocked"]:
                            st.error("This link type is not allowed.")
                        else:
                            db.update_qr(q["id"], user["id"], dest=new_dest)
                            st.toast("Destination updated")
                            st.rerun()
                    if c2.button("Resume" if not q["active"] else "Pause", key=f"pa_{q['id']}", width="stretch"):
                        db.update_qr(q["id"], user["id"], active=0 if q["active"] else 1)
                        st.rerun()
                    if c3.button("Check link", key=f"hc_{q['id']}", icon=":material/health_and_safety:", width="stretch",
                                 disabled=not plan.smart_rules, help="Pro: test that the destination still loads"):
                        r = health.check(q["dest"])
                        db.update_qr(q["id"], user["id"], health=json.dumps(r), health_at=datetime.now().isoformat(timespec="seconds"))
                        st.rerun()
                    if not plan.smart_rules:
                        st.caption("Link-health check is on Pro.")
                    elif q["health"]:
                        hr = json.loads(q["health"])
                        if hr["ok"]:
                            st.success(f"Destination is live (HTTP {hr['status']}, {hr['ms']} ms). Checked {q['health_at'][:16]}")
                        elif hr["ok"] is False:
                            st.error(f"Destination problem: {hr['error']}. Visitors may see an error page. Checked {q['health_at'][:16]}")
                    cc = st.text_input("Campaign tag", q["campaign"] or "", key=f"cmp_{q['id']}", placeholder="e.g. diwali-2026")
                    if cc != (q["campaign"] or ""):
                        db.update_qr(q["id"], user["id"], campaign=cc.strip() or None)
                else:
                    st.caption("Static QR content")
                    st.code(q["content"][:300], language=None)
                dc = st.columns(len(plan.formats) + 1)
                for col, fmt in zip(dc, plan.formats):
                    blob, mime = qe.export(data, style, fmt, plan.watermark)
                    col.download_button(fmt, blob, f"{q['name']}.{fmt.lower()}", mime, key=f"dl_{q['id']}_{fmt}", width="stretch")
                if dc[-1].button("Delete", key=f"del_{q['id']}", icon=":material/delete:", width="stretch"):
                    db.delete_qr(q["id"], user["id"])
                    st.rerun()

        if not q["is_dynamic"]:
            continue

        with t_rules:
            rules = router.parse_rules(q)
            utm = rules.get("utm", {})
            st.markdown("**Trust & identity**")
            tp = st.toggle("Show a trust-preview page with my name before redirecting", bool(q["trust_preview"]), key=f"tp_{q['id']}",
                           disabled=plan.key == "free",
                           help="Visitors see the destination domain and who published the code. Protects against sticker-swap scams.")
            if plan.key == "free":
                lock_note("Free-plan codes always show the short QRForge trust page. Upgrade for direct redirects and your own branding.")
            st.markdown("**Campaign tracking (UTM)**")
            u1, u2, u3 = st.columns(3)
            nutm = {"source": u1.text_input("utm_source", utm.get("source", ""), key=f"us_{q['id']}", placeholder="flyer"),
                    "medium": u2.text_input("utm_medium", utm.get("medium", ""), key=f"um_{q['id']}", placeholder="qr"),
                    "campaign": u3.text_input("utm_campaign", utm.get("campaign", ""), key=f"uc_{q['id']}", placeholder="diwali")}
            if plan.key == "free":
                lock_note("UTM auto-tagging starts on Starter.")

            if not plan.smart_rules:
                lock_note("Device routing, schedules, scan limits, A/B split and password protection are on Pro.")
                nrules = {**rules, "utm": nutm} if plan.key != "free" else rules
            else:
                st.markdown("**Send people to different places by device**")
                dev = rules.get("device", {})
                d1, d2, d3 = st.columns(3)
                ndev = {}
                for col, k in zip((d1, d2, d3), router.DEVICE_KEYS):
                    ndev[k] = col.text_input(DEV_LABEL[k], dev.get(k, ""), key=f"dv{k}_{q['id']}", placeholder="https://...")
                st.markdown("**A/B split test** (random split between destinations, used when no device rule matches)")
                ab = rules.get("ab") or [{"url": "", "w": 50}, {"url": "", "w": 50}]
                nab = []
                for i, v in enumerate(ab[:3] + [{"url": "", "w": 0}] * max(0, 3 - len(ab))):
                    x1, x2 = st.columns([4, 1])
                    nab.append({"url": x1.text_input(f"Variant {'ABC'[i]} URL", v.get("url", ""), key=f"ab{i}_{q['id']}"),
                                "w": x2.number_input("Weight %", 0, 100, int(v.get("w", 0)), key=f"abw{i}_{q['id']}")})
                st.markdown("**Schedule, limits and fallback**")
                s1, s2, s3 = st.columns(3)
                use_sch = s1.checkbox("Active only between dates", bool(rules.get("start") or rules.get("end")), key=f"sc_{q['id']}")
                start = s2.date_input("From", date.fromisoformat(rules["start"]) if rules.get("start") else date.today(),
                                      key=f"sd_{q['id']}", disabled=not use_sch)
                end = s3.date_input("Until", date.fromisoformat(rules["end"]) if rules.get("end") else date.today() + timedelta(days=30),
                                    key=f"ed_{q['id']}", disabled=not use_sch)
                l1, l2 = st.columns(2)
                limit = l1.number_input("Stop after N scans (0 = unlimited)", 0, 10_000_000, int(rules.get("limit") or 0),
                                        key=f"lm_{q['id']}", help="Great for coupons: the 100th scan gets the fallback page.")
                fallback = l2.text_input("Fallback URL (when expired / limit reached)", rules.get("fallback", ""), key=f"fb_{q['id']}",
                                         placeholder="https://example.com/offer-ended")
                st.markdown("**Password protection**")
                pw = st.text_input("Set / change password (leave empty to keep as is)", type="password", key=f"pw_{q['id']}")
                clear_pw = st.checkbox("Remove password", key=f"cpw_{q['id']}") if rules.get("pw_hash") else False
                if rules.get("pw_hash"):
                    st.caption("A password is currently set.")
                nrules = {"utm": nutm if plan.key != "free" else {}, "device": {k: v for k, v in ndev.items() if v},
                          "ab": [v for v in nab if v["url"]], "fallback": fallback or None, "limit": int(limit) or None}
                if use_sch:
                    nrules["start"], nrules["end"] = start.isoformat(), end.isoformat()
                if pw:
                    nrules["pw_hash"] = auth.hash_pw(pw)
                elif rules.get("pw_hash") and not clear_pw:
                    nrules["pw_hash"] = rules["pw_hash"]
                bad = [u for u in [*ndev.values(), fallback, *[v["url"] for v in nab]] if u and safety.check(u)["blocked"]]
                if bad:
                    st.error("Some URLs use a link type that is not allowed.")
            if st.button("Save routing settings", key=f"sr_{q['id']}", type="primary", disabled=plan.smart_rules and bool(bad)):
                db.update_qr(q["id"], user["id"], rules=json.dumps(nrules), trust_preview=int(tp))
                st.toast("Routing saved")
                st.rerun()

        with t_hist:
            sc = [s for s in db.scans_for_user(user["id"], plan.analytics_days) if s["qr_id"] == q["id"]]
            if not sc:
                st.caption("No scans yet.")
            else:
                d = pd.DataFrame(sc).sort_values("ts", ascending=False).head(15)
                d["ts"] = pd.to_datetime(d["ts"]).dt.strftime("%d %b %Y %H:%M") + " UTC"
                st.dataframe(d[["ts", "device", "os", "browser", "outcome"]].rename(columns={"ts": "When"}),
                             width="stretch", hide_index=True)
                st.page_link("views/analytics.py", label="Open full scan history", icon=":material/history:")
