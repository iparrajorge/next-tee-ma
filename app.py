import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import os
from geopy.geocoders import Nominatim

# Define the logo filename once so we can use it in multiple places
LOGO_FILENAME = "logo.png"

# ==========================================
# 1. PAGE SETUP & HEADER (NextTee Branding)
# ==========================================

# A. Set Browser/Tab Config
# We check if the logo exists; if so, it becomes your browser tab icon.
# If it doesn't exist yet, we use the golf emoji as a fallback.
st.set_page_config(
    page_title="NextTee MA", 
    layout="wide", 
    page_icon=LOGO_FILENAME if os.path.exists(LOGO_FILENAME) else "⛳"
)

# B. Handle Logo and Title Layout
header_col1, header_col2 = st.columns([1, 7])

with header_col1:
    # This displays the logo on the actual page next to your title
    if os.path.exists(LOGO_FILENAME):
        st.image(LOGO_FILENAME, width=100) 
    else:
        st.warning(f"Waiting for '{LOGO_FILENAME}' file.")

with header_col2:
    # The Branded Title
    st.markdown("# NextTee<sup>MA</sup>", unsafe_allow_html=True)
    
    # The Subtitle
    st.markdown("### A Massachusetts Golf Course Recommender")

st.markdown("---")

# 2. LOAD DATA
try:
    df_raw = pd.read_csv("MA_Courses_Basic.csv")
except FileNotFoundError:
    st.error("CSV file not found. Please ensure 'MA_Courses_Basic.csv' is in the folder.")
    st.stop()

# 3. SIDEBAR - USER INPUTS
st.sidebar.header("User Preferences")

# A. Course Size & History Filters
hole_choice = st.sidebar.radio("Course Size", [18, 9], index=0, format_func=lambda x: f"{x} Holes")
explore_choice = st.sidebar.radio("Course History", ["All", "Remove frequent", "New"], index=0)

# B. Location Inputs
@st.cache_data
def get_coordinates(address_string):
    """
    Caches the geocoding result so we don't spam the API 
    every time a slider is moved.
    """
    geolocator = Nominatim(user_agent="nexttee_ma_app")
    try:
        # Adding 'Massachusetts' ensures a local search
        location = geolocator.geocode(address_string + ", Massachusetts")
        if location:
            return location.latitude, location.longitude, location.address
    except:
        return None, None, None
    return None, None, None

st.sidebar.subheader("Your Location")
address_input = st.sidebar.text_input(
    "Enter City, Zip, or Address", 
    value="Boston City Hall"
)

# Set defaults
user_lat, user_lon = 42.3601, -71.0589 

if address_input:
    lat, lon, full_name = get_coordinates(address_input)
    if lat:
        user_lat, user_lon = lat, lon
        st.sidebar.success(f"📍 {full_name.split(',')[0]}")
    else:
        st.sidebar.error("Location not found. Using Boston City Hall.")

st.sidebar.markdown("---")
st.sidebar.subheader("Priority Balance")
st.sidebar.write("Adjust how much you care about each factor:")

imp_price = st.sidebar.slider("Price Sensitivity", 0, 10, 5)
imp_rank = st.sidebar.slider("Course Prestige", 0, 10, 5)
imp_dist = st.sidebar.slider("Proximity/Distance", 0, 10, 5)

# THE SMOOTH MATH: Normalization
total_imp = imp_price + imp_rank + imp_dist

if total_imp == 0:
    # Default to equal weighting if user zeros everything out
    p_w, r_w, d_w = 0.33, 0.33, 0.33
else:
    p_w = imp_price / total_imp
    r_w = imp_rank / total_imp
    d_w = imp_dist / total_imp

# Visual Feedback for the user
st.sidebar.markdown(f"""
**Current Weighting:**
* 💰 Price: {p_w:.0%}
* 🏆 Rank: {r_w:.0%}
* 🚗 Dist: {d_w:.0%}
""")

