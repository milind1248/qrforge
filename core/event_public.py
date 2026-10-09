"""Public event pages (no login): booking page (?event=), attendee pass (?pass=) and entrance staff scanner (?checkin=)."""
import html
from urllib.parse import quote

import streamlit as st

from core import event_db as E, event_mail, event_pass as P, event_ui, upi
from core.event_db import BookingError

MAX_SHOT = 6 * 1024 * 1024


def _shell(title_html: str):
    st.markdown(f"<div style='max-width:620px;margin:0 auto'>{title_html}</div>", unsafe_allow_html=True)


def _center():
    _, mid, _ = st.columns([1, 3, 1])
    return mid


def _upi_url(ev: dict, total: int, ref: str) -> str:
    return f"upi://pay?pa={quote(ev['upi_id'] or '')}&pn={quote(ev['upi_name'] or ev['name'])}&am={total}&cu=INR&tn={quote('Event ' + ev['code'])}"


def _info_card(ev: dict):
    stt = E.stats(ev["id"])
    price = f"Rs {ev['price']} per ticket" if ev["is_paid"] else "Free"
    desc = f"<p style='color:#475569;margin:.6rem 0 0'>{html.escape(ev['description'])}</p>" if ev.get("description") else ""
    maps = f" &middot; <a href='{html.escape(ev['map_url'])}' target='_blank'>Map</a>" if ev.get("map_url", "") and ev["map_url"].startswith("http") else ""
    st.markdown(
        f"<div style='background:linear-gradient(135deg,#4F46E5,#7C3AED);color:#fff;border-radius:22px;padding:22px 24px;margin-bottom:12px'>"
        f"<div style='font-size:12px;letter-spacing:.14em;opacity:.8;font-weight:700'>EVENT</div>"
        f"<div style='font-size:30px;font-weight:800;line-height:1.2'>{html.escape(ev['name'])}</div>"
        f"<div style='margin-top:10px;font-size:16px'>&#128197; {html.escape(P.nice_date(ev))}</div>"
        f"<div style='font-size:16px'>&#128205; {html.escape(ev['venue'])}{maps}</div>"
        f"<div style='font-size:16px'>&#127903; {price} &middot; {stt['remaining']} of {ev['capacity']} seats left</div></div>{desc}", unsafe_allow_html=True)
    st.caption("Registration closes " + E.deadline_dt(ev).strftime("%a, %d %b %Y, %I:%M %p").replace(" 0", " "))


def booking_page(code: str):
    ev = E.get_event_by_code(code)
    if not ev:
        _shell("<div class='card' style='text-align:center'><h3>Event not found</h3><p>This link is wrong or the event was removed.</p></div>")
        st.stop()
    with _center():
        _info_card(ev)
        open_, why = E.registration_state(ev)
        done = st.session_state.get(f"ev_done_{code}")
        if done:
            _confirmation(ev, done)
            st.stop()
        if not open_:
            st.warning(why, icon=":material/event_busy:")
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
        st.subheader("Book your seat")
        n = st.number_input("Number of tickets", 1, top, 1, key=f"ev_n_{code}") if top > 1 else 1
        names = []
        for i in range(int(n)):
            names.append(st.text_input("Full name" if n == 1 else f"Attendee {i + 1} name", key=f"ev_name_{code}_{i}", max_chars=80))
        email = st.text_input("Email (your pass is sent here)", key=f"ev_email_{code}", max_chars=120)
        phone = ""
        if ev["collect_phone"]:
            phone = st.text_input("Mobile number (for WhatsApp pass)", key=f"ev_phone_{code}", max_chars=20)
        extra = ""
        if ev.get("custom_label"):
            extra = st.text_input(ev["custom_label"], key=f"ev_extra_{code}", max_chars=200)
        pay_ref, shot = "", None
        if ev["is_paid"]:
            total = int(ev["price"]) * int(n)
            st.markdown(f"##### Pay Rs {total} by UPI")
            if ev.get("upi_id"):
                c1, c2 = st.columns([1, 1.3])
                c1.image(P.qr_png_bytes(_upi_url(ev, total, ""), 360), caption="Scan with any UPI app", width="stretch")
                c2.markdown(f"**UPI ID:** `{ev['upi_id']}`  \n**Amount:** Rs {total}  \n" + (f"{html.escape(ev['pay_note'])}" if ev.get("pay_note") else ""))
            st.caption("After paying, enter the transaction ID shown in your payment app. The organizer verifies it and your pass is emailed on approval.")
            pay_ref = st.text_input("UPI transaction ID (UTR)", key=f"ev_utr_{code}", max_chars=30)
            shot = st.file_uploader("Payment screenshot (optional)", type=["png", "jpg", "jpeg"], key=f"ev_shot_{code}")
        agree = st.checkbox("I agree to share these details with the event organizer.", key=f"ev_agree_{code}")
        if st.button("Confirm booking" if not ev["is_paid"] else "Submit payment details", type="primary", width="stretch", key=f"ev_go_{code}", disabled=not agree):
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
                st.error(str(e))
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
        st.success("Payment details received. The organizer will verify them and email your pass.", icon=":material/hourglass_top:")
    else:
        st.success(f"You are booked! A confirmation with your pass was sent to {bks[0]['email']}.", icon=":material/check_circle:")
    for i, b in enumerate(bks):
        event_ui.pass_view(ev, b, f"done_{ev['code']}_{i}", allow_cancel=False)
    if st.button("Book another seat", key=f"ev_again_{ev['code']}"):
        st.session_state.pop(f"ev_done_{ev['code']}", None)
        st.rerun()


