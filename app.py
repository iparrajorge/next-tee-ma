import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import os
from geopy.geocoders import Nominatim
from streamlit_gsheets import GSheetsConnection
from st_supabase_connection import SupabaseConnection # Add this

# 1. PAGE SETUP
FAVICON_FILENAME = "favicon.png"
HEADER_LOGO_FILENAME = "logo.png"

st.set_page_config(
    page_title="NextTee MA", 
    layout="wide", 
    page_icon=FAVICON_FILENAME if os.path.exists(FAVICON_FILENAME) else "⛳"
)

if os.path.exists(HEADER_LOGO_FILENAME):
    st.image(HEADER_LOGO_FILENAME, width=450)

# Force-feeding the verified secrets into the connection
st_supabase = st.connection(
    "supabase",
    type=SupabaseConnection,
    url=st.secrets["connections"]["supabase"]["url"].strip("/"), # Ensures no trailing slash
    key=st.secrets["connections"]["supabase"]["key"]
)

# Connection & URL
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/13qdUj2WBmp3mMTYSUtsbuITn3TPEHro-NTt73ZylzGI/edit?usp=sharing"


# Initialize session state for auth
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_id = None

# --- AUTHENTICATION UI ---
if not st.session_state.authenticated:
    st.markdown("## Find Your Perfect Round of Public Golg in Massachusetts")
    st.markdown("""
    **NextTee MA** uses a custom ranking algorithm to find the best public golf courses 
    based on your specific priorities. Join our community to:
    * **Personalized Rankings:** Weight Price, Quality, and Distance to fit your mood.
    * **Track Your Progress:** Save which of the 100+ MA courses you've played.
    """)
    
    st.info("Registration is free. We only use your email to save your personal course history.")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Log In"):
            try:
                response = st_supabase.auth.sign_in_with_password({"email": email, "password": password})
                if response:
                    st.session_state.authenticated = True
                    st.session_state.user_id = response.user.id
                    st.rerun()
            except Exception as e:
                st.error("Invalid login credentials.")

    with tab2:
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_pw")
        if st.button("Create Account"):
            try:
                response = st_supabase.auth.sign_up({"email": new_email, "password": new_password})
                # If confirm email is OFF, Supabase returns the session immediately
                if response.session:
                    st.session_state.authenticated = True
                    st.session_state.user_id = response.user.id
                    st.success("Welcome aboard!")
                    st.rerun()
                else:
                    st.success("Account created! Please log in.")
            except Exception as e:
                st.error(f"Account could not be created. (Check if email is already in use)")
    
    st.stop() # Stops the rest of the app from loading until logged in

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

# 2. SIDEBAR - USER INPUTS
# This only runs if st.session_state.authenticated is True
st.sidebar.write(f"Logged in as: {st_supabase.auth.get_user().user.email}")
if st.sidebar.button("Sign Out"):
    st_supabase.auth.sign_out()
    st.session_state.authenticated = False
    st.rerun()

st.sidebar.header("User Preferences")

hole_choice = st.sidebar.radio("Course Size", [18, 9], index=0, format_func=lambda x: f"{x} Holes")
explore_choice = st.sidebar.radio(
    "Course History", 
    ["All", "New"], 
    index=0,
    help="'New' only shows courses you haven't played yet."
)

# Location Logic
@st.cache_data(show_spinner=False)
def get_coordinates(address_string):
    geolocator = Nominatim(user_agent="nexttee_ma_golf_app_v2") 
    try:
        location = geolocator.geocode(address_string + ", Massachusetts", timeout=10)
        if location:
            return location.latitude, location.longitude, location.address
    except Exception:
        return None, None, None
    return None, None, None

st.sidebar.subheader("Your Location")
address_input = st.sidebar.text_input("Enter City, Zip, or Address", value="Boston City Hall")

user_lat, user_lon = 42.3601, -71.0589 
if address_input:
    lat, lon, full_name = get_coordinates(address_input)
    if lat:
        user_lat, user_lon = lat, lon
        st.sidebar.success(f"📍 {full_name.split(',')[0]}")

# --- RESTORED PERCENTAGE FEEDBACK ---
st.sidebar.markdown("---")
st.sidebar.subheader("Priority Balance")
st.sidebar.write("Adjust how much you care about each factor:")

imp_price = st.sidebar.slider("Price Sensitivity", 0, 10, 5)
imp_rank = st.sidebar.slider("Course Prestige", 0, 10, 5)
imp_dist = st.sidebar.slider("Proximity/Distance", 0, 10, 5)

total_imp = imp_price + imp_rank + imp_dist

