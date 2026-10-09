"""QR payload builders, rendering (PNG/JPG/SVG/PDF) and decoding."""
import io
from urllib.parse import quote

import numpy as np
import qrcode
import segno
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles import colormasks as cm
from qrcode.image.styles.moduledrawers import pil as md

# key: (label, icon, can be dynamic)
TYPES = {
    "url": ("Website URL", ":material/link:", True),
    "text": ("Plain text", ":material/notes:", True),
    "wifi": ("Wi-Fi", ":material/wifi:", False),
    "vcard": ("Contact card", ":material/contact_page:", True),
    "email": ("Email", ":material/mail:", True),
    "sms": ("SMS", ":material/sms:", True),
    "phone": ("Phone", ":material/call:", True),
    "whatsapp": ("WhatsApp", ":material/chat:", True),
    "upi": ("UPI payment", ":material/currency_rupee:", True),
    "location": ("Location", ":material/location_on:", True),
    "event": ("Calendar event", ":material/event:", False),
}

SHAPES = {"Square": md.SquareModuleDrawer, "Rounded": md.RoundedModuleDrawer, "Dots": md.CircleModuleDrawer,
          "Gapped": md.GappedSquareModuleDrawer, "Vertical bars": md.VerticalBarsDrawer,
          "Horizontal bars": md.HorizontalBarsDrawer}
EYES = {"Square": md.SquareModuleDrawer, "Rounded": md.RoundedModuleDrawer, "Dots": md.CircleModuleDrawer}
ECC = {"Low (7%)": ERROR_CORRECT_L, "Medium (15%)": ERROR_CORRECT_M, "Quartile (25%)": ERROR_CORRECT_Q,
       "High (30%)": ERROR_CORRECT_H}


