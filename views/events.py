from core import license as _license

_license.require()
import base64
from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from core import auth, event_db as E, event_export, event_mail, event_pass as P, event_ui
from core.plans import get_plan

user = auth.current_user()
plan = get_plan(user["plan"])
is_admin = user["role"] == "admin"
max_events, max_att = E.EVENT_LIMITS.get(plan.key, E.EVENT_LIMITS["free"])

st.title("Events")
st.caption("Sell or share free passes, scan guests at the door, and export attendance. Times are in India time (IST).")
if msg := st.session_state.pop("ev_flash", None):
    st.toast(msg, icon=":material/check_circle:", duration="long")      # a toast, not an element: it must not shift the page layout (that resets tabs and selections)

STATUS_LABEL = event_export.STATUS_LABEL


def _flash(msg: str):
    st.session_state["ev_flash"] = msg
    st.rerun()


# ----------------------------------------------------------------------------- create / edit form
def event_form(existing: dict | None, key: str):
    ev = existing or {}
    today = E.now_ist().date()
    with st.form(key):
        name = st.text_input("Event name", ev.get("name", ""), max_chars=100)
        desc = st.text_area("Description (optional)", ev.get("description") or "", max_chars=600, height=90)
        venue = st.text_input("Venue", ev.get("venue", ""), max_chars=150, placeholder="Hall name, address or 'Online'")
        map_url = st.text_input("Map link (optional)", ev.get("map_url") or "", placeholder="https://maps.google.com/...")
        c1, c2, c3 = st.columns(3)
        d_default = datetime.strptime(ev["event_date"], "%Y-%m-%d").date() if ev.get("event_date") else today + timedelta(days=7)
        s_default = datetime.strptime(ev["start_time"], "%H:%M").time() if ev.get("start_time") else time(18, 0)
        e_default = datetime.strptime(ev["end_time"], "%H:%M").time() if ev.get("end_time") else time(21, 0)
        edate = c1.date_input("Date", d_default, format="DD/MM/YYYY")
        stime = c2.time_input("Starts", s_default, step=900)
        etime = c3.time_input("Ends", e_default, step=900)
        c4, c5 = st.columns(2)
        capacity = c4.number_input(f"Maximum capacity (up to {max_att:,} on your plan)", 1, 100000, int(ev.get("capacity") or 100), step=10)
        max_tix = c5.number_input("Tickets per booking", 1, 10, int(ev.get("max_tickets") or 4))
        has_dl = st.checkbox("Set a registration deadline (otherwise registration closes when the event starts)", value=bool(ev.get("reg_deadline") and ev["reg_deadline"] != f"{ev.get('event_date')} {ev.get('start_time')}"))
        d1, d2 = st.columns(2)
        dl_default = E.deadline_dt(ev) if ev.get("reg_deadline") else datetime.combine(d_default, s_default) - timedelta(hours=2)
        dl_date = d1.date_input("Deadline date", dl_default.date(), format="DD/MM/YYYY")
        dl_time = d2.time_input("Deadline time", dl_default.time().replace(second=0, microsecond=0), step=900)
        st.markdown("**Ticketing**")
        paid = st.radio("Registration", ["Free", "Paid (UPI, you approve each payment)"], index=1 if ev.get("is_paid") else 0, horizontal=True)
        p1, p2, p3 = st.columns(3)
        price = p1.number_input("Ticket price (Rs)", 0, 100000, int(ev.get("price") or 0), step=50)
        upi_id = p2.text_input("Your UPI ID", ev.get("upi_id") or "", placeholder="name@bank")
        upi_name = p3.text_input("Payee name", ev.get("upi_name") or "")
        pay_note = st.text_input("Payment note shown to attendees (optional)", ev.get("pay_note") or "", max_chars=150)
        st.markdown("**Attendee details**")
        a1, a2 = st.columns(2)
        collect_phone = a1.checkbox("Ask for mobile number (enables WhatsApp pass)", value=bool(ev.get("collect_phone", 1)))
        custom = a2.text_input("Extra question (optional)", ev.get("custom_label") or "", placeholder="e.g. Company, T-shirt size", max_chars=60)
        contact = st.text_input("Organizer contact shown to attendees (optional)", ev.get("contact_info") or "", placeholder="Phone or email for questions", max_chars=120)
        go = st.form_submit_button("Save changes" if existing else "Create event", type="primary", width="stretch")
    if not go:
        return None
    d = {"name": name, "description": desc.strip(), "venue": venue.strip(), "map_url": map_url.strip(), "event_date": edate.strftime("%Y-%m-%d"),
         "start_time": stime.strftime("%H:%M"), "end_time": etime.strftime("%H:%M"), "capacity": int(capacity), "max_tickets": int(max_tix),
         "reg_deadline": f"{dl_date.strftime('%Y-%m-%d')} {dl_time.strftime('%H:%M')}" if has_dl else None,
         "is_paid": 1 if paid.startswith("Paid") else 0, "price": int(price), "upi_id": upi_id.strip(), "upi_name": upi_name.strip(), "pay_note": pay_note.strip(),
         "collect_phone": 1 if collect_phone else 0, "custom_label": custom.strip(), "contact_info": contact.strip()}
    if d["end_time"] <= d["start_time"]:
        d["end_time"] = None            # overnight/unknown end: stored as "no end time"
    errs = E.validate_event(d, plan.key, existing["id"] if existing else None, user["id"])
    if existing and d["capacity"] < E.stats(existing["id"])["confirmed"] + E.stats(existing["id"])["pending"]:
        errs.append("Capacity cannot be lower than the seats already booked.")
    if errs:
        for e in errs:
            st.error(e)
        return None
    return d


