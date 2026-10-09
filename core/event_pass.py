"""Digital event pass: links, QR, PNG/PDF pass, on-screen HTML card, calendar (.ics) file and WhatsApp share link."""
import base64
import html
import io
import re
from datetime import timedelta, timezone
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFont

from core import db, event_db as E
from core.i18n import _
from core.config import BASE_URL
from core.qr_engine import render as render_qr

PASS_W, PASS_H = 1080, 1520
INDIGO, VIOLET, INK, MUTED = (79, 70, 229), (124, 58, 237), (15, 23, 42), (100, 116, 139)
FONT_DIRS = ("C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/truetype/liberation/", "/usr/share/fonts/truetype/noto/",
             "/usr/share/fonts/opentype/noto/", "/usr/share/fonts/noto/")


# ----------------------------------------------------------------------------- links
def pass_url(token: str) -> str:
    return f"{BASE_URL}/?pass={token}"


def event_url(code: str) -> str:
    return f"{BASE_URL}/?event={code}"


def cancel_url(token: str) -> str:
    return f"{BASE_URL}/?cancel={token}"


def organizer_email(ev: dict) -> str:
    u = db.get_user(ev["owner_id"])
    return u["email"] if u else ""


def contact_text(ev: dict) -> str:
    """Plain 'who to contact' line: organizer's account email plus the contact detail they typed in."""
    parts = [organizer_email(ev), (ev.get("contact_info") or "").strip()]
    return " / ".join(x for x in dict.fromkeys(parts) if x)


def staff_url(code: str) -> str:
    return f"{BASE_URL}/?checkin={code}"


def whatsapp_link(phone: str, text: str) -> str:
    """wa.me click-to-chat link (the sender taps Send in WhatsApp). 10-digit Indian numbers get the 91 prefix."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        digits = "91" + digits
    base = f"https://wa.me/{digits}" if len(digits) >= 11 else "https://wa.me/"
    return f"{base}?text={quote(text)}"


def pass_share_text(ev: dict, b: dict) -> str:
    return (f"Hi {b['name']}, here is your pass for {ev['name']} on {nice_date(ev)} at {ev['venue']}. "
            f"Booking ID {b['ref']}. Show this QR at the entrance: {pass_url(b['token'])}")


def nice_date(ev: dict) -> str:
    s = E.event_start(ev)
    return s.strftime("%a, %d %b %Y") + ", " + s.strftime("%I:%M %p").lstrip("0") + (
        " to " + E.event_end(ev).strftime("%I:%M %p").lstrip("0") if ev.get("end_time") else "")


def ticket_label_i18n(ev: dict, b: dict) -> str:
    return _("Paid  Rs {amt}", amt=b["amount"]) if ev["is_paid"] else _("Free entry")


def ticket_label(ev: dict, b: dict) -> str:
    return f"Paid  Rs {b['amount']}" if ev["is_paid"] else "Free entry"


# ----------------------------------------------------------------------------- QR + image pass
def qr_image(data: str, px: int = 520) -> Image.Image:
    img = render_qr(data, {"fg": "#0F172A", "bg": "#FFFFFF", "shape": "Square", "eye": "Square", "ecc": "Quartile (25%)"}, False, box=14)
    return img.resize((px, px), Image.NEAREST).convert("RGB")


def qr_png_bytes(data: str, px: int = 520) -> bytes:
    buf = io.BytesIO()
    qr_image(data, px).save(buf, "PNG")
    return buf.getvalue()


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (("arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "NotoSans-Bold.ttf") if bold
             else ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "NotoSans-Regular.ttf"))
    for d in FONT_DIRS:
        for n in names:
            try:
                return ImageFont.truetype(d + n, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _pick(text: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Font for a piece of text: a Devanagari-capable font (Hindi / Marathi names) when the text contains Devanagari, else the normal one."""
    if any("ऀ" <= ch <= "ॿ" for ch in text or ""):
        names = ("NirmalaB.ttf", "NotoSansDevanagari-Bold.ttf", "NotoSansDevanagariUI-Bold.ttf") if bold else ("Nirmala.ttf", "NotoSansDevanagari-Regular.ttf", "NotoSansDevanagariUI-Regular.ttf")
        for d in FONT_DIRS:
            for n in names:
                try:
                    return ImageFont.truetype(d + n, size)
                except OSError:
                    continue
    return _font(size, bold)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int) -> list[str]:
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(1, len(lines[-1]) - 3)] + "..."
    return lines


