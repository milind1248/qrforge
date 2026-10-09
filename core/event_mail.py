"""Event emails: booking confirmation with pass attachments, payment review notices, cancellations. Sent in background threads."""
import html

from core import event_db as E, event_pass as P, notify
from core.config import APP_NAME


def _rows(ev: dict, extra: list[tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    return [("Event", ev["name"]), ("When", P.nice_date(ev)), ("Venue", ev["venue"]), *(extra or [])]


def _organizer_line(ev: dict) -> str:
    c = P.contact_text(ev)
    return f" Questions? Contact the organizer: {html.escape(c)}." if c else ""


def send_passes(ev: dict, bookings: list[dict]):
    """Confirmation + one PDF pass per attendee (+ calendar file). Safe to call from the request thread: sending runs in the background."""
    if not bookings or not notify.enabled():
        return
    first = bookings[0]
    atts = []
    for b in bookings:
        atts.append((f"pass-{b['ref']}.pdf", P.pass_pdf(ev, b), "application/pdf"))
    atts.append(("event.ics", P.ics_text(ev, first).encode("utf-8"), "text/calendar"))
    rows = _rows(ev, [("Booking ID" + ("s" if len(bookings) > 1 else ""), ", ".join(b["ref"] for b in bookings)),
                      ("Attendee" + ("s" if len(bookings) > 1 else ""), ", ".join(b["name"] for b in bookings))])
    links = "<br>".join(f"<a href='{html.escape(P.pass_url(b['token']))}'>Open pass: {html.escape(b['name'])} ({html.escape(b['ref'])})</a>"
                        f" &middot; <a href='{html.escape(P.cancel_url(b['token']))}'>Cancel this booking</a>" for b in bookings)
    foot = (f"Your pass{'es are' if len(bookings) > 1 else ' is'} attached as PDF. Show the QR code at the entrance (on your phone or printed).<br>{links}<br>"
            f"<a href='{html.escape(P.event_url(ev['code']))}'>Event details</a>.{_organizer_line(ev)}")
    lines = "\n".join(f"{b['name']}: {b['ref']}\n  Pass: {P.pass_url(b['token'])}\n  Cancel: {P.cancel_url(b['token'])}" for b in bookings)
    text = (f"Your booking for {ev['name']} is confirmed.\n{lines}\nWhen: {P.nice_date(ev)}\nVenue: {ev['venue']}\nEvent details: {P.event_url(ev['code'])}\nOrganizer: {P.contact_text(ev)}")
    notify.send_async(first["email"], f"Your pass for {ev['name']} ({first['ref']})", text, notify._wrap("Booking confirmed", rows, foot), attachments=atts)


def send_payment_received(ev: dict, bookings: list[dict]):
    if not bookings or not notify.enabled():
        return
    total = sum(int(b["amount"] or 0) for b in bookings)
    rows = _rows(ev, [("Booking ID", ", ".join(b["ref"] for b in bookings)), ("Amount", f"Rs {total}"), ("Status", "Payment under review")])
    foot = f"Thank you! The organizer will verify your payment. Your pass will be emailed as soon as it is approved.{_organizer_line(ev)}"
    notify.send_async(bookings[0]["email"], f"We received your payment details for {ev['name']}",
                      f"We received your payment details for {ev['name']} (booking {bookings[0]['ref']}). You will get your pass once it is approved.",
                      notify._wrap("Payment received, under review", rows, foot))


def notify_organizer_payment(ev: dict, owner: dict, bookings: list[dict]):
    if not bookings or not owner or not notify.enabled():
        return
    total = sum(int(b["amount"] or 0) for b in bookings)
    rows = [("Event", ev["name"]), ("Attendee", f"{bookings[0]['name']} <{bookings[0]['email']}>"), ("Tickets", str(len(bookings))),
            ("Amount", f"Rs {total}"), ("UPI reference", bookings[0]["pay_ref"] or "-")]
    notify.send_async(owner["email"], f"[{APP_NAME}] Payment to review: {ev['name']}", "A booking is waiting for payment approval: " + "; ".join(f"{k}: {v}" for k, v in rows),
                      notify._wrap("Payment waiting for your approval", rows, f"Open Events in {APP_NAME} to approve or reject it."))


def send_rejected(ev: dict, b: dict, reason: str = ""):
    if not notify.enabled():
        return
    foot = f"Your payment could not be verified. {html.escape(reason or '')} If you already paid, reply to the organizer with your transaction details.{_organizer_line(ev)}"
    notify.send_async(b["email"], f"Your payment for {ev['name']} could not be verified", f"Payment for {ev['name']} ({b['ref']}) was not accepted. {reason}",
                      notify._wrap("Payment not accepted", _rows(ev, [("Booking ID", b["ref"])]), foot))


def send_cancelled(ev: dict, b: dict, why: str = "cancelled"):
    if not notify.enabled():
        return
    title = "Event cancelled" if why == "event" else "Booking cancelled"
    notify.send_async(b["email"], f"{title}: {ev['name']} ({b['ref']})", f"{title}: {ev['name']} ({b['ref']}).",
                      notify._wrap(title, _rows(ev, [("Booking ID", b["ref"])]), _organizer_line(ev).strip() or "We are sorry for the inconvenience."))


def notify_organizer_cancel(ev: dict, owner: dict, b: dict):
    if not owner or not notify.enabled():
        return
    rows = [("Event", ev["name"]), ("Attendee", f"{b['name']} <{b['email']}>"), ("Booking ID", b["ref"]), ("Cancelled by", "the attendee")]
    notify.send_async(owner["email"], f"[{APP_NAME}] Booking cancelled: {ev['name']} ({b['ref']})", "Booking cancelled by attendee: " + "; ".join(f"{k}: {v}" for k, v in rows),
                      notify._wrap("An attendee cancelled", rows, "The seat is free again. It also shows as Cancelled in your attendee report."))
