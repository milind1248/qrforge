"""License-key gate. The app, every page, the scan links and the database layer refuse to run unless
LICENSE_KEY (Streamlit secret or environment variable) matches the fingerprint below.
Only a salted hash is stored here, never the key itself."""
import hashlib
import hmac

from core.config import LICENSE_KEY

_FINGERPRINT = "d8ef94b41c4c6236f8c4547a5ce1d738bb9187b4dd7314d5a641cd57747b7eb6"


def is_valid() -> bool:
    got = hashlib.sha256(("qrforge|" + (LICENSE_KEY or "").strip()).encode()).hexdigest()
    return hmac.compare_digest(got, _FINGERPRINT)


def require():
    """Call at the top of every page. Shows a locked screen and stops the script if the key is missing/wrong."""
    if is_valid():
        return
    import streamlit as st
    st.markdown(
        "<div style='max-width:560px;margin:12vh auto;text-align:center;font-family:sans-serif'>"
        "<div style='font-size:3rem'>🔒</div><h2>License required</h2>"
        "<p style='color:#64748B'>This application is not licensed for this deployment. "
        "Please contact the owner to obtain a valid license key.</p></div>", unsafe_allow_html=True)
    st.stop()
