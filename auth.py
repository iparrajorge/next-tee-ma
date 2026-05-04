import streamlit as st
from config import DEBUG_MODE

def _log_event(st_supabase, event: str, user_id: str):
    try:
        st_supabase.table("user_log").insert({
            "event":   event,
            "user_id": user_id,
        }).execute()
    except Exception:
        pass  # never let logging break the app

def init_session():
    """Initialise auth-related session state keys on first run."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_id = None


def restore_session(st_supabase):
    """Try to pick up an existing Supabase session (e.g. after a page refresh)."""
    if not st.session_state.authenticated:
        existing = st_supabase.auth.get_session()
        if existing:
            st.session_state.authenticated = True
            st.session_state.user_id = existing.user.id


def apply_debug_mode():
    """Bypass login entirely when DEBUG_MODE is on."""
    if DEBUG_MODE:
        st.session_state.authenticated = True
        st.session_state.user_id = "00000000-0000-0000-0000-000000000000"


def show_auth_ui(st_supabase):
    """
    Render the login / sign-up screen.
    Calls st.stop() so nothing below it renders until the user is authenticated.
    """
    st.markdown("## Find Your Perfect Round of Public Golf in MA")
    st.markdown("""
    **NextTee MA** uses a custom ranking algorithm to find the best public golf courses
    based on your specific priorities. Join our community to:
    * **Personalized Rankings:** Weight Price, Quality, and Distance to fit your mood.
    * **Track Your Progress:** Save which of the 100+ MA courses you've played.
    """)
    st.info("Registration is free. We only use your email to save your personal course history.")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        email    = st.text_input("Email",    key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Log In"):
            try:
                response = st_supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                if response:
                    st.session_state.authenticated = True
                    st.session_state.user_id = response.user.id
                    _log_event(st_supabase, "login", response.user.id)  # ← add this
                    st.rerun()
            except Exception:
                st.error("Invalid login credentials.")

    with tab2:
        new_email    = st.text_input("Email",    key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_pw")
        if st.button("Create Account"):
            try:
                response = st_supabase.auth.sign_up(
                    {"email": new_email, "password": new_password}
                )
                if response.session:
                    st.session_state.authenticated = True
                    st.session_state.user_id = response.user.id
                    _log_event(st_supabase, "signup", response.user.id)  # ← add this
                    st.success("Welcome aboard!")
                    st.rerun()
                else:
                    st.success("Account created! Please log in.")
            except Exception:
                st.error("Account could not be created. (Check if email is already in use)")

    st.stop()

def show_logout_button(st_supabase):
    """Render a logout button in the sidebar."""
    st.sidebar.markdown("---")
    if st.sidebar.button("Log Out"):
        st_supabase.auth.sign_out()
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.personal_ranking = []
        st.rerun()
    st.sidebar.markdown("Questions? [nextteema@proton.me](mailto:nextteema@proton.me)")

def run_auth(st_supabase):
    """
    Top-level auth orchestrator — call this near the top of app.py,
    before any app content is rendered.

    Order matters:
      1. Ensure session keys exist.
      2. Try to restore an existing Supabase session.
      3. Honour DEBUG_MODE bypass.
      4. Show auth UI (and halt) if still not authenticated.
    """
    init_session()
    restore_session(st_supabase)
    apply_debug_mode()

    if not st.session_state.authenticated:
        show_auth_ui(st_supabase)
