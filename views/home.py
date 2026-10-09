from core import license as _license

_license.require()
# QR generator (landing page). Works anonymously for static codes; saving/dynamic needs an account.
import datetime as dt

import streamlit as st

from core import auth, db, qr_engine as qe, safety, scan_test
from core.config import BASE_URL
from core.plans import PLANS, get_plan
from core.i18n import _
from core.stats import count_download
from core.ui import footer, hero_split, lock_note

user = auth.current_user()
plan = get_plan(user["plan"] if user else "free")

hero_split(_("Create QR codes that look great<br>and work everywhere"),
           _("Static codes are free forever. Go dynamic to edit destinations after printing and track every scan."),
           _("Free QR code generator · no signup needed"))


def type_fields(t: str) -> dict:
    k = lambda n: f"{t}_{n}"
    f = {}
    if t == "url":
        f["url"] = st.text_input(_("Website address"), key=k("url"), placeholder=_("https://example.com"))
    elif t == "text":
        f["text"] = st.text_area(_("Your text"), key=k("text"), height=120, placeholder=_("Any text, up to ~1000 characters"))
    elif t == "wifi":
        c1, c2 = st.columns(2)
        f["ssid"] = c1.text_input(_("Network name (SSID)"), key=k("ssid"))
        f["password"] = c2.text_input(_("Password"), key=k("pw"), type="password")
        f["enc"] = st.segmented_control(_("Security"), ["WPA/WPA2", "WEP", "None"], format_func=lambda v: _("None") if v == "None" else v, default="WPA/WPA2", key=k("enc")) or "WPA/WPA2"
        f["hidden"] = st.checkbox(_("Hidden network"), key=k("hid"))
    elif t == "vcard":
        c1, c2 = st.columns(2)
        f["first"] = c1.text_input(_("First name"), key=k("fn"))
        f["last"] = c2.text_input(_("Last name"), key=k("ln"))
        c1, c2 = st.columns(2)
        f["phone"] = c1.text_input(_("Phone"), key=k("ph"))
        f["email"] = c2.text_input(_("Email"), key=k("em"))
        c1, c2 = st.columns(2)
        f["org"] = c1.text_input(_("Company"), key=k("org"))
        f["title"] = c2.text_input(_("Job title"), key=k("ti"))
        f["web"] = st.text_input(_("Website"), key=k("web"))
        f["addr"] = st.text_input(_("Address"), key=k("ad"))
    elif t == "email":
        f["to"] = st.text_input(_("To"), key=k("to"), placeholder=_("hello@example.com"))
        f["subject"] = st.text_input(_("Subject"), key=k("su"))
        f["body"] = st.text_area(_("Message"), key=k("bo"), height=90)
    elif t == "sms":
        f["phone"] = st.text_input(_("Phone number"), key=k("ph"), placeholder=_("+919876543210"))
        f["message"] = st.text_area(_("Message"), key=k("me"), height=90)
    elif t == "phone":
        f["phone"] = st.text_input(_("Phone number"), key=k("ph"), placeholder=_("+919876543210"))
    elif t == "whatsapp":
        f["phone"] = st.text_input(_("WhatsApp number (with country code)"), key=k("ph"), placeholder=_("919876543210"))
        f["message"] = st.text_input(_("Pre-filled message (optional)"), key=k("me"))
    elif t == "upi":
        c1, c2 = st.columns(2)
        f["vpa"] = c1.text_input(_("UPI ID"), key=k("vpa"), placeholder=_("shop@upi"))
        f["name"] = c2.text_input(_("Payee name"), key=k("nm"))
        c1, c2 = st.columns(2)
        f["amount"] = c1.text_input(_("Amount ₹ (optional)"), key=k("am"))
        f["note"] = c2.text_input(_("Note (optional)"), key=k("no"))
    elif t == "location":
        c1, c2 = st.columns(2)
        f["lat"] = c1.text_input(_("Latitude"), key=k("la"), placeholder=_("19.0760"))
        f["lon"] = c2.text_input(_("Longitude"), key=k("lo"), placeholder=_("72.8777"))
    elif t == "event":
        f["title"] = st.text_input(_("Event title"), key=k("ti"))
        f["place"] = st.text_input(_("Location"), key=k("pl"))
        c1, c2, c3, c4 = st.columns(4)
        today = dt.date.today()
        f["start_d"] = c1.date_input(_("Start date"), today, key=k("sd"))
        f["start_t"] = c2.time_input(_("Start time"), dt.time(10, 0), key=k("st"))
        f["end_d"] = c3.date_input(_("End date"), today, key=k("ed"))
        f["end_t"] = c4.time_input(_("End time"), dt.time(11, 0), key=k("et"))
    return f