def pass_image(ev: dict, b: dict) -> Image.Image:
    """Printable pass: event name, date/time, venue, attendee, booking ID and the unique QR."""
    im = Image.new("RGB", (PASS_W, PASS_H), "white")
    d = ImageDraw.Draw(im)
    for y in range(330):                                   # gradient banner
        t = y / 330
        c = tuple(int(INDIGO[i] + (VIOLET[i] - INDIGO[i]) * t) for i in range(3))
        d.line([(0, y), (PASS_W, y)], fill=c)
    d.text((60, 44), "EVENT PASS", font=_font(30, True), fill=(210, 205, 255))
    f_title = _pick(ev["name"], 64, True)
    for i, ln in enumerate(_wrap(d, ev["name"], f_title, PASS_W - 120, 2)):
        d.text((60, 96 + i * 78), ln, font=f_title, fill="white")
    y = 380
    for label, value in (("DATE & TIME", nice_date(ev)), ("VENUE", ev["venue"])):
        d.text((60, y), label, font=_font(24, True), fill=MUTED)
        f = _pick(value, 38, True)
        for j, ln in enumerate(_wrap(d, value, f, PASS_W - 120, 2)):
            d.text((60, y + 34 + j * 46), ln, font=f, fill=INK)
        y += 34 + 46 * (len(_wrap(d, value, f, PASS_W - 120, 2)) or 1) + 26
    d.line([(60, y), (PASS_W - 60, y)], fill=(226, 232, 240), width=3)
    y += 24
    d.text((60, y), "ATTENDEE", font=_font(24, True), fill=MUTED)
    f_name = _pick(b["name"], 50, True)
    for j, ln in enumerate(_wrap(d, b["name"], f_name, PASS_W - 120, 1)):
        d.text((60, y + 34), ln, font=f_name, fill=INK)
    d.text((PASS_W - 60 - d.textlength(ticket_label(ev, b), font=_font(30, True)), y + 6), ticket_label(ev, b), font=_font(30, True), fill=INDIGO)
    y += 112
    qr = qr_image(pass_url(b["token"]), 520)
    box = Image.new("RGB", (qr.width + 48, qr.height + 48), "white")
    ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width - 1, box.height - 1), 28, outline=(203, 213, 225), width=4)
    box.paste(qr, (24, 24))
    im.paste(box, ((PASS_W - box.width) // 2, y))
    y += box.height + 26
    f_ref = _font(58, True)
    ref = b["ref"]
    d.text(((PASS_W - d.textlength(ref, font=f_ref)) / 2, y), ref, font=f_ref, fill=INK)
    d.text(((PASS_W - d.textlength("BOOKING ID", font=_font(22, True))) / 2, y + 70), "BOOKING ID", font=_font(22, True), fill=MUTED)
    d.rectangle([0, PASS_H - 70, PASS_W, PASS_H], fill=(241, 245, 249))
    foot = "Show this QR at the entrance  |  One entry per pass  |  Powered by QR Sugi"
    d.text(((PASS_W - d.textlength(foot, font=_font(24))) / 2, PASS_H - 48), foot, font=_font(24), fill=MUTED)
    return im


def pass_png(ev: dict, b: dict) -> bytes:
    buf = io.BytesIO()
    pass_image(ev, b).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def pass_pdf(ev: dict, b: dict) -> bytes:
    buf = io.BytesIO()
    pass_image(ev, b).save(buf, "PDF", resolution=170)
    return buf.getvalue()


# ----------------------------------------------------------------------------- calendar
def ics_text(ev: dict, b: dict | None = None) -> str:
    def z(dt):
        return dt.replace(tzinfo=E.IST).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def esc(s):
        return str(s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    desc = (ev.get("description") or "")[:500] + (f"\nBooking ID: {b['ref']}" if b else "")
    uid = f"{ev['code']}-{(b or {}).get('ref', 'event')}@qrforge"
    return "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//QR Sugi//Events//EN", "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{z(E.now_ist())}",
                        f"DTSTART:{z(E.event_start(ev))}", f"DTEND:{z(E.event_end(ev))}", f"SUMMARY:{esc(ev['name'])}", f"LOCATION:{esc(ev['venue'])}",
                        f"DESCRIPTION:{esc(desc)}", "END:VEVENT", "END:VCALENDAR", ""])


# ----------------------------------------------------------------------------- on-screen card (HTML renders any language)
def card_html(ev: dict, b: dict) -> str:
    e = html.escape
    qr64 = base64.b64encode(qr_png_bytes(pass_url(b["token"]), 360)).decode()
    status = b["status"]
    if b["checked_in_at"] and status == "confirmed":
        badge, col = _("Checked in {when}", when=E.fmt_utc(b["checked_in_at"], "%d %b, %I:%M %p")), "#B45309"
    else:
        badge, col = {"confirmed": (_("Valid"), "#059669"), "pending_payment": (_("Payment under review"), "#B45309"),
                      "cancelled": (_("Cancelled"), "#DC2626"), "rejected": (_("Payment not accepted"), "#DC2626")}.get(status, (status, "#475569"))
    dim = "" if status == "confirmed" and not b["checked_in_at"] else "opacity:.45;"
    return (f"<div class='pass-print' data-ref='{e(b['ref'])}' style='max-width:430px;margin:0 auto;border:1px solid #E2E8F0;border-radius:22px;overflow:hidden;background:#fff;"
            f"box-shadow:0 12px 32px rgba(79,70,229,.14);font-family:Inter,Arial,sans-serif'>"
            f"<div style='background:linear-gradient(135deg,#4F46E5,#7C3AED);color:#fff;padding:20px 22px'>"
            f"<div style='font-size:12px;letter-spacing:.14em;opacity:.8;font-weight:700'>{_('EVENT PASS')}</div>"
            f"<div style='font-size:24px;font-weight:800;line-height:1.2;margin-top:4px'>{e(ev['name'])}</div></div>"
            f"<div style='padding:18px 22px'>"
            f"<div style='font-size:11px;color:#64748B;font-weight:700;letter-spacing:.08em'>{_('DATE & TIME')}</div><div style='font-weight:700;color:#0F172A'>{e(nice_date(ev))}</div>"
            f"<div style='font-size:11px;color:#64748B;font-weight:700;letter-spacing:.08em;margin-top:10px'>{_('VENUE')}</div><div style='font-weight:700;color:#0F172A'>{e(ev['venue'])}</div>"
            f"<div style='border-top:1px solid #E2E8F0;margin:14px 0'></div>"
            f"<div style='display:flex;justify-content:space-between;align-items:flex-end;gap:10px'>"
            f"<div><div style='font-size:11px;color:#64748B;font-weight:700;letter-spacing:.08em'>{_('ATTENDEE')}</div><div style='font-size:20px;font-weight:800;color:#0F172A'>{e(b['name'])}</div></div>"
            f"<div style='font-weight:700;color:#4F46E5'>{e(ticket_label_i18n(ev, b))}</div></div>"
            f"<div style='text-align:center;margin:16px 0 4px;{dim}'><img src='data:image/png;base64,{qr64}' style='width:240px;height:240px;border:1px solid #CBD5E1;border-radius:14px;padding:8px'/></div>"
            f"<div style='text-align:center;font-size:26px;font-weight:800;color:#0F172A;letter-spacing:.04em'>{e(b['ref'])}</div>"
            f"<div style='text-align:center;font-size:11px;color:#64748B;font-weight:700;letter-spacing:.1em'>{_('BOOKING ID')}</div>"
            f"<div style='text-align:center;margin-top:12px'><span style='background:{col}1A;color:{col};padding:5px 14px;border-radius:999px;font-weight:700;font-size:13px'>{e(badge)}</span></div>"
            f"</div></div>")
