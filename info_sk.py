After the spli and merge the dataframe take the form:
    
{
    "GIMT": {
        "all": <DataFrame>,
        "in": <DataFrame>,
        "out": <DataFrame>,
        "merged": <DataFrame>
    },
    "GIPS": {
        "all": <DataFrame>,
        "in": <DataFrame>,
        "out": <DataFrame>,
        "merged": <DataFrame>
    },
    "ADMIN": {
        "all": <DataFrame>,
        "in": <DataFrame>,
        "out": <DataFrame>,
        "merged": <DataFrame>
    },
    "LEAVE": {
        "raw": <DataFrame>
    },
    "EXEMPTED": {
        "raw": <DataFrame>
    }
}
# for faculty    
df_fac_all = pd.concat(
    [st.session_state["attendance_splits"]["GIMT"]["all"],
     st.session_state["attendance_splits"]["GIPS"]["all"]],
    ignore_index=True
)

# Split data
df_admin_all = st.session_state["attendance_splits"]["ADMIN"]["all"]
df_admin_in = st.session_state["attendance_splits"]["ADMIN"]["in"]
df_admin_out = st.session_state["attendance_splits"]["ADMIN"]["out"]

# Processed with merge rules
df_admin_merged = st.session_state["attendance_splits"]["ADMIN"]["merged"]

# leave and exempted raw data
df_leave_raw = st.session_state["attendance_splits"]["LEAVE"]["raw"]
df_exempted_raw = st.session_state["attendance_splits"]["EXEMPTED"]["raw"]