def design_controls() -> dict:
    s = {}
    c1, c2 = st.columns(2)
    s["fg"] = c1.color_picker(_("QR colour"), "#0F172A", key="d_fg")
    s["bg"] = c2.color_picker(_("Background"), "#FFFFFF", key="d_bg")
    if plan.gradients:
        if st.toggle(_("Gradient colour"), key="d_grad"):
            c1, c2 = st.columns(2)
            s["fg2"] = c1.color_picker(_("Second colour"), "#7C3AED", key="d_fg2")
            s["gdir"] = c2.selectbox(_("Direction"), ["Vertical", "Horizontal", "Radial", "Diamond"], format_func=_, key="d_gd")
    else:
        lock_note(_("Gradient colours are on the Pro plan."))
    s["shape"] = st.pills(_("Dot style"), list(plan.shapes), format_func=_, default="Square", key="d_shape") or "Square"
    if len(plan.shapes) < 6:
        lock_note(_("More dot styles unlock on Starter."))
    s["eye"] = st.pills(_("Corner style"), list(qe.EYES), format_func=_, default="Square", key="d_eye") or "Square"
    s["ecc"] = st.select_slider(_("Error correction"), list(qe.ECC), value="Medium (15%)", format_func=_, key="d_ecc")
    if plan.logo:
        up = st.file_uploader(_("Logo in the centre (PNG/JPG)"), type=["png", "jpg", "jpeg"], key="d_logo")
        s["logo"] = up.getvalue() if up else None
    else:
        lock_note(_("Add your logo in the centre with Starter or higher."))
    # contrast guard
    def lum(h):
        r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
        return 0.299 * r + 0.587 * g + 0.114 * b
    if abs(lum(s["fg"]) - lum(s["bg"])) < 90:
        st.warning(_("Low contrast: this QR code may be hard to scan. Use a darker QR colour on a lighter background."))
    return s


def downloads(data: str, style: dict, key: str):
    fmts = list(plan.formats)
    cols = st.columns(len(fmts))
    for c, fmt in zip(cols, fmts):
        blob, mime = qe.export(data, style, fmt, plan.watermark)
        c.download_button(f"{fmt}", blob, f"qr-sugi.{fmt.lower()}", mime, key=f"{key}_{fmt}",
                          width="stretch", type="primary" if fmt == "PNG" else "secondary", on_click=count_download)
    if len(fmts) < 4:
        lock_note(_("SVG / PDF downloads and watermark-free files need a paid plan."))


def safety_panel(url: str):
    r = safety.check(url)
    if r["findings"][0][0] == "info":
        return r
    icon = {"Safe": "✅", "Caution": "⚠️", "Risky": "🚨", "Blocked": "⛔"}[r["label"]]
    box = st.success if r["label"] == "Safe" else st.warning if r["label"] == "Caution" else st.error
    box(f"{icon} Destination safety **{r['score']}/100** ({r['label']})")
    for sev, txt in r["findings"]:
        if sev != "ok":
            st.caption(f"• {txt}")
    return r


def reliability_test(data: str, style: dict):
    with st.expander(_("Test scan reliability before you print"), icon=":material/science:"):
        st.caption(_("Simulates blur, small size, noise, tilt and compression, then tries to read your code each time."))
        dist = st.select_slider(_("How far away will people scan from?"), [20, 50, 100, 200, 400, 1000], value=50,
                                format_func=lambda c: f"{c} cm" if c < 100 else f"{c / 100:g} m")
        adv = scan_test.print_advice(dist, len(data))
        st.info(_("Print it at least **{min} cm** wide (ideal **{ideal} cm**) for scanning from that distance.", min=adv['min_cm'], ideal=adv['ideal_cm']),
                icon=":material/straighten:")
        if st.button(_("Run stress test"), key="stress", width="stretch"):
            with st.spinner(_("Testing...")):
                res = scan_test.run(data, style)
            counted = [r for r in res if not r["info"]]
            ok = sum(r["passed"] for r in counted)
            score = round(100 * ok / len(counted))
            verdict = "Excellent" if score >= 75 else "Good" if score >= 60 else "Fair" if score >= 40 else "Poor"
            (st.success if score >= 60 else st.warning if score >= 40 else st.error)(
                f"Reliability **{verdict}** ({score}/100): survives {ok} of {len(counted)} real-world conditions. "
                "Extreme cases (stamp size, heavy blur, heavy noise) are expected to fail on most codes.")
            for r in res:
                mark = ":green[PASS]" if r["passed"] else (":gray[n/a]" if r["info"] else ":red[FAIL]")
                st.markdown(f"{mark} **{r['name']}** · {r['note']}")
            if score < 60:
                st.caption(_("Tips: use a dark QR on a light background, raise error correction, avoid heavy gradients, and print larger."))


left, right = st.columns([3, 2], gap="large")

with left:
    labels = {k: f"{v[1]} {_(v[0])}" for k, v in qe.TYPES.items()}
    t = st.pills(_("QR code type"), list(qe.TYPES), format_func=labels.get, default="url", key="qtype") or "url"
    tab_content, tab_design = st.tabs([":material/edit: " + _("Content"), ":material/palette: " + _("Design")])
    with tab_content:
        fields = type_fields(t)
    with tab_design:
        style = design_controls()