def _esc(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:")


def build_payload(t: str, f: dict) -> str:
    def g(k):
        return str(f.get(k) or "").strip()

    if t == "url":
        u = g("url")
        return u if not u or "://" in u else "https://" + u
    if t == "text":
        return f.get("text", "")
    if t == "wifi":
        enc = {"WPA/WPA2": "WPA", "WEP": "WEP", "None": "nopass"}[f.get("enc", "WPA/WPA2")]
        return f"WIFI:T:{enc};S:{_esc(g('ssid'))};P:{_esc(g('password'))};H:{'true' if f.get('hidden') else 'false'};;"
    if t == "vcard":
        lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:{g('last')};{g('first')};;;", f"FN:{g('first')} {g('last')}".strip()]
        for tag, k in (("ORG", "org"), ("TITLE", "title"), ("TEL", "phone"), ("EMAIL", "email"), ("URL", "web"), ("ADR", "addr")):
            if g(k):
                lines.append(f"{tag}:{g(k)}" if tag != "ADR" else f"ADR:;;{g(k)};;;;")
        return "\n".join(lines + ["END:VCARD"])
    if t == "email":
        q = "&".join(p for p in (f"subject={quote(g('subject'))}" if g("subject") else "",
                                  f"body={quote(g('body'))}" if g("body") else "") if p)
        return f"mailto:{g('to')}" + (f"?{q}" if q else "")
    if t == "sms":
        return f"SMSTO:{g('phone')}:{g('message')}"
    if t == "phone":
        return f"tel:{g('phone')}"
    if t == "whatsapp":
        num = "".join(ch for ch in g("phone") if ch.isdigit())
        return f"https://wa.me/{num}" + (f"?text={quote(g('message'))}" if g("message") else "")
    if t == "upi":
        p = f"upi://pay?pa={g('vpa')}&pn={quote(g('name'))}&cu=INR"
        if g("amount"):
            p += f"&am={g('amount')}"
        if g("note"):
            p += f"&tn={quote(g('note'))}"
        return p
    if t == "location":
        return f"https://www.google.com/maps?q={g('lat')},{g('lon')}"
    if t == "event":
        def fmt(d, tm):
            return f"{d.strftime('%Y%m%d')}T{tm.strftime('%H%M%S')}"
        return ("BEGIN:VEVENT\nSUMMARY:%s\nLOCATION:%s\nDTSTART:%s\nDTEND:%s\nEND:VEVENT" %
                (g("title"), g("place"), fmt(f["start_d"], f["start_t"]), fmt(f["end_d"], f["end_t"])))
    return ""


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mask(style, fg, bg):
    if not style.get("fg2"):
        return cm.SolidFillColorMask(back_color=bg, front_color=fg)
    fg2, d = _rgb(style["fg2"]), style.get("gdir", "Vertical")
    if d == "Radial":
        return cm.RadialGradiantColorMask(back_color=bg, center_color=fg, edge_color=fg2)
    if d == "Diamond":
        return cm.SquareGradiantColorMask(back_color=bg, center_color=fg, edge_color=fg2)
    if d == "Horizontal":
        return cm.HorizontalGradiantColorMask(back_color=bg, left_color=fg, right_color=fg2)
    return cm.VerticalGradiantColorMask(back_color=bg, top_color=fg, bottom_color=fg2)


def render(data: str, style: dict, watermark: bool = False, box: int = 12) -> Image.Image:
    """style keys: fg, bg, fg2, gdir, shape, eye, ecc, logo (bytes or None)."""
    logo = Image.open(io.BytesIO(style["logo"])).convert("RGBA") if style.get("logo") else None
    ecc = ERROR_CORRECT_H if logo else ECC.get(style.get("ecc", "Medium (15%)"), ERROR_CORRECT_M)
    qr = qrcode.QRCode(error_correction=ecc, box_size=box, border=3)
    qr.add_data(data or " ")
    qr.make(fit=True)
    fg, bg = _rgb(style.get("fg", "#0F172A")), _rgb(style.get("bg", "#FFFFFF"))
    kw = dict(image_factory=StyledPilImage,
              module_drawer=SHAPES.get(style.get("shape", "Square"), md.SquareModuleDrawer)(),
              color_mask=_mask(style, fg, bg))
    try:
        img = qr.make_image(eye_drawer=EYES.get(style.get("eye", "Square"), md.SquareModuleDrawer)(), **kw)
    except TypeError:
        img = qr.make_image(**kw)
    img = img.get_image().convert("RGBA")
    if logo:
        w = int(img.width * 0.22)
        logo.thumbnail((w, w))
        pad = 8
        plate = Image.new("RGBA", (logo.width + pad * 2, logo.height + pad * 2), bg + (255,))
        plate.paste(logo, (pad, pad), logo)
        img.paste(plate, ((img.width - plate.width) // 2, (img.height - plate.height) // 2), plate)
    img = img.convert("RGB")
    if watermark:
        strip = max(34, img.width // 14)
        out = Image.new("RGB", (img.width, img.height + strip), bg)
        out.paste(img, (0, 0))
        d = ImageDraw.Draw(out)
        try:
            font = ImageFont.truetype("arial.ttf", max(14, strip // 2))
        except OSError:
            font = ImageFont.load_default()
        txt = "Made with QR Sugi - free plan"
        tw = d.textlength(txt, font=font)
        d.text(((out.width - tw) / 2, img.height + strip // 6), txt, fill=(100, 116, 139), font=font)
        img = out
    return img


def export(data: str, style: dict, fmt: str, watermark: bool) -> tuple[bytes, str]:
    fmt = fmt.upper()
    if fmt == "SVG":
        buf = io.BytesIO()
        segno.make(data or " ", error="h" if style.get("logo") else "m").save(
            buf, kind="svg", scale=10, border=3, dark=style.get("fg", "#0F172A"), light=style.get("bg", "#FFFFFF"))
        return buf.getvalue(), "image/svg+xml"
    img = render(data, style, watermark, box=20)
    buf = io.BytesIO()
    if fmt == "PDF":
        page = Image.new("RGB", (1240, 1754), "white")
        img.thumbnail((900, 900))
        page.paste(img, ((1240 - img.width) // 2, 300))
        page.save(buf, "PDF", resolution=150)
        return buf.getvalue(), "application/pdf"
    if fmt == "JPG":
        img.save(buf, "JPEG", quality=95)
        return buf.getvalue(), "image/jpeg"
    img.save(buf, "PNG")
    return buf.getvalue(), "image/png"


def decode(image_bytes: bytes) -> str | None:
    import cv2
    arr = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return None
    det = cv2.QRCodeDetector()
    text, _, _ = det.detectAndDecode(arr)
    if not text:
        big = cv2.resize(arr, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        text, _, _ = det.detectAndDecode(big)
    return text or None
