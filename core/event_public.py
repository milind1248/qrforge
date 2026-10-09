"""Public event pages (no login): booking page (?event=), attendee pass (?pass=) and entrance staff scanner (?checkin=)."""
import html
from urllib.parse import quote

import streamlit as st

from core import event_db as E, event_mail, event_pass as P, event_ui, upi
from core.event_db import BookingError
from core import i18n
from core.i18n import _

MAX_SHOT = 6 * 1024 * 1024


def _shell(title_html: str):
    st.markdown(f"<div style='max-width:620px;margin:0 auto'>{title_html}</div>", unsafe_allow_html=True)


def tr_error(msg: str) -> str:
    """Booking error messages come from the database layer in English; translate the fixed ones and the two that carry a number."""
    import re
    m = re.fullmatch(r"You can book up to (\d+) tickets at a time\.", msg)
    if m:
        return _("You can book up to {n} tickets at a time.", n=m.group(1))
    m = re.fullmatch(r"Only (\d+) seat\(s\) left\. Reduce the number of tickets\.", msg)
    if m:
        return _("Only {n} seat(s) left. Reduce the number of tickets.", n=m.group(1))
    return _(msg)


def _center():
    _c1, mid, _c3 = st.columns([1, 3, 1])
    with mid:
        i18n.lang_switcher()
    return mid


def _upi_url(ev: dict, total: int, ref: str) -> str:
    return f"upi://pay?pa={quote(ev['upi_id'] or '')}&pn={quote(ev['upi_name'] or ev['name'])}&am={total}&cu=INR&tn={quote('Event ' + ev['code'])}"


def _info_card(ev: dict):
    stt = E.stats(ev["id"])
    price = _("Rs {price} per ticket", price=ev["price"]) if ev["is_paid"] else _("Free")
    desc = f"<p style='color:#475569;margin:.6rem 0 0'>{html.escape(ev['description'])}</p>" if ev.get("description") else ""
    maps = f" &middot; <a href='{html.escape(ev['map_url'])}' target='_blank'>{_('Map')}</a>" if ev.get("map_url", "") and ev["map_url"].startswith("http") else ""
    st.markdown(
        f"<div style='background:linear-gradient(135deg,#4F46E5,#7C3AED);color:#fff;border-radius:22px;padding:22px 24px;margin-bottom:12px'>"
        f"<div style='font-size:12px;letter-spacing:.14em;opacity:.8;font-weight:700'>{_('EVENT')}</div>"
        f"<div style='font-size:30px;font-weight:800;line-height:1.2'>{html.escape(ev['name'])}</div>"
        f"<div style='margin-top:10px;font-size:16px'>&#128197; {html.escape(P.nice_date(ev))}</div>"
        f"<div style='font-size:16px'>&#128205; {html.escape(ev['venue'])}{maps}</div>"
        f"<div style='font-size:16px'>&#127903; {price} &middot; {_('{n} of {cap} seats left', n=stt['remaining'], cap=ev['capacity'])}</div></div>{desc}", unsafe_allow_html=True)
    st.caption(_("Registration closes {when}", when=E.deadline_dt(ev).strftime("%a, %d %b %Y, %I:%M %p").replace(" 0", " ")))


def booking_page(code: str):
    ev = E.get_event_by_code(code)
    if not ev:
        _shell(f"<div class='card' style='text-align:center'><h3>{_('Event not found')}</h3><p>{_('This link is wrong or the event was removed.')}</p></div>")
        st.stop()
    with _center():
        _info_card(ev)
        open_, why = E.registration_state(ev)
        done = st.session_state.get(f"ev_done_{code}")
        if done:
            _confirmation(ev, done)
            st.stop()
        if not open_:
            st.warning(_(why), icon=":material/event_busy:")
            _find_pass(ev)
            st.stop()
        _booking_form(ev)
        _find_pass(ev)
        st.stop()


