import streamlit as st
import streamlit.components.v1 as components

# ── 1. Page config — must be the very first Streamlit call ────────────────────
from config import init_page, get_supabase_connection, get_gsheets_connection
init_page()

# ── 2. Connections ────────────────────────────────────────────────────────────
st_supabase = get_supabase_connection()
conn        = get_gsheets_connection()

# ── 3. Auth — calls st.stop() if the user is not logged in ───────────────────
from auth import run_auth
run_auth(st_supabase)

# ── 4. App header (only reached when authenticated) ───────────────────────────
st.subheader(
    "A Massachusetts Golf Course Recommender",
    help="""
**How NextTee Works:**

This app uses a user-weighted multi-objective optimization algorithm to rank public courses in Massachusetts.

* **Course History:** Have you played the course before? Show all or only new ones?
* **Course Size:** 18 or 9 holes?
* **Price:** Control cost or splash out.
* **Prestige:** Based on the BTP Ranking.
* **Proximity:** As the crow flies from your location.

*Note: Traffic to the Cape isn't factored into the mileage!*
    """
)

# ── 5. Sidebar — writes hole_choice, explore_choice, user_lat/lon,
#                p_w, r_w, d_w into st.session_state ─────────────────────────
from sidebar import render_sidebar
render_sidebar()

# ── 6. Data — load, filter, and score using the values now in session_state ───
from data import load_data, filter_data, calculate_scores

try:
    df, df_all = load_data(conn)
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

df_filtered = filter_data(df)
results     = calculate_scores(df_filtered)

# ── 7. Tab-persistence JS (unchanged from original) ───────────────────────────
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0

js = f"""
<script>
    var tabIndex = {st.session_state.active_tab};
    var tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
    if (tabs.length > tabIndex) {{ tabs[tabIndex].click(); }}
</script>
"""
components.html(js, height=0)

# ── 8. Tabs ───────────────────────────────────────────────────────────────────
from components import tab_table, tab_map, tab_ranking

tab1, tab2, tab3 = st.tabs(["📊 Ranked Table", "🗺️ Map View", "🏅 Personal Ranking"])

with tab1:
    tab_table.render(results, conn)

with tab2:
    tab_map.render(results)

with tab3:
    tab_ranking.render(df_all, conn)
