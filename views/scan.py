import streamlit as st

from core import qr_engine as qe
from core.ui import hero

hero("Scan a QR code", "Upload a picture or use your camera. Decoding happens on the server and nothing is stored.")

tab_up, tab_cam = st.tabs([":material/upload: Upload image", ":material/photo_camera: Camera"])
with tab_up:
    up = st.file_uploader("QR image", type=["png", "jpg", "jpeg", "webp"])
with tab_cam:
    cam = st.camera_input("Point at a QR code")

src = up or cam
if src:
    text = qe.decode(src.getvalue())
    if text:
        st.success("QR code decoded")
        st.code(text, language=None)
        if text.startswith(("http://", "https://")):
            st.link_button("Open link", text, icon=":material/open_in_new:")
            st.caption("Only open links from sources you trust.")
    else:
        st.error("No QR code found. Try a sharper, closer image with good lighting.")
