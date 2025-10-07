import streamlit as st
import pandas as pd
from utility import connect_gsheet, get_dataframe, gs_client, fix_streamlit_layout, set_compact_theme
from datetime import datetime, date
import gspread

def app():
    fix_streamlit_layout(padding_top="0.6rem")
    set_compact_theme()
    
    st.header("🎓 Mentor-Mentee Assignment")
    
    # Get current user and role
    current_user = st.session_state.get("current_user", None)
    user_role = st.session_state.get("role", "guest")
    
    if not current_user:
        st.error("⚠️ Please log in first.")
        return
    
    # Display current user info
    user_name = current_user.get('Name', 'Unknown User')
    st.markdown(
        f"<div style='text-align:right; font-size:12px; color:gray;'>👤 {user_name} ({user_role.upper()})</div>",
        unsafe_allow_html=True
    )
    
    # Debug: Show user information (remove this in production)
    if st.checkbox("🔍 Debug: Show User Info", key="debug_user_info"):
        st.write("**Current User Data:**")
        st.json(current_user)
        st.write("**User Role:**", user_role)
    
    try:
        # Connect to Google Sheets
        gs_client = connect_gsheet()
        
        # Fetch data from both sheets
        df_users = get_dataframe(gs_client, st.secrets["my_secrets"]["sheet_id"], "users")
        df_students = get_dataframe(gs_client, st.secrets["my_secrets"]["sheet_id"], "students")
        
        # Filter data based on user role
        filtered_students = filter_students_by_role(df_students, current_user, user_role)
        available_mentors = filter_mentors_by_role(df_users, current_user, user_role)
        
        if filtered_students.empty:
            st.warning("⚠️ No students available for assignment based on your role.")
            return
        
        # Display filters and get selected values
        filters = display_filters(filtered_students)
        
        # Apply filters
        filtered_df = apply_filters(filtered_students, filters)
        
        st.write(f"**Total Records:** {len(filtered_df)}")
        
        if not filtered_df.empty:
            # Display assignment interface
            display_assignment_interface(filtered_df, available_mentors, current_user, user_role, gs_client)
        else:
            st.warning("No records match your filters.")
            
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return

def filter_students_by_role(df_students, current_user, user_role):
    """Filter students based on user role and permissions"""
    if user_role == "admin" or user_role == "mentor_admin":
        # Admin and Mentor admin can see all students
        return df_students
    elif user_role == "hod":
        # HOD can see students from their department
        user_dept = current_user.get("Department", "")
        return df_students[df_students["Department"] == user_dept]
    elif user_role == "coordinator":
        # Coordinator can see students from their semester
        user_semester = current_user.get("Semester", "")
        return df_students[df_students["Semester"] == user_semester]
    elif user_role == "mentor":
        # Mentor can see students already assigned to them
        user_name = current_user.get("Name", "")
        return df_students[df_students["Mentor"] == user_name]
    else:
        return pd.DataFrame()

def filter_mentors_by_role(df_users, current_user, user_role):
    """Filter available mentors based on user role and permissions"""
    if user_role == "admin" or user_role == "mentor_admin":
        # Admin and Mentor admin can assign any mentor
        return df_users[df_users["User Type"].isin(["mentor", "hod", "coordinator", "mentor_admin", "admin"])]
    elif user_role == "hod":
        # HOD can assign mentors from their department
        user_dept = current_user.get("Department", "")
        return df_users[(df_users["Department"] == user_dept) & 
                       (df_users["User Type"].isin(["mentor", "coordinator"]))]
    elif user_role == "coordinator":
        # Coordinator can assign mentors from their department
        user_dept = current_user.get("Department", "")
        return df_users[(df_users["Department"] == user_dept) & 
                       (df_users["User Type"] == "mentor")]
    elif user_role == "mentor":
        # Mentor can only assign themselves
        user_name = current_user.get("Name", "")
        return df_users[df_users["Name"] == user_name]
    else:
        return pd.DataFrame()

