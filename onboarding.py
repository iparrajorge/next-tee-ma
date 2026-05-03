import streamlit as st


def _mark_complete(st_supabase):
    """Write onboarding_complete = true for the current user."""
    user_id = st.session_state.user_id
    st_supabase.table("user_flags").upsert({
        "user_id": user_id,
        "onboarding_complete": True,
    }, on_conflict="user_id").execute()


def check_onboarding(st_supabase):
    """
    Returns True if onboarding should be shown, False if the user
    has already completed it (or DEBUG_MODE is on).
    """
    from config import DEBUG_MODE
    if DEBUG_MODE:
        return False

    user_id = st.session_state.user_id
    result = st_supabase.table("user_flags") \
        .select("onboarding_complete") \
        .eq("user_id", user_id) \
        .execute()

    # No row yet = brand new user
    if not result.data:
        return True

    return not result.data[0]["onboarding_complete"]


def render_onboarding(st_supabase):
    """Render the welcome screen and block the app until dismissed."""
    st.markdown("## Welcome to NextTee MA ⛳")
    st.markdown("""
    **NextTee** helps you find the best public golf course in Massachusetts
    for your next round — based on what *you* care about.

    Here's how it works:

    - 🎚️ **Set your priorities** in the sidebar — price, prestige, and distance
    - 📍 **Enter your location** so we can factor in the drive
    - 📊 **Browse your personalised rankings** in the table or on the map
    - ✅ **Track which courses you've played** and build your personal ranking
    """)

    st.info("💡 You'll get a short hint on each section as you go — they're easy to dismiss.")

    if st.button("Get Started →", type="primary"):
        _mark_complete(st_supabase)
        st.rerun()

    st.stop()