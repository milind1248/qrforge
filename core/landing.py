"""Public scan landing: password gate, trust-preview interstitial, scan logging, redirect."""
import hashlib

import streamlit as st

from core import auth, db, router, safety, ui
from core.plans import get_plan

REPORT_REASONS = ["Looks like a scam / phishing", "Sticker placed over another QR code", "Inappropriate content",
                  "Link is broken", "Other"]
URI_OK = ("http://", "https://", "tel:", "mailto:", "sms:", "upi:")


def _headers() -> dict:
    try:
        return dict(st.context.headers)
    except Exception:  # noqa: BLE001
        return {}


def _visitor(h: dict) -> str:
    """Privacy-friendly pseudonymous id: hash of UA + language + IP (if proxied). IP itself is never stored."""
    raw = "|".join([h.get("User-Agent", ""), h.get("Accept-Language", "")[:20], h.get("X-Forwarded-For", "").split(",")[0]])
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _lang(h: dict) -> str:
    tag = h.get("Accept-Language", "").split(",")[0].split(";")[0].strip()
    return tag or "unknown"


def _card(html: str):
    st.markdown(f'<div class="card" style="max-width:640px;margin:2rem auto;text-align:center">{html}</div>',
                unsafe_allow_html=True)


def handle(code: str):
    qr = db.get_qr_by_code(code)
    if not qr or code == "preview":
        _card("<h3>QR code not found</h3><p>This code does not exist or was deleted.</p>"
              if code != "preview" else "<h3>Preview only</h3><p>Save the QR code to activate it.</p>")
        st.stop()
    owner = db.get_user(qr["user_id"])
    rules = router.parse_rules(qr)
    plan_smart = bool(owner) and get_plan(owner["plan"]).smart_rules

    if not qr["active"]:
        _card("<h3>Paused</h3><p>The owner has paused this QR code.</p>")
        st.stop()

    # ---- password gate (Pro+) ----
    if plan_smart and rules.get("pw_hash") and not st.session_state.get(f"unlocked_{code}"):
        _card("<h3>🔒 Password required</h3><p>The owner protected this QR code.</p>")
        _, mid, _ = st.columns([1, 1.4, 1])
        with mid, st.form("gate"):
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Unlock", type="primary", width="stretch"):
                if auth.check_pw(pw, rules["pw_hash"]):
                    st.session_state[f"unlocked_{code}"] = True
                    st.rerun()
                else:
                    st.error("Wrong password.")
        st.stop()

    # ---- resolve + log once per browser session ----
    key = f"res_{code}"
    if key not in st.session_state:
        h = _headers()
        device, os_, browser = ui.parse_ua(h.get("User-Agent", ""))
        res = router.resolve(qr, owner, device, os_)
        db.log_scan(qr["id"], device, os_, browser, _lang(h), _visitor(h), res["outcome"], res["variant"])
        st.session_state[key] = res
    res = st.session_state[key]
    dest = res["url"]

    if not dest:
        msgs = {"not-started": "This QR code is not active yet.", "expired": "This QR code has expired.",
                "limit-reached": "This QR code has reached its scan limit."}
        _card(f"<h3>Unavailable</h3><p>{msgs.get(res['outcome'], 'This QR code is unavailable right now.')}</p>")
        st.stop()

    # ---- non-redirect payloads ----
    if dest.startswith("BEGIN:VCARD"):
        st.markdown("### Contact card")
        st.code(dest, language=None)
        st.download_button("Save contact (.vcf)", dest, "contact.vcf", "text/vcard", type="primary")
        st.stop()
    if dest.startswith("SMSTO:"):
        num, _, msg = dest[6:].partition(":")
        dest = f"sms:{num}" + (f"?body={msg}" if msg else "")
    if not dest.startswith(URI_OK):
        st.markdown("### Message")
        st.write(dest)
        st.stop()

    # ---- safety re-check at scan time (destination may have been edited since creation) ----
    sc = safety.check(dest)
    if sc["blocked"]:
        _card("<h3>Blocked for your safety</h3><p>This QR code points to an unsafe link type.</p>")
        st.stop()

    free_owner = not owner or owner["plan"] == "free"
    preview = free_owner or bool(qr.get("trust_preview")) or sc["label"] == "Risky"
    if not preview:
        ui.redirect(dest)
        st.caption("Redirecting...")
        st.link_button("Tap here if you are not redirected", dest)
        st.stop()

    host = safety.domain_of(dest) or dest.split(":")[0]
    col = {"Safe": "#059669", "Caution": "#B45309", "Risky": "#DC2626"}.get(sc["label"], "#475569")
    by = ""
    if qr.get("trust_preview") and owner:
        by = f"<p style='margin:.2rem 0'>Published by <b>{owner['name']}</b></p>"
    delay = 5 if sc["label"] == "Risky" else 3
    _card(f"<div style='font-size:2rem'>🛡️</div><h3>You are about to open</h3>"
          f"<h2 style='margin:.2rem 0;word-break:break-all'>{host}</h2>{by}"
          f"<p style='color:{col};font-weight:700'>Safety check: {sc['label']} ({sc['score']}/100)</p>"
          + ("<p style='font-size:.85rem'>Automatic redirect is off for risky links. Continue only if you trust this site.</p>"
             if sc["label"] == "Risky" else
             f"<p style='font-size:.85rem'>Redirecting in {delay} seconds. Only continue if you trust this site.</p>"))
    if sc["label"] != "Safe":
        for sev, txt in sc["findings"]:
            st.warning(txt)
    if sc["label"] != "Risky":
        ui.redirect(dest, delay=delay)
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.link_button("Continue now", dest, type="primary", width="stretch")
        with st.expander("Report this QR code"):
            reason = st.selectbox("What is wrong?", REPORT_REASONS)
            note = st.text_input("Details (optional)")
            if st.button("Send report"):
                db.add_report(qr["id"], reason, note)
                st.success("Thanks. Our team will review this code.")
        if free_owner:
            st.caption("Created with QRForge. Make your own QR codes free.")
    st.stop()
