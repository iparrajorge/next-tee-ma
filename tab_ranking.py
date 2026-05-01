import streamlit as st
from streamlit_sortables import sort_items


# ── BTP-neighbour insertion ────────────────────────────────────────────────────
def _btp_insert_position(new_name, current_ranking, df_ref):
    """
    Insert a newly-played course into the personal ranking at a position
    that respects its relative BTP rank among already-ranked courses.
    """
    if not current_ranking:
        return 0

    new_btp = df_ref.loc[df_ref["Name"] == new_name, "BTP Ranking"].iloc[0]

    ranked = []
    for pos, name in enumerate(current_ranking):
        row = df_ref.loc[df_ref["Name"] == name, "BTP Ranking"]
        if not row.empty:
            ranked.append((pos, row.iloc[0]))

    better = [(pos, btp) for pos, btp in ranked if btp < new_btp]
    worse  = [(pos, btp) for pos, btp in ranked if btp > new_btp]

    if not better:
        return 0
    if not worse:
        return len(current_ranking)

    pos_better = max(better, key=lambda x: x[1])[0]
    pos_worse  = min(worse,  key=lambda x: x[1])[0]
    return (min(pos_better, pos_worse) + max(pos_better, pos_worse) + 1) // 2


def render(df_all, st_supabase):
    """Render the 🏅 Personal Ranking tab."""

    played_courses = df_all[df_all["played"] == True]["Name"].tolist()

    if not played_courses:
        st.info(
            "You haven't marked any courses as played yet. "
            "Check off courses in the Ranked Table tab first."
        )
        return

    # Initialise ranking state on first visit to this tab
    if "personal_ranking" not in st.session_state:
        previously_ranked = (
            df_all[df_all["personal_rank"] > 0]
            .sort_values("personal_rank")["Name"]
            .tolist()
        )
        st.session_state.personal_ranking = previously_ranked
        st.session_state.ranking_changed  = False

    current = st.session_state.personal_ranking

    # Insert newly played courses via BTP neighbour logic
    already_ranked = set(current)
    for new_course in [c for c in played_courses if c not in already_ranked]:
        pos = _btp_insert_position(new_course, current, df_all)
        current.insert(pos, new_course)

    # Drop courses that have been un-checked
    current = [c for c in current if c in set(played_courses)]
    st.session_state.personal_ranking = current

    st.caption("Drag to reorder your personal ranking. If a friend asked you to play tomorrow and ofered you two courses which one would you choose? Money and distance don't matter")
    new_order = sort_items(current, key=f"personal_ranking_sort_{len(current)}")

    if new_order != current:
        st.session_state.personal_ranking = new_order
        st.session_state.ranking_changed  = True

    st.divider()
    for i, name in enumerate(st.session_state.personal_ranking):
        st.markdown(f"**{i+1}.** {name}")
    st.divider()

    if st.button(
        "Sync My Ranking ☁️",
        disabled=not st.session_state.get("ranking_changed", False),
    ):
        user_id = st.session_state.user_id
        for rank, course_name in enumerate(st.session_state.personal_ranking, start=1):
            course_id = df_all[df_all["Name"] == course_name]["Course_ID"].iloc[0]
            st_supabase.table("user_courses").upsert({
                "user_id":       user_id,
                "course_id":     course_id,
                "played":        True,
                "personal_rank": rank,
            }, on_conflict="user_id,course_id").execute()
        st.session_state.ranking_changed = False
        st.success("Personal ranking synced!")