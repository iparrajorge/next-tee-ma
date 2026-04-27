import numpy as np
import pandas as pd
import streamlit as st
from config import SHEET_URL


# ── Loading ────────────────────────────────────────────────────────────────────
def load_data(conn):
    """
    Load the local CSV and merge in the Google Sheets 'Played' column.

    Returns
    -------
    df     : merged DataFrame used for filtering / scoring (same as before)
    df_all : same merge but on ALL holes (needed for Personal Ranking tab)
    """
    df_raw     = pd.read_csv("MA_Courses_Basic.csv")
    cloud_data = conn.read(spreadsheet=SHEET_URL, ttl=1)

    def _merge(base):
        merged = base.merge(
            cloud_data[["Course_ID", "Played"]], on="Course_ID", how="left"
        ).fillna(0)
        merged["Played"] = merged["Played"].astype(bool)
        return merged

    df     = _merge(df_raw)
    df_all = _merge(df_raw)          # identical for now; kept separate for clarity
    return df, df_all


# ── Filtering ─────────────────────────────────────────────────────────────────
def filter_data(df):
    """
    Apply hole-count and played/new filters using values from session_state.
    Must be called after sidebar.render_sidebar() has run.
    """
    hole_choice    = st.session_state.hole_choice
    explore_choice = st.session_state.explore_choice

    df_filtered = df[df["Holes"] == hole_choice]
    if explore_choice == "New":
        df_filtered = df_filtered[df_filtered["Played"] == False]
    return df_filtered


# ── Scoring ───────────────────────────────────────────────────────────────────
def calculate_scores(data):
    """
    Score and rank courses.

    Reads user_lat, user_lon, p_w, r_w, d_w from st.session_state so that
    the weights are always exactly what the sidebar last rendered — no risk
    of stale values from a previous run being passed as arguments.
    """
    if data.empty:
        return data

    # Pull weights + location from session_state
    user_lat = st.session_state.user_lat
    user_lon = st.session_state.user_lon
    p_w      = st.session_state.p_w
    r_w      = st.session_state.r_w
    d_w      = st.session_state.d_w

    data = data.copy()

    # Distance (miles, Euclidean approximation)
    data["dist_miles"] = np.sqrt(
        (69.1 * (data["Location X"] - user_lat)) ** 2 +
        (51.4 * (data["Location Y"] - user_lon)) ** 2
    )

    # Price score (lower price → higher score; anything above $150 scores 0)
    price_cap = 150
    data["price_score"] = data["Price"].apply(
        lambda x: 0 if x > price_cap
        else (price_cap - x) / (price_cap - data["Price"].min() + 1e-6)
    )

    # Rank score (exponential decay on BTP Ranking, then normalised 0–1)
    k = 0.01
    raw_rank_score    = np.exp(-k * (data["BTP Ranking"] - 1))
    data["rank_score"] = (
        (raw_rank_score - raw_rank_score.min()) /
        (raw_rank_score.max() - raw_rank_score.min() + 1e-6)
    )

    # Distance score (anything beyond 50 miles scores 0)
    dist_cap = 50
    data["dist_score"] = data["dist_miles"].apply(
        lambda x: 0 if x > dist_cap
        else (dist_cap - x) / (dist_cap - data["dist_miles"].min() + 1e-6)
    )

    # Weighted composite score — weights come from session_state
    data["Score"] = (
        data["price_score"] * p_w +
        data["rank_score"]  * r_w +
        data["dist_score"]  * d_w
    )

    return data.sort_values(by="Score", ascending=False)
