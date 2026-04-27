import pandas as pd
import pydeck as pdk
import streamlit as st


def render(results):
    """Render the 🗺️ Map View tab."""
    st.session_state.active_tab = 1

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