# ----------------------------------------------------------------------------- attendee table + actions
def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{"Booking ID": b["ref"], "Event": b["event_name"], "Name": b["name"], "Email": b["email"], "Phone": b["phone"] or "",
                          "Status": STATUS_LABEL.get(b["status"], b["status"]), "Paid (Rs)": b["amount"] or 0, "UPI ref": b["pay_ref"] or "",
                          "Checked in": "Yes" if b["checked_in_at"] and b["status"] == "confirmed" else "No",
                          "Check-in time": E.fmt_utc(b["checked_in_at"], "%d %b %Y, %I:%M %p") if b["checked_in_at"] else "",
                          "Booked": E.fmt_utc(b["created_at"], "%d %b %Y, %I:%M %p"), "Note": b["review_note"] or ""} for b in rows])


def _ci_range(key: str):
    """Check-in date/time filter -> (from_utc, to_utc) strings or (None, None)."""
    on = st.checkbox("Filter by check-in date and time", key=f"{key}_ci_on")
    if not on:
        return None, None
    today = E.now_ist().date()
    a, b, c, d = st.columns(4)
    d1 = a.date_input("From date", today, key=f"{key}_d1", format="DD/MM/YYYY")
    t1 = b.time_input("From time", time(0, 0), key=f"{key}_t1", step=900)
    d2 = c.date_input("To date", today, key=f"{key}_d2", format="DD/MM/YYYY")
    t2 = d.time_input("To time", time(23, 59), key=f"{key}_t2", step=60)
    return E.ist_to_utc_str(d1, t1), E.ist_to_utc_str(d2, t2.replace(second=59))


def explorer(event_ids: list[int], key: str, actions: bool = True):
    """Search + filter attendees. Returns the filtered rows (used for exports)."""
    f1, f2, f3 = st.columns([2, 2, 1.4])
    text = f1.text_input("Search name, email, phone or booking ID", key=f"{key}_q")
    stat = f2.multiselect("Status", list(STATUS_LABEL), format_func=STATUS_LABEL.get, key=f"{key}_st")
    chk = f3.selectbox("Attendance", ["all", "in", "not"], format_func={"all": "Everyone", "in": "Checked in", "not": "Not arrived"}.get, key=f"{key}_chk")
    ci_from, ci_to = _ci_range(key)
    rows = E.search_bookings(event_ids, text, stat or None, chk, ci_from, ci_to)
    st.caption(f"{len(rows)} attendee(s) match")
    if not rows:
        st.info("No attendees match these filters yet.")
        return rows
    sel = st.dataframe(_df(rows), hide_index=True, width="stretch", on_select="rerun", selection_mode="multi-row", key=f"{key}_tbl")
    picked = [rows[i] for i in sel.selection.rows if i < len(rows)]
    if actions and picked:
        _actions(picked, key)
    return rows


