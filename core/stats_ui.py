"""Sidebar 'Live on QRForge' panel: visitors, QR codes created, creators leaderboard. Self-contained card styling that never exceeds the sidebar width."""
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
.lb-card { margin-top:10px; border-radius:16px; padding:11px 11px 9px; background:#fff; border:1px solid #E2E8F0; box-shadow:0 4px 14px rgba(15,23,42,.06); }
.lb-title { font-size:13px; font-weight:800; color:#0F172A; margin-bottom:8px; display:flex; align-items:center; gap:6px; }
.lb-row { display:flex; align-items:center; gap:7px; margin-bottom:7px; min-width:0; }
.lb-medal { width:20px; text-align:center; font-size:15px; flex:none; }
.lb-mid { flex:1; min-width:0; }
.lb-name { font-size:12.5px; font-weight:700; color:#1E293B; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.lb-bar { height:6px; border-radius:99px; background:#EEF2FF; margin-top:3px; overflow:hidden; }
.lb-fill { height:100%; border-radius:99px; transform-origin:left; animation:lbg 1.1s ease-out both; }
@keyframes lbg { from { transform:scaleX(0); } to { transform:scaleX(1); } }
.lb-n { font-size:12px; font-weight:800; color:#4F46E5; flex:none; min-width:22px; text-align:right; }
.lb-empty { font-size:12px; color:#64748B; padding:4px 0 6px; }
</style>
"""
_BARS = ["linear-gradient(90deg,#F59E0B,#FB923C)", "linear-gradient(90deg,#94A3B8,#CBD5E1)", "linear-gradient(90deg,#D97706,#F59E0B)",
         "linear-gradient(90deg,#6366F1,#8B5CF6)", "linear-gradient(90deg,#06B6D4,#3B82F6)"]
_MEDALS = ["🥇", "🥈", "🥉", "4", "5"]


def _fmt(n: int) -> str:
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 10000 else f"{n:,}"


def panel():
    try:
        s = stats.snapshot()
    except Exception:  # noqa: BLE001 - never break the page for a stats card
        return
    rows = ""
    top = max((b["n"] for b in s["board"]), default=0) or 1
    for i, b in enumerate(s["board"]):
        w = max(8, round(100 * b["n"] / top))
        rows += (f"<div class='lb-row'><div class='lb-medal'>{_MEDALS[i]}</div><div class='lb-mid'><div class='lb-name'>{html.escape(b['name'])}</div>"
                 f"<div class='lb-bar'><div class='lb-fill' style='width:{w}%;background:{_BARS[i]};animation-delay:{i * 0.12:.2f}s'></div></div></div>"
                 f"<div class='lb-n'>{_fmt(b['n'])}</div></div>")
    if not rows:
        rows = f"<div class='lb-empty'>{html.escape(_('Be the first to save a QR code!'))}</div>"
    st.markdown(
        _CSS + f"<div class='lb'><div class='lb-top'><div class='lb-head'><span class='lb-dot'></span>{html.escape(_('Live on QRForge'))}</div>"
        f"<div class='lb-tiles'><div class='lb-tile'><b>{_fmt(s['visits'])}</b><span>{html.escape(_('Visitors'))}</span></div>"
        f"<div class='lb-tile'><b>{_fmt(s['today'])}</b><span>{html.escape(_('Today'))}</span></div>"
        f"<div class='lb-tile'><b>{_fmt(s['created'])}</b><span>{html.escape(_('QR codes created'))}</span></div></div></div>"
        f"<div class='lb-card'><div class='lb-title'>🏆 {html.escape(_('Top creators'))}</div>{rows}</div></div>",
        unsafe_allow_html=True)
