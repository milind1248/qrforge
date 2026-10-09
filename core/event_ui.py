"""Shared event screens: scan result banner, scanner panel (live camera + manual + photo fallback), and the attendee pass view."""
import hashlib
import html
import time

import pandas as pd
import streamlit as st

from core import event_db as E, event_pass as P, qr_engine, scanner
from core.i18n import _

RESULT_STYLE = {
    "valid": ("VALID", "#047857", "#D1FAE5", "&#10003;"),
    "already_used": ("ALREADY USED", "#B45309", "#FEF3C7", "!"),
    "cancelled": ("CANCELLED", "#B91C1C", "#FEE2E2", "&#10005;"),
    "invalid": ("INVALID PASS", "#B91C1C", "#FEE2E2", "&#10005;"),
    "wrong_event": ("WRONG EVENT", "#B91C1C", "#FEE2E2", "&#10005;"),
    "unpaid": ("PAYMENT PENDING", "#B45309", "#FEF3C7", "!"),
    "event_cancelled": ("EVENT CANCELLED", "#B91C1C", "#FEE2E2", "&#10005;"),
}
RESULT_ICON = {"valid": "✅ valid", "already_used": "⚠️ already used", "cancelled": "⛔ cancelled", "invalid": "❌ invalid", "wrong_event": "❌ wrong event",
               "unpaid": "⏳ unpaid", "event_cancelled": "⛔ event cancelled", "undo": "↩️ undone"}


def result_banner(res: dict):
    label, fg, bg, icon = RESULT_STYLE.get(res["result"], ("RESULT", "#334155", "#E2E8F0", "?"))
    b = res.get("booking")
    who = ""
    if b:
        who = (f"<div style='font-size:26px;font-weight:800;margin-top:6px'>{html.escape(b['name'])}</div>"
               f"<div style='font-size:16px;opacity:.85'>{html.escape(b['ref'])} &middot; {html.escape(b['email'])}</div>")
    st.markdown(f"<div style='background:{bg};color:{fg};border:3px solid {fg};border-radius:20px;padding:18px 20px;text-align:center;margin:8px 0'>"
                f"<div style='font-size:46px;line-height:1;font-weight:900'>{icon}</div>"
                f"<div style='font-size:34px;font-weight:900;letter-spacing:.04em'>{label}</div>{who}"
                f"<div style='font-size:15px;margin-top:6px;font-weight:600'>{html.escape(res['message'])}</div></div>", unsafe_allow_html=True)


def scans_table(eid: int, limit: int = 15):
    rows = E.recent_scans(eid, limit)
    if not rows:
        st.caption(_("No scans yet."))
        return
    df = pd.DataFrame([{"Time": E.fmt_utc(r["ts"], "%d %b, %I:%M:%S %p"), "Result": RESULT_ICON.get(r["result"], r["result"]), "Booking": r["ref"] or "",
                        "Name": r["name"] or "", "By": r["actor"] or ""} for r in rows])
    st.dataframe(df, hide_index=True, width="stretch")


def _handle(ev, raw, actor, key, mark=True):
    res = E.process_scan(ev, raw, actor, mark=mark)
    st.session_state[f"{key}_res"] = res
    st.session_state[f"{key}_nonce"] = st.session_state.get(f"{key}_nonce", 0) + 1
    st.session_state[f"{key}_last"] = (raw, time.time())


