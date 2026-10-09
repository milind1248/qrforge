"""'Contact us' link in the sidebar: opens a dialog with a form; the message is emailed to the site owner (Reply-To = the visitor)."""
import re
import time

import streamlit as st

from core import notify
from core.i18n import _

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PER_SESSION = (3, 600)        # at most 3 messages per 10 minutes per browser session
GLOBAL = (30, 3600)           # and 30 per hour for the whole site, so the form cannot be used to flood the inbox


@st.cache_resource
def _global_times() -> list:
    return []


def _allowed() -> bool:
    now = time.time()
    mine = [t for t in st.session_state.get("_contact_times", []) if now - t < PER_SESSION[1]]
    g = _global_times()
    g[:] = [t for t in g if now - t < GLOBAL[1]]
    st.session_state["_contact_times"] = mine
    return len(mine) < PER_SESSION[0] and len(g) < GLOBAL[0]


def _clean_line(s: str, n: int) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", " ", s or "").strip()[:n]


def _contact_body():
    if st.session_state.pop("_contact_sent", False):
        st.success(_("Thank you! Your message was sent. We will reply to your email."), icon=":material/check_circle:")
        return
    st.caption(_("Questions, feedback or a problem? Write to us and we will reply by email."))
    with st.form("contact_form", clear_on_submit=False):
        name = st.text_input(_("Your name (optional)"), max_chars=60)
        email = st.text_input(_("Your email"), max_chars=120, placeholder="name@example.com")
        subject = st.text_input(_("Your query"), max_chars=100, placeholder=_("e.g. Help with a dynamic QR code"))
        message = st.text_area(_("Description"), max_chars=2000, height=140)
        go = st.form_submit_button(_("Send message"), type="primary", width="stretch")
    if not go:
        return
    name, subject, email, message = _clean_line(name, 60), _clean_line(subject, 100), _clean_line(email, 120), (message or "").strip()[:2000]
    if not subject:
        st.error(_("Enter your query."))
    elif not EMAIL_RE.match(email):
        st.error(_("Enter a valid email address."))
    elif len(message) < 10:
        st.error(_("Please describe your question in a few words (at least 10 characters)."))
    elif not _allowed():
        st.error(_("You have sent several messages recently. Please try again later."))
    else:
        with st.spinner(_("Sending...")):
            ok = notify.send_contact_message(name, email, subject, message)
        if ok:
            st.session_state.setdefault("_contact_times", []).append(time.time())
            _global_times().append(time.time())
            st.session_state["_contact_sent"] = True
            st.rerun(scope="fragment")
        else:
            st.error(_("Sorry, the message could not be sent right now. Please try again later."))


def sidebar_link():
    """Pinned to the bottom of the sidebar."""
    with st.container(key="contact_box"):
        if st.button(_("Contact us"), key="contact_open", icon=":material/mail:", width="stretch"):
            st.dialog(_("Contact us"))(_contact_body)()