def _actions(picked: list[dict], key: str):
    st.markdown(f"**{len(picked)} selected**")
    ids = [b["id"] for b in picked]
    by = user["name"]
    evs = {}
    def ev_of(b):
        return evs.setdefault(b["event_id"], E.get_event(b["event_id"]))
    pend = [b for b in picked if b["status"] == "pending_payment"]
    c = st.columns(5)
    if c[0].button("Approve payment", key=f"{key}_ap", disabled=not pend, width="stretch", icon=":material/check:"):
        done = E.approve([b["id"] for b in pend], by)
        for b in done:
            event_mail.send_passes(ev_of(b), [b])
        _flash(f"Approved {len(done)} booking(s). Passes are being emailed.")
    if c[1].button("Reject payment", key=f"{key}_rj", disabled=not pend, width="stretch", icon=":material/close:"):
        done = E.reject([b["id"] for b in pend], by)
        for b in done:
            event_mail.send_rejected(ev_of(b), b)
        _flash(f"Rejected {len(done)} booking(s).")
    live = [b for b in picked if b["status"] in ("confirmed", "pending_payment")]
    if c[2].button("Cancel booking", key=f"{key}_cn", disabled=not live, width="stretch", icon=":material/event_busy:"):
        done = E.cancel([b["id"] for b in live], by)
        for b in done:
            event_mail.send_cancelled(ev_of(b), b)
        _flash(f"Cancelled {len(done)} booking(s). Their seats are free again.")
    conf = [b for b in picked if b["status"] == "confirmed"]
    if c[3].button("Resend pass", key=f"{key}_rs", disabled=not conf, width="stretch", icon=":material/forward_to_inbox:"):
        for b in conf:
            event_mail.send_passes(ev_of(b), [E.get_booking(b["id"])])
        _flash(f"Pass emailed to {len(conf)} attendee(s).")
    notin = [b for b in conf if not b["checked_in_at"]]
    if c[4].button("Check in manually", key=f"{key}_mc", disabled=not notin, width="stretch", icon=":material/how_to_reg:"):
        for b in notin:
            E.manual_checkin(b["id"], f"{by} (manual)")
        _flash(f"Checked in {len(notin)} attendee(s).")
    undo = [b for b in conf if b["checked_in_at"]]
    if undo and st.button("Undo check-in", key=f"{key}_un", icon=":material/undo:"):
        for b in undo:
            E.undo_checkin(b["id"], by)
        _flash(f"Check-in undone for {len(undo)} attendee(s).")
    if len(picked) == 1:
        b = picked[0]
        shot = E.payment_shot(b["id"]) if b["has_shot"] else None
        with st.expander("Booking details", expanded=True):
            st.write(f"**{b['name']}** · {b['email']} · {b['phone'] or 'no phone'}")
            if b["extra"]:
                st.write(f"Extra detail: {b['extra']}")
            if b["pay_ref"]:
                st.write(f"UPI transaction ID: `{b['pay_ref']}` · Rs {b['amount']}")
            if b["review_note"]:
                st.caption(b["review_note"])
            st.code(P.pass_url(b["token"]), language=None)
            if shot and shot["pay_shot"]:
                st.image(base64.b64decode(shot["pay_shot"]), caption="Payment screenshot", width=320)


# ----------------------------------------------------------------------------- per-event screen
def add_registration(ev: dict):
    eid = ev["id"]
    with st.expander("Add a registration (walk-in, guest, VIP)", icon=":material/person_add:"):
        st.caption("Add anyone yourself. Works even after registration closes, as long as seats are free. They get their pass by email.")
        with st.form(f"addreg{eid}", clear_on_submit=True):
            a, b = st.columns(2)
            name = a.text_input("Full name", max_chars=80)
            email = b.text_input("Email (the pass is sent here)", max_chars=120)
            c, d = st.columns(2)
            phone = c.text_input("Mobile (optional)", max_chars=20)
            extra = d.text_input(ev["custom_label"] or "Extra detail (optional)", max_chars=200)
            comp = False
            if ev["is_paid"]:
                comp = st.radio("Payment", [f"Paid already (Rs {ev['price']}, counted in revenue)", "Complimentary (Rs 0)"], horizontal=True).startswith("Compl")
            send = st.checkbox("Email the pass", value=True)
            go = st.form_submit_button("Add registration", type="primary")
        if go:
            try:
                made = E.create_bookings(ev, [name], email, phone, extra, by=user["name"], amount=0 if comp else None)
            except E.BookingError as e:
                st.error(str(e))
                return
            full = [E.get_by_token(m["token"]) for m in made]
            if send:
                event_mail.send_passes(ev, full)
            _flash(f"Added {full[0]['name']} ({full[0]['ref']})." + (" Pass emailed." if send and event_mail.notify.enabled() else ""))


