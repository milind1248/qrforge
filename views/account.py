from core import license as _license

_license.require()
import streamlit as st

from core import auth, db

user = auth.current_user()
st.title("Account")

with st.form("profile"):
    name = st.text_input("Full name", user["name"])
    st.text_input("Email", user["email"], disabled=True)
    pw = st.text_input("New password (leave blank to keep current)", type="password")
    if st.form_submit_button("Save changes", type="primary"):
        if pw and len(pw) < 8:
            st.error("Password must be at least 8 characters.")
        else:
            db.update_profile(user["id"], name.strip() or user["name"], auth.hash_pw(pw) if pw else None)
            st.success("Profile updated.")

st.divider()
if st.button("Log out", icon=":material/logout:"):
    auth.logout()
    st.switch_page("views/home.py")
