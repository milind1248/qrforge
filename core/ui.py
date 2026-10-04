"""Shared look & feel plus small UI helpers."""
import re

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, .stApp { font-family: 'Inter', sans-serif; }
.stApp { background: radial-gradient(1200px 500px at 85% -10%, #E0E7FF 0%, rgba(248,250,252,0) 60%), #F8FAFC; }
.block-container { padding-top: 2rem; max-width: 1200px; }
h1, h2, h3 { letter-spacing: -0.02em; }
.hero { text-align:center; padding: 1.5rem 0 1rem; }
.hero h1 { font-size: 2.9rem; font-weight: 800; line-height: 1.1; margin: 0 0 .6rem;
  background: linear-gradient(90deg,#4F46E5,#7C3AED 55%,#EC4899); -webkit-background-clip: text;
  background-clip: text; color: transparent; }
.hero p { color:#475569; font-size:1.1rem; max-width: 680px; margin: 0 auto; }
.pill { display:inline-block; padding:.2rem .7rem; border-radius:999px; background:#EEF2FF; color:#4338CA;
  font-size:.78rem; font-weight:600; margin-bottom:.8rem; border:1px solid #C7D2FE; }
.card { background:#fff; border:1px solid #E2E8F0; border-radius:18px; padding:1.3rem 1.4rem;
  box-shadow: 0 1px 2px rgba(15,23,42,.04), 0 8px 24px rgba(79,70,229,.05); height:100%; }
.card h4 { margin:.2rem 0 .3rem; font-size:1.05rem; }
.card p { color:#64748B; font-size:.92rem; margin:0; }
.feat-ico { font-size:1.6rem; }
.plan { min-height: 480px; background:#fff; border:1px solid #E2E8F0; border-radius:20px; padding:1.5rem; height:100%;
  box-shadow: 0 8px 24px rgba(15,23,42,.05); }
.plan.hot { border:2px solid #4F46E5; box-shadow: 0 16px 40px rgba(79,70,229,.18); position:relative; }
.plan .badge { position:absolute; top:-12px; right:18px; background:linear-gradient(90deg,#4F46E5,#7C3AED);
  color:#fff; font-size:.72rem; font-weight:700; padding:.25rem .7rem; border-radius:999px; }
.plan h3 { margin:0; font-size:1.25rem; }
.plan .tag { color:#64748B; font-size:.88rem; margin-bottom:.8rem; }
.plan .price { font-size:clamp(1.55rem,2.1vw,2.3rem); font-weight:800; color:#0F172A; white-space:nowrap; }
.plan .price small { font-size:.9rem; font-weight:500; color:#64748B; }
.plan .strike { color:#94A3B8; text-decoration:line-through; font-size:.85rem; margin-left:.3rem; white-space:nowrap; }
.plan ul { padding-left:0; list-style:none; margin:1rem 0 0; }
.plan li { padding:.28rem 0 .28rem 1.5rem; position:relative; font-size:.92rem; color:#334155; }
.plan li:before { content:"✓"; position:absolute; left:0; color:#10B981; font-weight:800; }
.lock { color:#B45309; background:#FEF3C7; border:1px solid #FDE68A; border-radius:10px; padding:.45rem .75rem;
  font-size:.85rem; margin:.3rem 0 .6rem; }
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
  background: linear-gradient(90deg,#4F46E5,#7C3AED); border:0; color:#fff; font-weight:600; }
.stButton > button, .stDownloadButton > button { border-radius: 12px; }
div[data-testid="stMetric"] { background:#fff; border:1px solid #E2E8F0; border-radius:16px; padding:.9rem 1.1rem; }
.qrbox, [data-testid="stImage"] img { background:#fff; border:1px solid #E2E8F0; border-radius:20px; padding:1rem; text-align:center;
  box-shadow: 0 12px 32px rgba(79,70,229,.10); }
.footer { text-align:center; color:#94A3B8; font-size:.85rem; padding:2rem 0 .5rem; }
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, sub: str, pill: str | None = None):
    pill_html = f'<div class="pill">{pill}</div>' if pill else ""
    st.markdown(f'<div class="hero">{pill_html}<h1>{title}</h1><p>{sub}</p></div>', unsafe_allow_html=True)


def lock_note(text: str):
    st.markdown(f'<div class="lock">🔒 {text}</div>', unsafe_allow_html=True)


def footer():
    import base64

    from core.config import ROOT
    b64 = base64.b64encode((ROOT / "assets" / "sugi_logo.png").read_bytes()).decode()
    st.markdown(
        f'<div class="footer"><img src="data:image/png;base64,{b64}" width="84" style="display:block;margin:0 auto .4rem"/>'
        'QRForge · a Sugi product · Digital products made simple<br>Create, track and manage QR codes · Made in India</div>',
        unsafe_allow_html=True)


def parse_ua(ua: str) -> tuple[str, str, str]:
    """Return (device, os, browser) from a User-Agent string."""
    u = ua or ""
    device = "Tablet" if re.search(r"iPad|Tablet", u) else "Mobile" if re.search(r"Mobi|Android|iPhone", u) else "Desktop"
    os_ = next((n for p, n in (("Windows", "Windows"), ("Android", "Android"), ("iPhone|iPad|iOS", "iOS"),
                               ("Mac OS", "macOS"), ("Linux", "Linux")) if re.search(p, u)), "Other")
    br = next((n for p, n in (("Edg/", "Edge"), ("OPR/|Opera", "Opera"), ("Chrome/", "Chrome"), ("Firefox/", "Firefox"),
                              ("Safari/", "Safari")) if re.search(p, u)), "Other")
    return device, os_, br


_REDIRECT = st.components.v2.component(
    "qrforge_redirect",
    html="<div></div>",
    js="""export default function (c) {
  const d = c.data || {};
  if (!d.url) return;
  const go = () => { window.location.href = d.url; };
  if (d.delay > 0) { setTimeout(go, d.delay * 1000); } else { go(); }
}""",
)


def redirect(url: str, delay: float = 0):
    _REDIRECT(data={"url": url, "delay": delay}, key="redir")
