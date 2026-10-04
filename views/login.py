from core import license as _license

_license.require()
import streamlit as st

from core import auth
from core.ui import hero

hero("Welcome to QRForge", "Log in or create a free account to save QR codes, go dynamic and track scans.")

_, mid, _ = st.columns([1, 1.6, 1])
with mid:
    tab_in, tab_up = st.tabs(["Log in", "Create account"])
    with tab_in:
        with st.form("login"):
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary", width="stretch"):
                err = auth.login(email, pw)
                if err:
                    st.error(err)
                else:
                    st.session_state["goto_dash"] = True
                    st.rerun()
    with tab_up:
        with st.form("signup"):
            name = st.text_input("Full name")
            email2 = st.text_input("Email ", key="su_email")
            pw2 = st.text_input("Password (min 8 characters)", type="password", key="su_pw")
            if st.form_submit_button("Create free account", type="primary", width="stretch"):
                err = auth.signup(email2, name, pw2)
                if err:
                    st.error(err)
                else:
                    st.session_state["goto_dash"] = True
                    st.rerun()
        st.caption("By signing up you agree to our Terms and Privacy Policy.")