def _booking_form(ev: dict):
    code = ev["code"]
    maxt = int(ev["max_tickets"])
    left = E.stats(ev["id"])["remaining"]
    top = max(1, min(maxt, left))
    with st.container(border=True):
        st.subheader(_("Book your seat"))
        n = st.number_input(_("Number of tickets"), 1, top, 1, key=f"ev_n_{code}") if top > 1 else 1
        names = []
        for i in range(int(n)):
            names.append(st.text_input(_("Full name") if n == 1 else _("Attendee {i} name", i=i + 1), key=f"ev_name_{code}_{i}", max_chars=80))
        email = st.text_input(_("Email (your pass is sent here)"), key=f"ev_email_{code}", max_chars=120)
        phone = ""
        if ev["collect_phone"]:
            phone = st.text_input(_("Mobile number (for WhatsApp pass)"), key=f"ev_phone_{code}", max_chars=20)
        extra = ""
        if ev.get("custom_label"):
            extra = st.text_input(ev["custom_label"], key=f"ev_extra_{code}", max_chars=200)
        pay_ref, shot = "", None
        if ev["is_paid"]:
            total = int(ev["price"]) * int(n)
            st.markdown("##### " + _("Pay Rs {total} by UPI", total=total))
            if ev.get("upi_id"):
                c1, c2 = st.columns([1, 1.3])
                c1.image(P.qr_png_bytes(_upi_url(ev, total, ""), 360), caption=_("Scan with any UPI app"), width="stretch")
                c2.markdown(f"**UPI ID:** `{ev['upi_id']}`  \n**Amount:** Rs {total}  \n" + (f"{html.escape(ev['pay_note'])}" if ev.get("pay_note") else ""))
            st.caption(_("After paying, enter the transaction ID shown in your payment app. The organizer verifies it and your pass is emailed on approval."))
            pay_ref = st.text_input(_("UPI transaction ID (UTR)"), key=f"ev_utr_{code}", max_chars=30)
            shot = st.file_uploader(_("Payment screenshot (optional)"), type=["png", "jpg", "jpeg"], key=f"ev_shot_{code}")
        agree = st.checkbox(_("I agree to share these details with the event organizer."), key=f"ev_agree_{code}")
        if st.button(_("Confirm booking") if not ev["is_paid"] else _("Submit payment details"), type="primary", width="stretch", key=f"ev_go_{code}", disabled=not agree):
            try:
                pay_shot = pay_mime = ""
                if shot is not None:
                    raw = shot.getvalue()
                    if len(raw) > MAX_SHOT:
                        raise BookingError("Screenshot is too large (max 6 MB).")
                    try:
                        pay_shot, pay_mime = upi.prepare_screenshot(raw)
                    except Exception:  # noqa: BLE001
                        raise BookingError("That file is not a valid image.")
                made = E.create_bookings(ev, names, email, phone, extra, pay_ref, pay_shot, pay_mime)
            except BookingError as e:
                st.error(tr_error(str(e)))
                return
            full = [E.get_by_token(m["token"]) for m in made]
            if ev["is_paid"]:
                event_mail.send_payment_received(ev, full)
                event_mail.notify_organizer_payment(ev, E.organizer_contact(ev), full)
            else:
                event_mail.send_passes(ev, full)
            st.session_state[f"ev_done_{code}"] = [m["token"] for m in made]
            st.rerun()


def _confirmation(ev: dict, tokens: list[str]):
    bks = [E.get_by_token(t) for t in tokens]
    bks = [b for b in bks if b]
    if ev["is_paid"]:
        st.success(_("Payment details received. The organizer will verify them and email your pass."), icon=":material/hourglass_top:")
    else:
        st.success(_("You are booked! A confirmation with your pass was sent to {email}.", email=bks[0]["email"]), icon=":material/check_circle:")
    for i, b in enumerate(bks):
        event_ui.pass_view(ev, b, f"done_{ev['code']}_{i}")
    if st.button(_("Book another seat"), key=f"ev_again_{ev['code']}"):
        st.session_state.pop(f"ev_done_{ev['code']}", None)
        st.rerun()


def _find_pass(ev: dict):
    with st.expander(_("Already booked? Find my pass")):
        with st.form(f"ev_find_{ev['code']}"):
            em = st.text_input(_("Email used for booking"))
            go = st.form_submit_button(_("Email me my pass"))
        if go:
            found = E.bookings_for_email(ev["id"], em)
            if found:
                active = [b for b in found if b["status"] == "confirmed"]
                if active:
                    event_mail.send_passes(ev, active)
            # same message either way, so nobody can probe which emails are registered
            st.info(_("If that email has a booking, we just sent the pass to it. Check your inbox and spam folder."))


