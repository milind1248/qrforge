"""QRForge - QR code generator SaaS (Streamlit). Run:  streamlit run app.py"""
import html

import streamlit as st

st.set_page_config(page_title="QRForge - QR Code Generator", page_icon=str(__import__("pathlib").Path(__file__).parent / "assets" / "favicon.png"), layout="wide", initial_sidebar_state="expanded")

from core import auth, db, landing, license, ui  # noqa: E402

license.require()  # no valid key = nothing runs, including scan links
from core.config import ROOT  # noqa: E402



@st.cache_resource
def _init_db_once():
    db.init_db()   # once per server process, not on every rerun


_init_db_once()
ui.inject_css()


if code := st.query_params.get("r"):
    landing.handle(code)

if any(k in st.query_params for k in ("event", "pass", "checkin", "cancel")):
    from core import event_public
    event_public.handle_routes()

user = auth.current_user()
st.logo(str(ROOT / "assets" / "sugi_logo.png"), icon_image=str(ROOT / "assets" / "sugi_logo.png"), size="large")

home = st.Page("views/home.py", title="QR Generator", icon=":material/qr_code_2:", default=True)
scan = st.Page("views/scan.py", title="Scan", icon=":material/qr_code_scanner:")
pricing = st.Page("views/pricing.py", title="Pricing", icon=":material/workspace_premium:")
login = st.Page("views/login.py", title="Log in / Sign up", icon=":material/login:")

dash = st.Page("views/dashboard.py", title="My QR codes", icon=":material/dashboard:")
if user:
    pages = {
        "": [home, scan, pricing],
        "My account": [
            dash,
            st.Page("views/analytics.py", title="Analytics", icon=":material/insights:"),
            st.Page("views/bulk.py", title="Bulk", icon=":material/stacks:"),
            st.Page("views/events.py", title="Events", icon=":material/confirmation_number:"),
            st.Page("views/billing.py", title="Billing", icon=":material/receipt_long:"),
            st.Page("views/account.py", title="Account", icon=":material/person:"),
        ],
    }
    if user["role"] == "admin":
        pages["My account"].append(st.Page("views/admin.py", title="Admin", icon=":material/admin_panel_settings:"))
else:
    pages = [home, scan, pricing, login]

if user:
    from core.plans import get_plan
    plan = get_plan(user["plan"])
    badge = {"free": "🆓", "starter": "⭐", "pro": "💎", "business": "👑"}.get(plan.key, "💎")
    with st.sidebar:
        st.markdown(
            f"<div style='font-size:15px;line-height:1.5'>{badge} <b style='color:#2563EB'>Welcome</b>, "
            f"<b style='color:#16A34A'>{html.escape(user['name'])}</b> — <span style='color:#64748B'>{plan.name}</span></div>",
            unsafe_allow_html=True)
        if user["plan_expires"] and plan.key != "free":
            st.caption(f"Renews / expires {user['plan_expires'][:10]}")
        elif plan.key != "business":
            st.page_link(pricing, label="Upgrade plan", icon=":material/workspace_premium:")
        if st.button("Sign out", key="sidebar_logout", icon=":material/logout:", width="stretch"):
            auth.logout()
            st.rerun()

else:
    with st.sidebar:
        st.markdown("<div style='font-size:15px;line-height:1.5'>👋 <b style='color:#2563EB'>Welcome</b> to QRForge</div>",
                    unsafe_allow_html=True)
        st.caption("Log in to save QR codes, go dynamic and track scans.")
        st.page_link(login, label="Log in / Sign up", icon=":material/login:")

nav = st.navigation(pages, position="top")
if user and st.session_state.pop("goto_dash", False):
    st.switch_page(dash)
nav.run()
