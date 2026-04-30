import numpy as np
import pandas as pd
import streamlit as st


# ── Loading ────────────────────────────────────────────────────────────────────
def load_data(st_supabase):
    """
    Load courses from Supabase and merge with the user's played/ranking data.

    Returns
    -------
    df     : merged DataFrame used for filtering / scoring
    df_all : same data but unfiltered by holes (needed for Personal Ranking tab)
    """
    user_id = st.session_state.user_id

    # Load all courses
    courses_resp = st_supabase.table("courses").select("*").execute()
    df_raw = pd.DataFrame(courses_resp.data)

    # Load this user's played/ranking data
    user_resp = (
        st_supabase.table("user_courses")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    user_df = pd.DataFrame(user_resp.data) if user_resp.data else pd.DataFrame(
        columns=["course_id", "played", "personal_rank"]
    )

    # Merge
    df = df_raw.merge(
        user_df[["course_id", "played", "personal_rank"]],
        left_on="Course_ID",
        right_on="course_id",
        how="left"
    )
    df["played"] = df["played"].fillna(False).astype(bool)
    df["personal_rank"] = df["personal_rank"].fillna(0).astype(int)

    df_all = df.copy()
    return df, df_all


# ── Filtering ─────────────────────────────────────────────────────────────────
def filter_data(df):
    """
    Apply hole-count and played/new filters using values from session_state.
    """
    hole_choice    = st.session_state.hole_choice
    explore_choice = st.session_state.explore_choice

    df_filtered = df[df["Holes"] == hole_choice]
    if explore_choice == "New":
        df_filtered = df_filtered[df_filtered["played"] == False]
    return df_filtered


# ── Scoring ───────────────────────────────────────────────────────────────────
def calculate_scores(data):
    """
    Score and rank courses using weights from session_state.
    """
    if data.empty:
        return data

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

    # Price score
    price_cap = 150
    data["price_score"] = data["Price"].apply(
        lambda x: 0 if x > price_cap
        else (price_cap - x) / (price_cap - data["Price"].min() + 1e-6)
    )

    # Rank score
    k = 0.01
    raw_rank_score     = np.exp(-k * (data["BTP Ranking"] - 1))
    data["rank_score"] = (
        (raw_rank_score - raw_rank_score.min()) /
        (raw_rank_score.max() - raw_rank_score.min() + 1e-6)
    )

    # Distance score
    dist_cap = 50
    data["dist_score"] = data["dist_miles"].apply(
        lambda x: 0 if x > dist_cap
        else (dist_cap - x) / (dist_cap - data["dist_miles"].min() + 1e-6)
    )

    # Weighted composite score
    data["Score"] = (
        data["price_score"] * p_w +
        data["rank_score"]  * r_w +
        data["dist_score"]  * d_w
    )

    return data.sort_values(by="Score", ascending=False)