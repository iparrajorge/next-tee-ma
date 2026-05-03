import streamlit as st


def render(results, st_supabase):
    """Render the 📊 Ranked Table tab."""
    # ── First-visit hint ───────────────────────────────────────────────────────
    if not st.session_state.get("seen_table_hint", False):
        user_id = st.session_state.user_id
        result = st_supabase.table("user_flags") \
            .select("seen_table_hint") \
            .eq("user_id", user_id) \
            .execute()

        seen = result.data[0]["seen_table_hint"] if result.data else False
        st.session_state.seen_table_hint = seen

        if not seen:
            st.info(
                "📊 **Ranked Table** — Courses are scored based on your sidebar preferences. "
                "Check the **Played?** box for any course you've played, then hit **Sync** to save."
            )
            if st.button("Got it ✓", key="dismiss_table_hint"):
                st_supabase.table("user_flags").upsert({
                    "user_id": user_id,
                    "seen_table_hint": True,
                }, on_conflict="user_id").execute()
                st.session_state.seen_table_hint = True
                st.rerun()


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
        for _, row in edited_df.iterrows():
            st_supabase.table("user_courses").upsert({
                "user_id":   user_id,
                "course_id": row["Course_ID"],
                "played":    bool(row["played"]),
            }, on_conflict="user_id,course_id").execute()
        st.success("Synced to the Cloud!")
        st.rerun()