def display_filters(df_students):
    """Display filter options and return selected filters"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        program_options = ["All"] + sorted(df_students["Program"].astype(str).unique().tolist())
        program_filter = st.selectbox("Program", program_options, key="program_filter")
    
    with col2:
        semester_options = ["All"] + sorted(df_students["Semester"].astype(str).unique().tolist())
        semester_filter = st.selectbox("Semester", semester_options, key="semester_filter")
    
    with col3:
        department_options = ["All"] + sorted(df_students["Department"].astype(str).unique().tolist())
        department_filter = st.selectbox("Department", department_options, key="department_filter")
    
    with col4:
        mentor_options = ["All", "Unassigned"] + sorted(df_students["Mentor"].dropna().astype(str).unique().tolist())
        mentor_filter = st.selectbox("Current Mentor", mentor_options, key="mentor_filter")
    
    return {
        "program_filter": program_filter,
        "semester_filter": semester_filter,
        "department_filter": department_filter,
        "mentor_filter": mentor_filter
    }

def apply_filters(df_students, filters):
    """Apply selected filters to the dataframe"""
    filtered_df = df_students.copy()
    
    if filters["program_filter"] != "All":
        filtered_df = filtered_df[filtered_df["Program"] == filters["program_filter"]]
    
    if filters["semester_filter"] != "All":
        filtered_df = filtered_df[filtered_df["Semester"] == filters["semester_filter"]]
    
    if filters["department_filter"] != "All":
        filtered_df = filtered_df[filtered_df["Department"] == filters["department_filter"]]
    
    mentor_filter = filters["mentor_filter"]
    if mentor_filter == "Unassigned":
        filtered_df = filtered_df[filtered_df["Mentor"].isna() | (filtered_df["Mentor"] == "")]
    elif mentor_filter != "All":
        filtered_df = filtered_df[filtered_df["Mentor"] == mentor_filter]
    
    return filtered_df

def display_assignment_interface(df_students, available_mentors, current_user, user_role, gs_client):
    """Display the main assignment interface"""
    
    # Add selection column
    df_display = df_students.copy()
    df_display["Select"] = False
    
    # Display columns based on role
    if user_role == "admin" or user_role == "mentor_admin":
        display_cols = ['Student ID', 'Student Name', 'Program', 'Semester', 'Department', 'Mentor', 'Select']
    else:
        display_cols = ['Student ID', 'Student Name', 'Program', 'Semester', 'Mentor', 'Select']
    
    # Display the dataframe
    edited_df = st.data_editor(
        df_display[display_cols],
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        key="student_editor"
    )
    
    # Get selected rows
    selected_rows = edited_df[edited_df["Select"]]
    
    if not selected_rows.empty:
        st.write(f"**Selected Students:** {len(selected_rows)}")
        
        # Assignment section
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Mentor selection dropdown
            mentor_options = {mentor["Name"]: mentor["Name"] for _, mentor in available_mentors.iterrows()}
            selected_mentor = st.selectbox(
                "Select Mentor to Assign:",
                options=list(mentor_options.keys()),
                key="mentor_selection"
            )
        
        with col2:
            st.write("")  # Spacing
            st.write("")  # Spacing
            
            # Action buttons
            col_assign, col_unassign = st.columns(2)
            
            with col_assign:
                if st.button("✅ Assign Mentor", type="primary", use_container_width=True):
                    assign_mentor(selected_rows, selected_mentor, gs_client)
            
            with col_unassign:
                if st.button("❌ Unassign Mentor", use_container_width=True):
                    unassign_mentor(selected_rows, gs_client)
    
    # Display mentor statistics
    display_mentor_statistics(df_students, available_mentors)

def assign_mentor(selected_students, mentor_name, gs_client):
    """Assign selected students to the specified mentor"""
    try:
        sh = gs_client.open_by_key(st.secrets["my_secrets"]["sheet_id"])
        ws = sh.worksheet("students")
        
        # Get all data from sheet
        data = ws.get_all_records()
        df_google = pd.DataFrame(data)
        
        # Update selected students
        updated_count = 0
        for _, row in selected_students.iterrows():
            student_id = row["Student ID"]
            df_google.loc[df_google["Student ID"] == student_id, "Mentor"] = mentor_name
            updated_count += 1
        
        # Push back to Google Sheets
        ws.update([df_google.columns.values.tolist()] + df_google.values.tolist())
        
        st.success(f"✅ Assigned {mentor_name} as mentor for {updated_count} students.")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Failed to assign mentor: {e}")

def unassign_mentor(selected_students, gs_client):
    """Unassign mentors from selected students"""
    try:
        sh = gs_client.open_by_key(st.secrets["my_secrets"]["sheet_id"])
        ws = sh.worksheet("students")
        
        # Get all data from sheet
        data = ws.get_all_records()
        df_google = pd.DataFrame(data)
        
        # Update selected students
        updated_count = 0
        for _, row in selected_students.iterrows():
            student_id = row["Student ID"]
            df_google.loc[df_google["Student ID"] == student_id, "Mentor"] = ""
            updated_count += 1
        
        # Push back to Google Sheets
        ws.update([df_google.columns.values.tolist()] + df_google.values.tolist())
        
        st.success(f"✅ Unassigned mentors for {updated_count} students.")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Failed to unassign mentor: {e}")

def display_mentor_statistics(df_students, available_mentors):
    """Display statistics about mentor assignments"""
    st.markdown("---")
    st.subheader("📊 Assignment Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Total students
    total_students = len(df_students)
    with col1:
        st.metric("Total Students", total_students)
    
    # Assigned students
    assigned_students = len(df_students[df_students["Mentor"].notna() & (df_students["Mentor"] != "")])
    with col2:
        st.metric("Assigned Students", assigned_students)
    
    # Unassigned students
    unassigned_students = total_students - assigned_students
    with col3:
        st.metric("Unassigned Students", unassigned_students)
    
    # Available mentors
    with col4:
        st.metric("Available Mentors", len(available_mentors))
    
    # Mentor workload chart
    if assigned_students > 0:
        st.markdown("### Mentor Workload Distribution")
        mentor_counts = df_students[df_students["Mentor"].notna() & (df_students["Mentor"] != "")]["Mentor"].value_counts()
        
        if not mentor_counts.empty:
            chart_data = pd.DataFrame({
                'Mentor': mentor_counts.index,
                'Students': mentor_counts.values
            })
            
            chart = st.bar_chart(chart_data.set_index('Mentor'))
        else:
            st.info("No mentor assignments found.")