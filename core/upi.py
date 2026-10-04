"""Manual UPI payment helpers: payment-QR storage, server-side blur, and screenshot sanitising."""
import base64
import io

from PIL import Image, ImageFilter

from core import db

QR_KEY = "payment_qr"


def save_payment_qr(raw: bytes) -> None:
    """Validate and store the owner's UPI QR image (re-encoded as PNG, max 900 px)."""
    img = Image.open(io.BytesIO(raw))
    img.verify()
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((900, 900))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    db.set_setting(QR_KEY, base64.b64encode(buf.getvalue()).decode(), "image/png")


def get_payment_qr() -> bytes | None:
    row = db.get_setting(QR_KEY)
    return base64.b64decode(row["value"]) if row and row["value"] else None


def blurred(raw: bytes) -> bytes:
    """Blur on the server, so the readable QR is never sent to the browser until the user reveals it."""
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((300, 300))
    img = img.filter(ImageFilter.GaussianBlur(14))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70)
    return buf.getvalue()


def prepare_screenshot(raw: bytes) -> tuple[str, str]:
    """Verify it is a real image, strip metadata, downscale, re-encode as JPEG. Returns (base64, mime)."""
    img = Image.open(io.BytesIO(raw))
    img.verify()
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"