def event_screen(ev: dict):
    eid = ev["id"]
    tabs = st.tabs(["Overview", "Attendees", "Check-in", "Reports (Excel)", "Settings"])
    with tabs[0]:
        overview(ev)
    with tabs[1]:
        add_registration(ev)
        explorer([eid], f"att{eid}")
    with tabs[2]:
        st.caption("Use this on your phone at the entrance. Or share the staff link and PIN so volunteers can scan without an account.")
        event_ui.scanner_panel(eid, user["name"], f"org{eid}")
    with tabs[3]:
        reports(ev)
    with tabs[4]:
        settings(ev)


@st.fragment(run_every=8)
def live_numbers(eid: int):
    s = E.stats(eid)
    c = st.columns(5)
    c[0].metric("Confirmed", s["confirmed"], help="Seats booked with a valid pass")
    c[1].metric("Payment pending", s["pending"])
    c[2].metric("Checked in", f"{s['checked_in']} / {s['confirmed']}")
    c[3].metric("Seats left", s["remaining"])
    c[4].metric("Revenue", f"Rs {s['revenue']:,}")
    st.progress(min(1.0, s["checked_in"] / s["confirmed"]) if s["confirmed"] else 0.0, text=f"Live attendance {s['rate']}%  (updates every few seconds)")


def overview(ev: dict):
    eid = ev["id"]
    stat_txt = {"open": "Registration open", "closed": "Registration closed", "cancelled": "Event cancelled"}[ev["status"]]
    st.markdown(f"**{ev['name']}** · {P.nice_date(ev)} · {ev['venue']} · _{stat_txt}_")
    live_numbers(eid)
    l1, l2 = st.columns(2)
    with l1:
        st.markdown("**Booking page**")
        st.code(P.event_url(ev["code"]), language=None)
        st.link_button("Open booking page", P.event_url(ev["code"]), icon=":material/open_in_new:")
        st.image(P.qr_png_bytes(P.event_url(ev["code"]), 300), caption="QR for posters and invitations", width=170)
    with l2:
        st.markdown("**Entrance staff scanner**")
        st.code(P.staff_url(ev["code"]), language=None)
        st.markdown(f"Staff PIN: `{ev['staff_pin']}`")
        st.caption("Volunteers open this link, enter the PIN, and scan passes. They never see attendee lists.")
    bt, ct = E.booking_times(eid), E.checkin_times(eid)
    g1, g2 = st.columns(2)
    if bt:
        s = pd.Series(1, index=[E.utc_to_ist(t).date() for t in bt]).groupby(level=0).sum()
        g1.markdown("**Bookings per day**")
        g1.bar_chart(s)
    if ct:
        s = pd.Series(1, index=[E.utc_to_ist(t).strftime("%d %b %H:00") for t in ct]).groupby(level=0, sort=False).sum()
        g2.markdown("**Check-ins per hour**")
        g2.bar_chart(s)
    st.markdown("**Recent scans**")
    event_ui.scans_table(eid, 10)


def reports(ev: dict):
    eid = ev["id"]
    st.markdown("Download Excel reports. Each file has a Summary sheet and, optionally, the scan log.")
    inc_log = st.checkbox("Include the scan log sheet", True, key=f"rep_log{eid}")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Complete attendee list")
        st.caption("Everyone who booked, with status, payment and check-in details.")
        everyone = E.search_bookings([eid])
        st.download_button(f"Download attendee list ({len(everyone)})", lambda: event_export.build([ev], everyone, "full", inc_log), f"{ev['code']}-attendees.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_full{eid}", type="primary", icon=":material/download:", disabled=not everyone)
    with c2:
        st.markdown("##### Actual check-in records")
        st.caption("Only people who really arrived, with the exact date and time they were scanned.")
        ci_from, ci_to = _ci_range(f"rep{eid}")
        arrived = [b for b in E.search_bookings([eid], checked="in", ci_from=ci_from, ci_to=ci_to) if b["status"] == "confirmed"]
        st.download_button(f"Download check-ins ({len(arrived)})", lambda: event_export.build([ev], arrived, "checkins", inc_log), f"{ev['code']}-checkins.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_ci{eid}", type="primary", icon=":material/download:", disabled=not arrived)