payload = qe.build_payload(t, fields)
can_dynamic = qe.TYPES[t][2]

with right:
    mode = "Static"
    if can_dynamic:
        mode = st.segmented_control(_("Mode"), ["Static", "Dynamic"], format_func=_, default="Static", key="mode",
                                    help=_("Dynamic codes point to a short link you can edit later and track scans.")) or "Static"
    encoded = f"{BASE_URL}/?r=preview" if mode == "Dynamic" else payload
    img = qe.render(encoded if payload else " ", style, plan.watermark)
    st.image(img, width="stretch")
    if not payload.strip():
        st.caption(_("Fill in the content to generate your code."))

    if mode == "Dynamic":
        st.info(_("Dynamic QR: the printed code never changes, but you can change where it goes and see scan analytics."),
                icon=":material/bolt:")
        if payload.strip():
            reliability_test(encoded, style)
        if not user:
            st.page_link("views/login.py", label=_("Log in or sign up to create dynamic codes"), icon=":material/login:")
        else:
            used = db.count_dynamic(user["id"])
            st.caption(_("Dynamic codes used: **{used} / {limit}** on the {plan} plan", used=used, limit=plan.dynamic_limit, plan=plan.name))
            name = st.text_input(_("Name this QR code"), key="dyn_name", placeholder=_("e.g. Diwali flyer"))
            campaign = st.text_input(_("Campaign tag (optional)"), key="dyn_campaign", placeholder=_("e.g. diwali-2026"))
            sres = safety_panel(payload) if payload.strip() else {"blocked": False}
            if used >= plan.dynamic_limit:
                lock_note(_("You have reached your dynamic QR limit. Upgrade to add more."))
                st.page_link("views/pricing.py", label=_("See plans"), icon=":material/workspace_premium:")
            elif sres.get("blocked"):
                st.error(_("This link type is not allowed."))
            elif st.button(_("Create dynamic QR code"), type="primary", width="stretch", disabled=not payload.strip()):
                qid = db.save_qr(user["id"], name or f"{qe.TYPES[t][0]} QR", t, payload, {k: v for k, v in style.items() if k != "logo"},
                                 True, dest=payload, campaign=campaign)
                st.session_state["flash"] = "Dynamic QR code created. Download it from My QR codes."
                st.switch_page("views/dashboard.py")
    else:
        if payload.strip() and safety.check(payload)["blocked"]:
            st.error(_("This link type can run code in the visitor's browser and is not allowed."))
        elif payload.strip():
            if t in ("url", "whatsapp", "location"):
                safety_panel(payload)
            downloads(payload, style, "gen")
            reliability_test(payload, style)
            if user:
                if st.button(_("Save to my account"), width="stretch", icon=":material/bookmark:"):
                    db.save_qr(user["id"], f"{qe.TYPES[t][0]} QR", t, payload,
                               {k: v for k, v in style.items() if k != "logo"}, False)
                    st.toast(_("Saved to My QR codes"))
            else:
                st.caption(_("Create a free account to save codes and unlock dynamic QR."))

st.divider()
st.subheader(_("Everything you need to run QR campaigns"))
feats = [
    ("⚡", "Dynamic QR codes", "Change the destination any time without reprinting. Pause or resume a code in one click."),
    ("📊", "Scan analytics", "See scans over time plus device, OS and browser breakdowns to measure every campaign."),
    ("🎨", "Beautiful designs", "Custom colours, gradients, dot and corner styles, and your logo in the centre."),
    ("📦", "Bulk generator", "Upload a CSV and download hundreds of codes as a ZIP: labels, tickets, inventory."),
    ("🇮🇳", "Made for India", "UPI payment QR, WhatsApp chat links and pricing in rupees."),
    ("🔒", "Yours to keep", "Static codes never expire and never route through our servers."),
]
for row in (feats[:3], feats[3:]):
    cols = st.columns(3)
    for c, (ico, ttl, txt) in zip(cols, row):
        c.markdown(f'<div class="card"><div class="feat-ico">{ico}</div><h4>{_(ttl)}</h4><p>{_(txt)}</p></div>',
                   unsafe_allow_html=True)
    st.write("")

st.subheader(_("Popular use cases"))
uc = st.columns(4)
for c, (ttl, txt) in zip(uc, [("Restaurants", "Contactless menus, UPI table payments, review links"),
                              ("Retail & shops", "Product pages, offers, WhatsApp ordering"),
                              ("Events", "Schedules, check-ins, add-to-calendar codes"),
                              ("Real estate", "Listings, brochures, site-visit enquiries")]):
    c.markdown(f'<div class="card"><h4>{_(ttl)}</h4><p>{_(txt)}</p></div>', unsafe_allow_html=True)

if not user:
    st.write("")
    st.page_link("views/pricing.py", label=_("Compare plans →"), icon=":material/workspace_premium:")
footer()