def pass_page(token: str):
    b = E.get_by_token(token)
    if not b:
        _shell(f"<div class='card' style='text-align:center'><h3>{_('Pass not found')}</h3><p>{_('This pass link is not valid.')}</p></div>")
        st.stop()
    ev = E.get_event(b["event_id"])
    with _center():
        if ev["status"] == "cancelled":
            st.error(_("This event has been cancelled."))
        event_ui.pass_view(ev, b, "pp")
        st.caption(_("Event page: {url}", url=P.event_url(ev["code"])))
    st.stop()


def cancel_page(token: str):
    b = E.get_by_token(token)
    if not b:
        _shell(f"<div class='card' style='text-align:center'><h3>{_('Booking not found')}</h3><p>{_('This cancel link is not valid.')}</p></div>")
        st.stop()
    ev = E.get_event(b["event_id"])
    with _center():
        st.markdown("### " + _("Cancel your registration"))
        st.markdown(f"**{html.escape(ev['name'])}**<br>{html.escape(P.nice_date(ev))}<br>{html.escape(ev['venue'])}<br>"
                    f"{_('Attendee')}: **{html.escape(b['name'])}** &nbsp;·&nbsp; {_('Booking ID')} **{html.escape(b['ref'])}**", unsafe_allow_html=True)
        ok, why = E.attendee_can_cancel(ev, b)
        done = st.session_state.get(f"cx_done_{token}")
        if done:
            st.success(_("Your registration is cancelled. The seat was released and your pass no longer works. A confirmation was emailed to you."), icon=":material/check_circle:")
        elif not ok:
            st.warning(_(why), icon=":material/info:")
        else:
            st.warning(_("Are you sure? Your pass and QR code will stop working and the seat goes back to other people. This cannot be undone."), icon=":material/warning:")
            if ev["is_paid"]:
                st.caption(_("Refunds for paid tickets are handled by the organizer."))
            c1, c2 = st.columns(2)
            if c1.button(_("Yes, cancel my registration"), type="primary", width="stretch", key=f"cx_yes_{token}"):
                done_rows = E.cancel([b["id"]], "attendee", "cancelled by attendee")
                if done_rows:
                    event_mail.send_cancelled(ev, done_rows[0])
                    event_mail.notify_organizer_cancel(ev, E.organizer_contact(ev), done_rows[0])
                st.session_state[f"cx_done_{token}"] = True
                st.rerun()
            c2.link_button(_("No, keep my booking"), P.pass_url(token), width="stretch")
        st.caption(_("Questions? Contact the organizer: {who}", who=P.contact_text(ev)) if P.contact_text(ev) else "")
    st.stop()


def staff_page(code: str):
    ev = E.get_event_by_code(code)
    if not ev:
        _shell(f"<div class='card' style='text-align:center'><h3>{_('Event not found')}</h3></div>")
        st.stop()
    with _center():
        st.markdown(f"### &#128274; Entrance check-in<br><span style='font-size:16px;font-weight:600'>{html.escape(ev['name'])}</span>", unsafe_allow_html=True)
        okkey = f"staff_ok_{code}"
        if not st.session_state.get(okkey):
            with st.form("staff_pin"):
                pin = st.text_input(_("Staff PIN"), type="password", max_chars=12)
                go = st.form_submit_button(_("Open scanner"), type="primary", width="stretch")
            if go:
                ok, msg = E.verify_pin(ev, pin)
                if ok:
                    st.session_state[okkey] = True
                    st.rerun()
                else:
                    st.error(msg)
            st.stop()
        event_ui.scanner_panel(ev["id"], "gate staff", f"gate_{code}")
        if st.button(_("Lock scanner"), key=f"staff_lock_{code}"):
            st.session_state.pop(okkey, None)
            st.rerun()
    st.stop()


def handle_routes():
    """Called from app.py before navigation. Renders and stops the run when the URL is an event link."""
    qp = st.query_params
    if t := qp.get("pass"):
        pass_page(str(t))
    if t := qp.get("cancel"):
        cancel_page(str(t))
    if c := qp.get("checkin"):
        staff_page(str(c))
    if c := qp.get("event"):
        booking_page(str(c))
