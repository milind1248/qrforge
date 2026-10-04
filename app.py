"""QRForge - QR code generator SaaS (Streamlit). Run:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="QRForge - QR Code Generator", page_icon=":material/qr_code_2:", layout="wide")

from core import auth, db, landing, ui  # noqa: E402
from core.config import ROOT  # noqa: E402



@st.cache_resource
def _init_db_once():
    db.init_db()   # once per server process, not on every rerun


_init_db_once()
ui.inject_css()


if code := st.query_params.get("r"):
    landing.handle(code)

user = auth.current_user()
st.logo(str(ROOT / "assets" / "logo.svg"), size="large")

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
            st.Page("views/billing.py", title="Billing", icon=":material/receipt_long:"),
            st.Page("views/account.py", title="Account", icon=":material/person:"),
        ],
    }
    if user["role"] == "admin":
        pages["My account"].append(st.Page("views/admin.py", title="Admin", icon=":material/admin_panel_settings:"))
else:
    pages = [home, scan, pricing, login]

nav = st.navigation(pages, position="top")
if user and st.session_state.pop("goto_dash", False):
    st.switch_page(dash)
nav.run()
