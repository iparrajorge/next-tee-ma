import streamlit as st
from geopy.geocoders import Nominatim


# ── Geocoding ──────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_coordinates(address_string):
    geolocator = Nominatim(user_agent="nexttee_ma_golf_app_v2")
    try:
        location = geolocator.geocode(address_string + ", Massachusetts", timeout=10)
        if location:
            return location.latitude, location.longitude, location.address
    except Exception:
        pass
    return None, None, None


def render_sidebar(st_supabase):
    """
    Draw all sidebar widgets and write the user's choices into st.session_state
    so that data.py and the tab components can read them without needing
    return values threaded through every call.

    Keys written to st.session_state:
        hole_choice   – int  (9 or 18)
        explore_choice – str ("All" or "New")
        user_lat      – float
        user_lon      – float
        p_w           – float  price weight   (sums to 1.0 with r_w + d_w)
        r_w           – float  rank weight
        d_w           – float  distance weight
    """
    st.sidebar.header("User Preferences")

    # ── First-visit sidebar hint ───────────────────────────────────────────
    if not st.session_state.get("seen_sidebar_hint", False):
        user_id = st.session_state.user_id
        result = st_supabase.table("user_flags") \
            .select("seen_sidebar_hint") \
            .eq("user_id", user_id) \
            .execute()

        seen = result.data[0]["seen_sidebar_hint"] if result.data else False
        st.session_state.seen_sidebar_hint = seen

        if not seen:
            st.sidebar.info(
                "👋 **Start here!** Set your location and adjust the sliders "
                "to match what matters most to you. Your results update instantly."
            )
            if st.sidebar.button("Got it ✓"):
                st_supabase.table("user_flags").upsert({
                    "user_id": user_id,
                    "seen_sidebar_hint": True,
                }, on_conflict="user_id").execute()
                st.session_state.seen_sidebar_hint = True
                st.rerun()

    # ── Course filters ─────────────────────────────────────────────────────────
    hole_choice = st.sidebar.radio(
        "Course Size", [18, 9], index=0, format_func=lambda x: f"{x} Holes"
    )
    explore_choice = st.sidebar.radio(
        "Course History", ["All", "New"], index=0,
        help="'New' only shows courses you haven't played yet."
    )

    # ── Location ───────────────────────────────────────────────────────────────
    st.sidebar.subheader("Your Location")
    address_input = st.sidebar.text_input(
        "Enter City, Zip, or Address", value="Boston City Hall"
    )

    user_lat, user_lon = 42.3601, -71.0589   # Boston default
    if address_input:
        lat, lon, full_name = get_coordinates(address_input)
        if lat:
            user_lat, user_lon = lat, lon
            st.sidebar.success(f"📍 {full_name.split(',')[0]}")
        else:
            st.sidebar.warning("📍 Location not found — defaulting to Boston.")

    # ── Priority sliders ───────────────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("Priority Balance")
    st.sidebar.write("Adjust how much you care about each factor:")

    imp_price = st.sidebar.slider("Price Sensitivity",  0, 10, 5)
    imp_rank  = st.sidebar.slider("Course Prestige",    0, 10, 5)
    imp_dist  = st.sidebar.slider("Proximity/Distance", 0, 10, 5)

    total_imp = imp_price + imp_rank + imp_dist
    if total_imp == 0:
        p_w, r_w, d_w = 0.33, 0.33, 0.33
    else:
        p_w = imp_price / total_imp
        r_w = imp_rank  / total_imp
        d_w = imp_dist  / total_imp

    st.sidebar.markdown(f"""
**Current Weighting:**
* 💰 Price: {p_w:.0%}
* 🏆 Rank:  {r_w:.0%}
* 🚗 Dist:  {d_w:.0%}
""")

    # ── Persist everything in session_state ───────────────────────────────────
    # Using st.session_state as the single source of truth means data.py
    # and all tab components always read the same, freshly-computed values.
    st.session_state.hole_choice    = hole_choice
    st.session_state.explore_choice = explore_choice
    st.session_state.user_lat       = user_lat
    st.session_state.user_lon       = user_lon
    st.session_state.p_w            = p_w
    st.session_state.r_w            = r_w
    st.session_state.d_w            = d_w