def _find_pass(ev: dict):
    with st.expander("Already booked? Find my pass"):
        with st.form(f"ev_find_{ev['code']}"):
            em = st.text_input("Email used for booking")
            go = st.form_submit_button("Email me my pass")
        if go:
            found = E.bookings_for_email(ev["id"], em)
            if found:
                active = [b for b in found if b["status"] == "confirmed"]
                if active:
                    event_mail.send_passes(ev, active)
            # same message either way, so nobody can probe which emails are registered
            st.info("If that email has a booking, we just sent the pass to it. Check your inbox and spam folder.")


def pass_page(token: str):
    b = E.get_by_token(token)
    if not b:
        _shell("<div class='card' style='text-align:center'><h3>Pass not found</h3><p>This pass link is not valid.</p></div>")
        st.stop()
    ev = E.get_event(b["event_id"])
    with _center():
        if ev["status"] == "cancelled":
            st.error("This event has been cancelled.")
        event_ui.pass_view(ev, b, "pp")
        st.caption(f"Event page: {P.event_url(ev['code'])}")
    st.stop()


def staff_page(code: str):
    ev = E.get_event_by_code(code)
    if not ev:
        _shell("<div class='card' style='text-align:center'><h3>Event not found</h3></div>")
        st.stop()
    with _center():
        st.markdown(f"### &#128274; Entrance check-in<br><span style='font-size:16px;font-weight:600'>{html.escape(ev['name'])}</span>", unsafe_allow_html=True)
        okkey = f"staff_ok_{code}"
        if not st.session_state.get(okkey):
            with st.form("staff_pin"):
                pin = st.text_input("Staff PIN", type="password", max_chars=12)
                go = st.form_submit_button("Open scanner", type="primary", width="stretch")
            if go:
                ok, msg = E.verify_pin(ev, pin)
                if ok:
                    st.session_state[okkey] = True
                    st.rerun()
                else:
                    st.error(msg)
            st.stop()
        event_ui.scanner_panel(ev["id"], "gate staff", f"gate_{code}")
        if st.button("Lock scanner", key=f"staff_lock_{code}"):
            st.session_state.pop(okkey, None)
            st.rerun()
    st.stop()


def handle_routes():
    """Called from app.py before navigation. Renders and stops the run when the URL is an event link."""
    qp = st.query_params
    if t := qp.get("pass"):
        pass_page(str(t))
    if c := qp.get("checkin"):
        staff_page(str(c))
    if c := qp.get("event"):
        booking_page(str(c))