if total_imp == 0:
    p_w, r_w, d_w = 0.33, 0.33, 0.33
else:
    p_w = imp_price / total_imp
    r_w = imp_rank / total_imp
    d_w = imp_dist / total_imp

# The visual feedback you liked:
st.sidebar.markdown(f"""
**Current Weighting:**
* 💰 Price: {p_w:.0%}
* 🏆 Rank: {r_w:.0%}
* 🚗 Dist: {d_w:.0%}
""")
# ------------------------------------

# 3. DATA LOADING & MERGING
try:
    df_raw = pd.read_csv("MA_Courses_Basic.csv")
    cloud_data = conn.read(spreadsheet=SHEET_URL, ttl=0)
    
    # Merge on Course_ID to sync Played status
    df = df_raw.merge(cloud_data[['Course_ID', 'Played']], on="Course_ID", how="left").fillna(0)
    df['Played'] = df['Played'].astype(bool)

except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# 4. FILTERING & SCORING
df = df[df['Holes'] == hole_choice]

if explore_choice == "New":
    df = df[df['Played'] == False]

def calculate_scores(data):
    if data.empty:
        return data
        
    # Distance
    data['dist_miles'] = np.sqrt((69.1 * (data['Location X'] - user_lat))**2 + 
                                 (51.4 * (data['Location Y'] - user_lon))**2)
    
    # Normalizations
    price_cap = 150
    data['price_score'] = data['Price'].apply(
        lambda x: 0 if x > price_cap else (price_cap - x) / (price_cap - data['Price'].min() + 1e-6)
    )
    
    k = 0.01
    raw_rank_score = np.exp(-k * (data['BTP Ranking'] - 1))
    data['rank_score'] = (raw_rank_score - raw_rank_score.min()) / (raw_rank_score.max() - raw_rank_score.min() + 1e-6)
    
    dist_cap = 50
    data['dist_score'] = data['dist_miles'].apply(
        lambda x: 0 if x > dist_cap else (dist_cap - x) / (dist_cap - data['dist_miles'].min() + 1e-6)
    )
    
    data['Score'] = (data['price_score'] * p_w) + (data['rank_score'] * r_w) + (data['dist_score'] * d_w)
    return data.sort_values(by='Score', ascending=False)

results = calculate_scores(df)

# 5. DISPLAY
tab1, tab2 = st.tabs(["📊 Ranked Table", "🗺️ Map View"])

with tab1:
    if results.empty:
        st.warning("No courses match those filters. Try opening up your options!")
    else:
        display_cols = ['Score', 'Name', 'BTP Ranking', 'Price', 'dist_miles', 'Played', 'Course_ID', 'Website_Link']
        
        edited_df = st.data_editor(
            results[display_cols],
            column_config={
                "Played": st.column_config.CheckboxColumn("Played already?", default=False),
                "Price": st.column_config.NumberColumn(format="$%d"),
                "dist_miles": st.column_config.NumberColumn(format="%.1f mi"),
                "Score": st.column_config.NumberColumn(format="%.2f"),
                "Website_Link": st.column_config.LinkColumn("Website_Link", display_text="Visit Site"),
                "Course_ID": None 
            },
            disabled=['Score', 'Name', 'BTP Ranking', 'Price', 'dist_miles', 'Website_Link'],
            hide_index=True, 
            use_container_width=True
        )

        if st.button("Sync My Progress ☁️"):
            update_data = edited_df[["Course_ID", "Played"]]
            conn.update(spreadsheet=SHEET_URL, data=update_data)
            st.success("Synced to the Cloud!")

with tab2:
    if not results.empty:
        map_df = results.copy().rename(columns={'Location X': 'lat', 'Location Y': 'lon'})
        st.pydeck_chart(pdk.Deck(
            map_style="light",
            initial_view_state=pdk.ViewState(latitude=user_lat, longitude=user_lon, zoom=8),
            layers=[
                pdk.Layer("ScatterplotLayer", map_df.head(5), get_position=["lon", "lat"], get_fill_color=[34, 139, 34, 255], get_radius=1500, pickable=True),
                pdk.Layer("ScatterplotLayer", map_df.iloc[5:], get_position=["lon", "lat"], get_fill_color=[40, 40, 40, 200], get_radius=900, pickable=True),
                pdk.Layer("ScatterplotLayer", pd.DataFrame([{'lat': user_lat, 'lon': user_lon}]), get_position=["lon", "lat"], get_fill_color=[200, 30, 30, 255], get_radius=1500)
            ],
            tooltip={"text": "{Name}\nRank: {BTP Ranking}\nPrice: ${Price}"}
        ))