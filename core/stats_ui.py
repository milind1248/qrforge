"""Sidebar 'Live on QR Sugi' panel: visitors, QR codes created, creators leaderboard. Self-contained card styling that never exceeds the sidebar width."""
import html

import streamlit as st

from core import stats
from core.i18n import _

_CSS = """
<style>
.lb { width:100%; box-sizing:border-box; overflow:hidden; font-family:inherit; }
.lb * { box-sizing:border-box; }
.lb-top { border-radius:16px; padding:12px; color:#fff; background:linear-gradient(150deg,#4F46E5 0%,#7C3AED 55%,#EC4899 100%); box-shadow:0 8px 20px rgba(79,70,229,.25); }
.lb-head { display:flex; align-items:center; gap:7px; font-size:12px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; opacity:.95; margin-bottom:10px; }
.lb-dot { width:8px; height:8px; border-radius:50%; background:#34D399; box-shadow:0 0 0 0 rgba(52,211,153,.7); animation:lbp 1.8s infinite; flex:none; }
@keyframes lbp { 70% { box-shadow:0 0 0 7px rgba(52,211,153,0); } 100% { box-shadow:0 0 0 0 rgba(52,211,153,0); } }
.lb-tiles { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; }
.lb-tile { background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.22); border-radius:11px; padding:8px 4px; text-align:center; min-width:0; }
.lb-tile b { display:block; font-size:17px; font-weight:800; line-height:1.1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.lb-tile span { display:block; font-size:9.5px; opacity:.9; margin-top:3px; line-height:1.15; }
.lb-card { margin-top:10px; border-radius:16px; padding:11px 10px 9px; background:#fff; border:1px solid #E2E8F0; box-shadow:0 4px 14px rgba(15,23,42,.06); }
.lb-title { font-size:13px; font-weight:800; color:#0F172A; display:flex; align-items:center; gap:6px; }
.lb-sub { font-size:10.5px; color:#64748B; margin:1px 0 8px; }
.lb-chart { display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:5px; align-items:end; height:104px; }
.lb-col { display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; min-width:0; }
.lb-val { font-size:10px; font-weight:800; color:#4F46E5; line-height:1; margin-bottom:3px; }
.lb-bar { width:100%; max-width:26px; border-radius:7px 7px 3px 3px; transform-origin:bottom; animation:lbg 1s ease-out both; min-height:4px; }
@keyframes lbg { from { transform:scaleY(0); } to { transform:scaleY(1); } }
.lb-days { display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:5px; margin-top:5px; }
.lb-day { text-align:center; font-size:9px; color:#64748B; line-height:1.2; min-width:0; overflow:hidden; }
.lb-day b { display:block; font-size:10px; color:#334155; }
.lb-day.today b, .lb-day.today { color:#7C3AED; font-weight:800; }
</style>
"""
_BARS = ["linear-gradient(180deg,#818CF8,#4F46E5)", "linear-gradient(180deg,#A78BFA,#7C3AED)", "linear-gradient(180deg,#F472B6,#DB2777)", "linear-gradient(180deg,#FBBF24,#F97316)",
         "linear-gradient(180deg,#34D399,#059669)", "linear-gradient(180deg,#38BDF8,#0284C7)", "linear-gradient(180deg,#FB7185,#E11D48)"]
_WD = {"en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "hi": ["सोम", "मंगल", "बुध", "गुरु", "शुक्र", "शनि", "रवि"],
       "mr": ["सोम", "मंगळ", "बुध", "गुरू", "शुक्र", "शनि", "रवि"]}


def _fmt(n: int) -> str:
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 10000 else f"{n:,}"


def panel():
    try:
        s = stats.snapshot()
    except Exception:  # noqa: BLE001 - never break the page for a stats card
        return
    from core.i18n import current
    wd = _WD[current()]
    top = max((d["n"] for d in s["days"]), default=0) or 1
    cols, labels = "", ""
    last = len(s["days"]) - 1
    for i, d in enumerate(s["days"]):
        h = 6 if d["n"] == 0 else max(10, round(70 * d["n"] / top))
        val = f"<div class='lb-val'>{_fmt(d['n'])}</div>" if d["n"] else "<div class='lb-val' style='color:#CBD5E1'>0</div>"
        glow = "box-shadow:0 0 0 2px rgba(124,58,237,.35);" if i == last else ""
        cols += f"<div class='lb-col'>{val}<div class='lb-bar' style='height:{h}px;background:{_BARS[i % 7]};animation-delay:{i * 0.08:.2f}s;{glow}'></div></div>"
        labels += f"<div class='lb-day{' today' if i == last else ''}'><b>{d['label']}</b>{html.escape(wd[d['wd']])}</div>"
    st.markdown(
        _CSS + f"<div class='lb'><div class='lb-top'><div class='lb-head'><span class='lb-dot'></span>{html.escape(_('Live on QR Sugi'))}</div>"
        f"<div class='lb-tiles'><div class='lb-tile'><b>{_fmt(s['visits'])}</b><span>{html.escape(_('Visitors'))}</span></div>"
        f"<div class='lb-tile'><b>{_fmt(s['today'])}</b><span>{html.escape(_('Today'))}</span></div>"
        f"<div class='lb-tile'><b>{_fmt(s['created'])}</b><span>{html.escape(_('QR codes created'))}</span></div></div></div>"
        f"<div class='lb-card'><div class='lb-title'>📈 {html.escape(_('QR codes per day'))}</div><div class='lb-sub'>{html.escape(_('Last 7 days'))}</div>"
        f"<div class='lb-chart'>{cols}</div><div class='lb-days'>{labels}</div></div></div>",
        unsafe_allow_html=True)
