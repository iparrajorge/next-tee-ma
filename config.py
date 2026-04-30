import os
import streamlit as st
from st_supabase_connection import SupabaseConnection

# ── Constants ──────────────────────────────────────────────────────────────────
FAVICON_FILENAME    = "favicon.png"
HEADER_LOGO_FILENAME = "logo.png"
DEBUG_MODE = True  # Set to True to skip login during development

# ── Page config (must be first Streamlit call in app.py) ──────────────────────
def init_page():
    st.set_page_config(
        page_title="NextTee MA",
        layout="wide",
        page_icon=FAVICON_FILENAME if os.path.exists(FAVICON_FILENAME) else "⛳"
    )
    if os.path.exists(HEADER_LOGO_FILENAME):
        st.image(HEADER_LOGO_FILENAME, width=450)

# ── Connections (cached so they are only created once per session) ─────────────
@st.cache_resource
def get_supabase_connection():
    return st.connection(
        "supabase",
        type=SupabaseConnection,
        url=st.secrets["connections"]["supabase"]["url"].strip("/"),
        key=st.secrets["connections"]["supabase"]["key"]
    )