# 4. DATA FILTERING & CALCULATION
df = df_raw[df_raw['Holes'] == hole_choice].copy()

if explore_choice == "Remove frequent":
    df = df[df['Played already'] < 2]
elif explore_choice == "New":
    df = df[df['Played already'] == 0]

def calculate_scores(data):
    if data.empty:
        return data
        
    # A. Distance Calculation
    data['dist_miles'] = np.sqrt((69.1 * (data['Location X'] - user_lat))**2 + 
                                 (51.4 * (data['Location Y'] - user_lon))**2)
    
    # B. Normalize Price (Capped at $150)
    price_cap = 150
    min_price = data['Price'].min()
    data['price_score'] = data['Price'].apply(
        lambda x: 0 if x > price_cap else (price_cap - x) / (price_cap - min_price) if price_cap != min_price else 1
    )
    
    # C. Normalize Rank (Exponential Decay)
    k = 0.05
    raw_rank_score = np.exp(-k * (data['BTP Ranking'] - 1))
    data['rank_score'] = (raw_rank_score - raw_rank_score.min()) / (raw_rank_score.max() - raw_rank_score.min() + 1e-6)
    
    # D. Normalize Distance (Capped at 50 miles)
    dist_cap = 50
    min_dist = data['dist_miles'].min()
    data['dist_score'] = data['dist_miles'].apply(
        lambda x: 0 if x > dist_cap else (dist_cap - x) / (dist_cap - min_dist) if dist_cap != min_dist else 1
    )
    
    # FINAL WEIGHTED SCORE
    data['Final Score'] = (data['price_score'] * p_w) + \
                          (data['rank_score'] * r_w) + \
                          (data['dist_score'] * d_w)
    
    return data.sort_values(by='Final Score', ascending=False)

results = calculate_scores(df)

# 5. DISPLAY
tab1, tab2 = st.tabs(["🗺️ Map View", "📊 Ranked Table"])

with tab1:
    st.subheader(f"Top Recommended {hole_choice}-Hole Courses")
    if not results.empty:
        map_df = results.copy().rename(columns={'Location X': 'lat', 'Location Y': 'lon'}).reset_index(drop=True)
        map_df['map_size'] = 50
        map_df.iloc[:5, map_df.columns.get_loc('map_size')] = 200
        
        dark_orange, dark_blue = [180, 60, 0, 230], [30, 70, 140, 180]
        map_df['map_color'] = pd.Series([dark_blue] * len(map_df))
        map_df.iloc[:5, map_df.columns.get_loc('map_color')] = pd.Series([dark_orange] * 5)
        
        map_df['map_label'] = ""
        map_df.iloc[:5, map_df.columns.get_loc('map_label')] = map_df['Name'][:5]

        st.pydeck_chart(pdk.Deck(
            map_style="light", 
            layers=[
                pdk.Layer("ScatterplotLayer", map_df, get_position=["lon", "lat"], get_fill_color="map_color", get_radius="map_size", pickable=True),
                pdk.Layer("TextLayer", map_df, get_position=["lon", "lat"], get_text="map_label", get_color="map_color", get_size=20, get_outline_color=[255,255,255,255], get_outline_width=2)
            ],
            initial_view_state=pdk.ViewState(latitude=map_df['lat'].mean(), longitude=map_df['lon'].mean(), zoom=8),
            tooltip={"text": "{Name}\nPrice: ${Price:.0f}\nRank: {BTP Ranking}"}
        ))
    else:
        st.write("No courses found.")

with tab2:
    st.subheader("Ranked Results")
    display_cols = ['Name', 'Holes', 'BTP Ranking', 'Price', 'dist_miles', 'Played already', 'Final Score']
    st.dataframe(
        results[display_cols].style.format({'Price': '{:.0f}', 'dist_miles': '{:.1f}', 'Final Score': '{:.2f}'}),
        hide_index=True, use_container_width=True
    )

st.caption("⚠️ Distances are calculated 'as the crow flies.' Cape Cod travel times may vary!")