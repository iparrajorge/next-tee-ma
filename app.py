import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import os
from geopy.geocoders import Nominatim
from streamlit_gsheets import GSheetsConnection

# Create the connection object
conn = st.connection("gsheets", type=GSheetsConnection)

# Replace 'YOUR_SHEET_URL' with the actual URL of your Google Sheet
SHEET_URL = "https://docs.google.com/spreadsheets/d/13qdUj2WBmp3mMTYSUtsbuITn3TPEHro-NTt73ZylzGI/edit?usp=sharing"

# Define separate filenames for the tab and the header
FAVICON_FILENAME = "favicon.png"  # The tiny one for the browser tab
HEADER_LOGO_FILENAME = "logo.png" # The main logo for the page

# ==========================================
# 1. PAGE SETUP & HEADER (NextTee Branding)
# ==========================================

# A. Set Browser/Tab Config
# We check if the logo exists; if so, it becomes your browser tab icon.
# If it doesn't exist yet, we use the golf emoji as a fallback.
st.set_page_config(
    page_title="NextTee MA", 
    layout="wide", 
    # Use the favicon here
    page_icon=FAVICON_FILENAME if os.path.exists(FAVICON_FILENAME) else "⛳"
)

# B. Handle Logo and Title Layout
if os.path.exists(HEADER_LOGO_FILENAME):
    st.image(HEADER_LOGO_FILENAME, width=450)
st.subheader(
    "A Massachusetts Golf Course Recommender", 
    help="""
**How NextTee Works:**

This app uses a user-weighted multi-objective optimization algorithm to rank public courses in Massachusetts.

Go to the left side and enter your preferences. The results will adapt automatically.

* **Course History:** Have you played the course before? How adventurous do you feel? Show all the courses or those you haven't played yet?
* **Course Size:** 18 or 9? How much time do you have?
* **Price:** Do you want to keep cost under control? Is this a special ocasion? You decide.
* **Prestige:** Based on the BTP Ranking.
* **Proximity:** Calculated via 'as the crow flies' distance from your location.

*Note: Traffic to the Cape isn't factored into the mileage!*
    """
)

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
explore_choice = st.sidebar.radio(
    "Course History", 
    ["All", "New"], 
    index=0,
    help="'New' only shows courses you haven't played yet."
)

# B. Location Inputs
@st.cache_data(show_spinner=False)
def get_coordinates(address_string):
    """
    Caches the geocoding result so we don't spam the API.
    Increased timeout to prevent silent failures.
    """
    # Make sure this string is unique to you! 
    geolocator = Nominatim(user_agent="nexttee_ma_golf_app_v1") 
    
    try:
        # THE FIX: Added timeout=10. This gives the free server time to think.
        location = geolocator.geocode(address_string + ", Massachusetts", timeout=10)
        
        if location:
            return location.latitude, location.longitude, location.address
            
    except Exception as e:
        # This will print the exact error in your VS Code/Terminal console!
        print(f"Geocoding Error: {e}") 
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
cloud_data = conn.read(spreadsheet=SHEET_URL, ttl=0) # ttl=0 ensures it's never stale
df_raw_with_played = df_raw.merge(cloud_data, on="Course_ID", how="left").fillna(0)

# Then your existing filtering logic continues using df_raw_with_played
df_raw_with_played['Played'] = df_raw_with_played['Played'].astype(bool)

# New logic: Only filter if 'New' is selected. 
# This treats any value > 0 (1, 2, etc.) as 'Played'.
if explore_choice == "New":
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
    k = 0.01
    raw_rank_score = np.exp(-k * (data['BTP Ranking'] - 1))
    data['rank_score'] = (raw_rank_score - raw_rank_score.min()) / (raw_rank_score.max() - raw_rank_score.min() + 1e-6)
    
    # D. Normalize Distance (Capped at 50 miles)
    dist_cap = 50
    min_dist = data['dist_miles'].min()
    data['dist_score'] = data['dist_miles'].apply(
        lambda x: 0 if x > dist_cap else (dist_cap - x) / (dist_cap - min_dist) if dist_cap != min_dist else 1
    )
    
    # FINAL WEIGHTED SCORE
    data['Score'] = (data['price_score'] * p_w) + \
                          (data['rank_score'] * r_w) + \
                          (data['dist_score'] * d_w)
    
    return data.sort_values(by='Score', ascending=False)

results = calculate_scores(df)

# 5. DISPLAY
tab1, tab2 = st.tabs(["📊 Ranked Table", "🗺️ Map View"])

with tab1:
    st.subheader("Ranked Results")
    
    # Define which columns to show
    display_cols = ['Score', 'Name', 'BTP Ranking', 'Price', 'dist_miles', 'Played', 'Holes', 'Course_ID']
    
    # THE INTERACTIVE TABLE
    edited_df = st.data_editor(
        results[display_cols],
        column_config={
            "Played": st.column_config.CheckboxColumn("Played already?", default=False),
            "Price": st.column_config.NumberColumn(format="$%d"),
            "dist_miles": st.column_config.NumberColumn(format="%.1f mi"),
            "Score": st.column_config.NumberColumn(format="%.2f"),
            "Course_ID": None  # This hides the ID from the user but keeps it in the data
        },
        disabled=['Score', 'Name', 'BTP Ranking', 'Price', 'dist_miles', 'Holes'],
        hide_index=True, 
        use_container_width=True
    )

    # THE SYNC BUTTON
    if st.button("Sync My Progress ☁️"):
        update_data = edited_df[["Course_ID", "Played"]]
        # The connection now has 'Service Account' powers and won't throw that error
        conn.update(spreadsheet=SHEET_URL, data=update_data)
        st.success("Synced!")

with tab2:
    st.subheader(f"Top Recommended {hole_choice}-Hole Courses")
    if not results.empty:
        # 1. Prepare User Location Data with dummy values to satisfy the tooltip
        user_df = pd.DataFrame([{
            'lat': user_lat, 
            'lon': user_lon, 
            'Name': '📍 Your Location',
            'Price_Label': '-', 
            'BTP Ranking': '-'
        }])

        # 2. Prepare Course Data
        map_df = results.copy().rename(columns={'Location X': 'lat', 'Location Y': 'lon'}).reset_index(drop=True)
        map_df['Price_Label'] = map_df['Price'].apply(lambda x: f"${int(x)}" if pd.notnull(x) else "N/A")
        
        top_5 = map_df.head(5).copy()
        others = map_df.iloc[5:].copy()

        # 3. Layers (Same as before)
        other_layer = pdk.Layer("ScatterplotLayer", others, get_position=["lon", "lat"], 
                                get_fill_color=[40, 40, 40, 200], get_radius=900, pickable=True)

        top_layer = pdk.Layer("ScatterplotLayer", top_5, get_position=["lon", "lat"], 
                              get_fill_color=[34, 139, 34, 255], get_radius=1500, pickable=True)

        user_layer = pdk.Layer("ScatterplotLayer", user_df, get_position=["lon", "lat"], 
                               get_fill_color=[200, 30, 30, 255], get_radius=1500, pickable=True)

        # 4. Render
        st.pydeck_chart(pdk.Deck(
            map_style="light",
            initial_view_state=pdk.ViewState(latitude=user_lat, longitude=user_lon, zoom=8),
            layers=[other_layer, top_layer, user_layer],
            tooltip={"text": "{Name}\nPrice: {Price_Label}\nRank: {BTP Ranking}"}
        ))

st.caption("⚠️ Distances are calculated 'as the crow flies.' Cape Cod travel times may vary!")