def settings(ev: dict):
    eid = ev["id"]
    s = E.stats(eid)
    st.markdown("##### Event status")
    c = st.columns(3)
    if ev["status"] == "open" and c[0].button("Close registration", key=f"cl{eid}", width="stretch"):
        E.set_status(eid, "closed")
        _flash("Registration closed. Existing passes still work.")
    if ev["status"] == "closed" and c[0].button("Reopen registration", key=f"ro{eid}", width="stretch"):
        E.set_status(eid, "open")
        _flash("Registration reopened.")
    if c[1].button("New staff PIN", key=f"pin{eid}", width="stretch"):
        E.new_pin(eid)
        _flash("New staff PIN created. Old PIN no longer works.")
    if ev["status"] != "cancelled":
        with st.expander("Cancel this event"):
            st.warning("All passes stop working and every attendee gets an email. This cannot be undone.")
            sure = st.checkbox("Yes, cancel the event", key=f"cev{eid}")
            if st.button("Cancel event and notify attendees", disabled=not sure, key=f"cevb{eid}"):
                E.set_status(eid, "cancelled")
                for b in E.search_bookings([eid], statuses=["confirmed", "pending_payment"]):
                    event_mail.send_cancelled(ev, b, "event")
                _flash("Event cancelled. Attendees are being emailed.")
    st.markdown("##### Edit details")
    d = event_form(ev, f"edit{eid}")
    if d:
        E.update_event(eid, d)
        _flash("Event updated.")
    st.markdown("##### Co-organizers")
    st.caption("People you add can see this event's dashboard, attendees and scanner. They need a QRForge account.")
    for m in E.team(eid):
        a, b = st.columns([4, 1])
        a.write(f"{m['name']} · {m['email']}")
        if (ev["owner_id"] == user["id"] or is_admin) and b.button("Remove", key=f"rm{eid}_{m['id']}"):
            E.remove_team_member(eid, m["id"])
            st.rerun()
    if ev["owner_id"] == user["id"] or is_admin:
        with st.form(f"team{eid}", clear_on_submit=True):
            em = st.text_input("Add co-organizer by email")
            if st.form_submit_button("Add") and em.strip():
                err = E.add_team_member(eid, em)
                if err:
                    st.error(err)
                else:
                    _flash("Co-organizer added.")
    if s["confirmed"] + s["pending"] + s["cancelled"] == 0:
        if st.button("Delete this event", key=f"del{eid}"):
            E.delete_event(eid)
            _flash("Event deleted.")


# ----------------------------------------------------------------------------- page
events = E.list_events(user["id"], is_admin)
tab_my, tab_new, tab_all = st.tabs(["My events", "Create event", "All attendees"])

with tab_my:
    if not events:
        st.info("You have no events yet. Open the Create event tab to make your first one.", icon=":material/event:")
    else:
        labels = {e["id"]: f"{e['name']} · {e['event_date']}" + (f" · by {e['owner_name']}" if e["owner_id"] != user["id"] else "") for e in events}   # labels must stay constant: they are part of the selectbox identity
        ids = list(labels)
        if (goto := st.session_state.pop("ev_goto", None)) in ids:
            st.session_state["ev_sel"] = goto
        if st.session_state.get("ev_sel") not in ids:
            st.session_state["ev_sel"] = ids[0]
        sel = st.selectbox("Event", ids, format_func=labels.get, key="ev_sel")
        event_screen(E.get_event(sel))

with tab_new:
    if sum(1 for e in events if e["owner_id"] == user["id"] and e["status"] != "cancelled") >= max_events and not is_admin:
        st.warning(f"Your {plan.name} plan includes {max_events} active event(s) with up to {max_att:,} attendees each. Cancel an event or upgrade for more.", icon=":material/lock:")
        st.page_link("views/pricing.py", label="See plans", icon=":material/workspace_premium:")
    else:
        if made := st.session_state.get("ev_created"):
            st.success(f"Event created: **{made['name']}**. Open the **My events** tab to manage it. Booking link to share: {P.event_url(made['code'])}", icon=":material/check_circle:")
        d = event_form(None, "create_event")
        if d:
            new = E.create_event(user["id"], d)
            st.session_state["ev_goto"] = new["id"]
            st.session_state["ev_created"] = new
            st.rerun()

with tab_all:
    if not events:
        st.info("Attendees from all your events will show here.")
    else:
        pick = st.multiselect("Events", [e["id"] for e in events], default=[e["id"] for e in events], format_func=lambda i: next(e["name"] for e in events if e["id"] == i), key="all_ev")
        rows = explorer(pick, "all", actions=True)
        if rows:
            evs = [e for e in events if e["id"] in pick]
            x1, x2 = st.columns(2)
            x1.download_button(f"Export filtered list ({len(rows)})", lambda: event_export.build(evs, rows, "full"), "attendees.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", key="all_dl_full")
            ci = [b for b in rows if b["checked_in_at"] and b["status"] == "confirmed"]
            x2.download_button(f"Export check-ins only ({len(ci)})", lambda: event_export.build(evs, ci, "checkins"), "checkins.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", key="all_dl_ci", disabled=not ci)
