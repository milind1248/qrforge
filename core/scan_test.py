"""Scannability stress-test: renders the QR then tries to decode it after real-world damage."""
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from core import qr_engine as qe


def _decode(img: Image.Image) -> str | None:
    import io
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return qe.decode(buf.getvalue())


def _jpeg(img, q):
    import io
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=q)
    return Image.open(io.BytesIO(b.getvalue()))


def _noise(img, sigma):
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    a += np.random.default_rng(7).normal(0, sigma, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _fade(img, f):
    return Image.blend(img.convert("RGB"), Image.new("RGB", img.size, (170, 170, 170)), f)


def _small(img, px):
    return img.resize((px, px), Image.BILINEAR)


def run(data: str, style: dict) -> list[dict]:
    """Returns [{name, passed, note}] for each simulated condition."""
    base = qe.render(data, style, watermark=False, box=10).convert("RGB")
    w = base.width
    tests = [
        ("Perfect conditions", lambda i: i, "Baseline"),
        ("Small placement (about 1/5 size)", lambda i: _small(i, max(60, w // 5)), "Tiny placements fail first"),
        ("Very small placement (about 1/9 size)", lambda i: _small(i, max(34, w // 9)), "Stamp-size prints"),
        ("Out of focus (light blur)", lambda i: i.filter(ImageFilter.GaussianBlur(2.5)), "Shaky camera"),
        ("Out of focus (heavy blur)", lambda i: i.filter(ImageFilter.GaussianBlur(9)), "Far away or dirty lens"),
        ("Dim light / faded print", lambda i: _fade(ImageEnhance.Brightness(i).enhance(0.55), 0.7), "Sun-faded poster"),
        ("Camera noise", lambda i: _noise(i, 75), "Low-light phone camera"),
        ("Tilted 20 degrees", lambda i: i.rotate(20, expand=True, fillcolor=(255, 255, 255)), "Scanning at an angle"),
        ("Low-quality JPEG (WhatsApp forward)", lambda i: _jpeg(_small(i, max(120, w // 2)), 25), "Compressed sharing"),
        ("Inverted colours", lambda i: Image.eval(i, lambda v: 255 - v), "Some readers cannot read light-on-dark"),
    ]
    out = []
    for name, fn, note in tests:
        info = name.startswith("Inverted")
        try:
            ok = _decode(fn(base)) == data
        except Exception:  # noqa: BLE001
            ok = False
        out.append({"name": name, "passed": ok, "note": note, "info": info})
    return out


def print_advice(distance_cm: float, data_len: int) -> dict:
    """Rule of thumb: minimum QR width = scan distance / 10, never below 2 cm; dense codes need more."""
    base = max(2.0, distance_cm / 10)
    density = 1.0 + max(0, data_len - 60) / 400  # long payloads => denser modules => larger print
    return {"min_cm": round(base * density, 1), "ideal_cm": round(base * density * 1.5, 1)}
