import streamlit as st
from config import SHEET_URL


def render(results, conn):
    """Render the 📊 Ranked Table tab."""
    st.session_state.active_tab = 0

    if results.empty:
        st.warning("No courses match those filters. Try opening up your options!")
        return

    display_cols = [
        "Score", "Name", "BTP Ranking", "Price",
        "dist_miles", "Played", "Course_ID", "Website_Link",
    ]

    edited_df = st.data_editor(
        results[display_cols],
        column_config={
            "Played":       st.column_config.CheckboxColumn("Played already?", default=False),
            "Price":        st.column_config.NumberColumn(format="$%d"),
            "dist_miles":   st.column_config.NumberColumn(format="%.1f mi"),
            "Score":        st.column_config.NumberColumn(format="%.2f"),
            "Website_Link": st.column_config.LinkColumn("Website_Link", display_text="Visit Site"),
            "Course_ID":    None,
        },
        disabled=["Score", "Name", "BTP Ranking", "Price", "dist_miles", "Website_Link"],
        hide_index=True,
        use_container_width=True,
    )

    if st.button("Sync My Progress ☁️"):
        conn.update(spreadsheet=SHEET_URL, data=edited_df[["Course_ID", "Played"]])
        st.cache_data.clear()
        st.success("Synced to the Cloud!")
