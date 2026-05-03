import pandas as pd
import pydeck as pdk
import streamlit as st


def render(results, st_supabase):
    """Render the 🗺️ Map View tab."""

    # ── First-visit hint ───────────────────────────────────────────────────────
    if not st.session_state.get("seen_map_hint", False):
        user_id = st.session_state.user_id
        result = st_supabase.table("user_flags") \
            .select("seen_map_hint") \
            .eq("user_id", user_id) \
            .execute()

        seen = result.data[0]["seen_map_hint"] if result.data else False
        st.session_state.seen_map_hint = seen

        if not seen:
            st.info(
                "🗺️ **Map View** — Green dots are your top 5 courses, grey dots are the rest. "
                "The red dot is your location. Hover over any dot for details."
            )
            if st.button("Got it ✓", key="dismiss_map_hint"):
                st_supabase.table("user_flags").upsert({
                    "user_id": user_id,
                    "seen_map_hint": True,
                }, on_conflict="user_id").execute()
                st.session_state.seen_map_hint = True
                st.rerun()


    if results.empty:
        st.warning("No courses match those filters.")
        return

    user_lat = st.session_state.user_lat
    user_lon = st.session_state.user_lon

    map_df = results.copy().rename(columns={"Location X": "lat", "Location Y": "lon"})

    st.pydeck_chart(pdk.Deck(
        map_style="light",
        initial_view_state=pdk.ViewState(
            latitude=user_lat, longitude=user_lon, zoom=8
        ),
        layers=[
            # Top-5 courses — green, larger dot
            pdk.Layer(
                "ScatterplotLayer", map_df.head(5),
                get_position=["lon", "lat"],
                get_fill_color=[34, 139, 34, 255],
                get_radius=1500,
                pickable=True,
            ),
            # Remaining courses — dark grey, smaller dot
            pdk.Layer(
                "ScatterplotLayer", map_df.iloc[5:],
                get_position=["lon", "lat"],
                get_fill_color=[40, 40, 40, 200],
                get_radius=900,
                pickable=True,
            ),
            # User location — red
            pdk.Layer(
                "ScatterplotLayer",
                pd.DataFrame([{"lat": user_lat, "lon": user_lon}]),
                get_position=["lon", "lat"],
                get_fill_color=[200, 30, 30, 255],
                get_radius=1500,
            ),
        ],
        tooltip={"text": "{Name}\nRank: {BTP Ranking}\nPrice: ${Price}"},
    ))