@st.fragment
def scanner_panel(event_id: int, actor: str, key: str):
    """Entrance scanner for ONE event. Runs as a fragment so a scan only reruns this panel."""
    ev = E.get_event(event_id)
    ss = st.session_state
    stt = E.stats(event_id)
    st.markdown(f"**Checked in {stt['checked_in']} / {stt['confirmed']}** &nbsp;·&nbsp; {max(0, stt['confirmed'] - stt['checked_in'])} still to arrive &nbsp;·&nbsp; {stt['rate']}%")
    st.progress(min(1.0, stt["checked_in"] / stt["confirmed"]) if stt["confirmed"] else 0.0)
    if ss.get(f"{key}_res"):                    # result first, so it is visible on a phone without scrolling past the camera
        result_banner(ss[f"{key}_res"])
    else:
        st.info(_("Scan a pass with the camera, type the booking ID below, or take a photo of the pass."), icon=":material/qr_code_scanner:")
    mark = st.toggle(_("Check in automatically when a valid pass is scanned"), value=True, key=f"{key}_mark",
                     help=_("Turn off to only verify a pass without marking the attendee as arrived."))
    code, frame = scanner.live_scanner(f"{key}_cam", (ss.get(f"{key}_res") or {}).get("result", ""), ss.get(f"{key}_nonce", 0))
    raw = code
    if not raw and frame:
        img = scanner.frame_to_bytes(frame)
        raw = qr_engine.decode(img) if img else None
    if raw:
        last = ss.get(f"{key}_last")
        if not (last and last[0] == raw and time.time() - last[1] < 4):      # ignore the same code read again within 4 seconds
            _handle(ev, raw, actor, key, mark)
            st.rerun(scope="fragment")
    with st.form(f"{key}_manual", clear_on_submit=True):
        m1, m2 = st.columns([4, 1])
        txt = m1.text_input(_("Booking ID or pass link"), placeholder=_("EVT-7K2M9Q"), label_visibility="collapsed")
        go = m2.form_submit_button("Check", type="primary", width="stretch")
    if go and txt.strip():
        _handle(ev, txt, actor, key, mark)
        st.rerun(scope="fragment")
    with st.expander(_("Camera not working? Take a photo of the pass instead")):
        shot = st.camera_input("Photo of the pass QR", key=f"{key}_photo", label_visibility="collapsed")
        if shot is not None:
            data = shot.getvalue()
            h = hashlib.sha1(data).hexdigest()
            if ss.get(f"{key}_photo_h") != h:
                ss[f"{key}_photo_h"] = h
                found = qr_engine.decode(data)
                _handle(ev, found or "unreadable", actor, key, mark)
                st.rerun(scope="fragment")
    st.markdown("**Recent scans**")
    scans_table(event_id)


def pass_view(ev: dict, b: dict, key: str, allow_cancel: bool = True):
    """The attendee's pass: card, downloads, print, calendar and WhatsApp share."""
    st.markdown(P.card_html(ev, b), unsafe_allow_html=True)
    if b["status"] == "pending_payment":
        st.info(_("Your payment is being reviewed by the organizer. This pass becomes active as soon as it is approved, and you will get an email."), icon=":material/hourglass_top:")
        return
    if b["status"] in ("cancelled", "rejected"):
        st.error(_("This booking is not valid anymore.") if b["status"] == "cancelled" else _("Your payment was not accepted, so this pass is not valid."))
        return
    st.write("")
    c1, c2, c3 = st.columns(3)
    c1.download_button(_("Download pass (PNG)"), P.pass_png(ev, b), f"pass-{b['ref']}.png", "image/png", key=f"{key}_png", width="stretch", icon=":material/download:")
    c2.download_button(_("Download pass (PDF)"), P.pass_pdf(ev, b), f"pass-{b['ref']}.pdf", "application/pdf", key=f"{key}_pdf", width="stretch", icon=":material/picture_as_pdf:")
    c3.download_button(_("Add to calendar"), P.ics_text(ev, b), f"{ev['code']}.ics", "text/calendar", key=f"{key}_ics", width="stretch", icon=":material/event:")
    d1, d2 = st.columns(2)
    with d1:
        scanner.print_button(f"{key}_print", b["ref"])
    if b.get("phone"):
        d2.link_button(_("Send to my WhatsApp"), P.whatsapp_link(b["phone"], P.pass_share_text(ev, b)), width="stretch", icon=":material/chat:")
    else:
        d2.link_button(_("Share on WhatsApp"), P.whatsapp_link("", P.pass_share_text(ev, b)), width="stretch", icon=":material/chat:")
    if b["checked_in_at"]:
        st.success(_("Checked in on {when}. Welcome!", when=E.fmt_utc(b["checked_in_at"], "%d %b %Y, %I:%M %p")))
    st.markdown(f"**{_('Event details')}:** [{P.event_url(ev['code'])}]({P.event_url(ev['code'])})")
    if contact := P.contact_text(ev):
        st.markdown(f"**{_('Organizer contact')}:** {contact}")
    if allow_cancel and E.attendee_can_cancel(ev, b)[0]:
        st.link_button(_("Cancel this booking"), P.cancel_url(b["token"]), icon=":material/event_busy:")
        if ev["is_paid"]:
            st.caption(_("Refunds for paid tickets are handled by the organizer."))
