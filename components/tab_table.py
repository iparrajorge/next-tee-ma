import streamlit as st
from config import SHEET_URL


def render(results, st_supabase):
    """Render the 📊 Ranked Table tab."""

    if results.empty:
        st.warning("No courses match those filters. Try opening up your options!")
        return

    display_cols = [
        "Score", "Name", "BTP Ranking", "Price",
        "dist_miles", "played", "Course_ID", "Website_Link",
    ]

    display_df = results[display_cols].copy()

    # Encode the course name into the URL as a fragment so LinkColumn
    # can extract and display it via a regex, keeping the URL functional.
    # Format: <url>#<name>  →  display_text regex captures the name after #
    def make_link(row):
        url = row["Website_Link"]
        name = row["Name"]
        if not url or (isinstance(url, float)):
            return None
        safe_name = str(name).replace("#", "")
        return f"{url}#{safe_name}"

    display_df["Link"] = display_df.apply(make_link, axis=1)

    display_cols_final = [
        "Score", "Name", "BTP Ranking", "Price",
        "dist_miles", "played", "Course_ID", "Link",
    ]

    edited_df = st.data_editor(
        display_df[display_cols_final],
        column_config={
            "Played":      st.column_config.CheckboxColumn("Played?", default=False),
            "Price":       st.column_config.NumberColumn("Price ($)", format="%d"),
            "dist_miles":  st.column_config.NumberColumn("Distance (mi)", format="%.1f"),
            "Score":       st.column_config.NumberColumn(format="%.2f"),
            "BTP Ranking": st.column_config.NumberColumn(
                               "Ranking",
                               help="BTP Ranking",
                           ),
            "Link":        st.column_config.LinkColumn(
                               "Link",
                               display_text=r"#(.+)$",
                           ),
            "Course_ID":   None,
        },
        disabled=["Score", "Name", "BTP Ranking", "Price", "dist_miles", "Link"],
        hide_index=True,
        use_container_width=True,
    )

    if st.button("Sync My Progress ☁️"):
        user_id = st.session_state.user_id
        played_df = edited_df[edited_df["played"] == True]
        for _, row in played_df.iterrows():
            st_supabase.table("user_courses").upsert({
                "user_id":   user_id,
                "course_id": row["Course_ID"],
                "played":    True,
            }, on_conflict="user_id,course_id").execute()
        st.success("Synced to the Cloud!")
        st.rerun()