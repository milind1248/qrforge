"""Tiny translation layer: English text is the key, so code stays readable and a missing translation simply shows English.
    from core.i18n import _          ->  _("Sign out")   or   _("Hello {name}", name=x)
The language lives in st.session_state["lang"] ("en" / "hi" / "mr") and can be preset with ?lang=hi in the URL."""
import streamlit as st

LANGS = {"en": "English", "hi": "हिन्दी", "mr": "मराठी"}


def current() -> str:
    lang = st.session_state.get("lang") or "en"
    return lang if lang in LANGS else "en"


def _(text: str, **kw) -> str:
    from core.translations import HI, MR
    lang = current()
    out = text if lang == "en" else (HI if lang == "hi" else MR).get(text, text)
    return out.format(**kw) if kw else out


def init():
    """Call once per run, before any widget: picks the language from ?lang= on the first visit and keeps the second switcher (home page) in step."""
    if not st.session_state.get("lang"):
        q = st.query_params.get("lang", "en")
        st.session_state["lang"] = q if q in LANGS else "en"
    st.session_state["lang_home"] = st.session_state["lang"]


def _from_home():
    st.session_state["lang"] = st.session_state.get("lang_home") or "en"


def lang_switcher(label_visibility: str = "collapsed", home: bool = False):
    """home=True is a second copy of the switcher for the main page (the sidebar is hidden on phones); both stay in sync."""
    if home:
        st.segmented_control("Language", list(LANGS), format_func=LANGS.get, key="lang_home", label_visibility=label_visibility, on_change=_from_home)
    else:
        st.segmented_control("Language", list(LANGS), format_func=LANGS.get, key="lang", label_visibility=label_visibility, help="Language / भाषा / भाषा")
