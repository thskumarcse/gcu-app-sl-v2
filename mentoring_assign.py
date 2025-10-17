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
            # Add bulk upload section
            display_bulk_upload_section(available_mentors, gs_client)
            
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
        user_id = current_user.get("User ID", "")
        return df_students[df_students["Mentor User ID"] == user_id]
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
        user_id = current_user.get("User ID", "")
        # In this system, User ID is the same as Emp Id
        return df_users[df_users["Emp Id"] == user_id]
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
        # Get mentor names for display, but we'll work with user_ids
        mentor_names = df_students[df_students["Mentor"].notna() & (df_students["Mentor"] != "")]["Mentor"].unique()
        mentor_options = ["All", "Unassigned"] + sorted(mentor_names.astype(str).tolist())
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

def display_bulk_upload_section(available_mentors, gs_client):
    """Display bulk upload section with template download and file upload"""
    st.markdown("---")
    st.subheader("📤 Bulk Upload Assignment")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Download template button
        template_data = get_template_data()
        template_df = pd.DataFrame(template_data)
        csv = template_df.to_csv(index=False)
        
        st.download_button(
            label="📥 Download Template CSV",
            data=csv,
            file_name="mentor_assignment_template.csv",
            mime="text/csv",
            use_container_width=True,
            type="secondary"
        )
    
    with col2:
        # File uploader
        uploaded_file = st.file_uploader(
            "Upload CSV/Excel file",
            type=['csv', 'xlsx', 'xls'],
            help="Upload a file with columns: Student ID, Student Name, Mentor emp id, Mentor name"
        )
        
        if uploaded_file is not None:
            process_bulk_upload(uploaded_file, available_mentors, gs_client)

def get_template_data():
    """Get template data for bulk upload"""
    template_data = {
        'Student ID': ['STU001', 'STU002', 'STU003'],
        'Student Name': ['John Doe', 'Jane Smith', 'Bob Johnson'],
        'Mentor emp id': ['EMP001', 'EMP002', 'EMP001'],
        'Mentor name': ['Dr. Smith', 'Prof. Brown', 'Dr. Smith']
    }
    return template_data

def process_bulk_upload(uploaded_file, available_mentors, gs_client):
    """Process the uploaded file for bulk assignment"""
    try:
        # Read the file
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # Validate required columns
        required_columns = ['Student ID', 'Student Name', 'Mentor emp id', 'Mentor name']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"❌ Missing required columns: {missing_columns}")
            st.write("Required columns:", required_columns)
            return
        
        
        # Create mentor mapping (emp id to user id)
        mentor_mapping = {}
        
        # In this system, Emp Id is the same as User ID
        for _, mentor in available_mentors.iterrows():
            emp_id = str(mentor.get('Emp Id', '')).strip()
            name = str(mentor.get('Name', '')).strip()
            if emp_id:
                mentor_mapping[emp_id] = {'user_id': emp_id, 'name': name}
        
        # Get Google Sheets data once and trim Student IDs
        sh = gs_client.open_by_key(st.secrets["my_secrets"]["sheet_id"])
        ws = sh.worksheet("students")
        data = ws.get_all_records()
        df_google = pd.DataFrame(data)
        df_google["Student ID"] = df_google["Student ID"].astype(str).str.strip()
        
        # Process assignments
        success_count = 0
        error_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                student_id = str(row['Student ID']).strip()
                mentor_emp_id = str(row['Mentor emp id']).strip()
                
                
                # Find mentor user_id (try exact match first, then case-insensitive)
                mentor_found = False
                mentor_user_id = None
                mentor_name = None
                
                if mentor_emp_id in mentor_mapping:
                    mentor_found = True
                    mentor_user_id = mentor_mapping[mentor_emp_id]['user_id']
                    mentor_name = mentor_mapping[mentor_emp_id]['name']
                else:
                    # Try case-insensitive matching
                    for emp_id, mentor_info in mentor_mapping.items():
                        if emp_id.lower() == mentor_emp_id.lower():
                            mentor_found = True
                            mentor_user_id = mentor_info['user_id']
                            mentor_name = mentor_info['name']
                            break
                
                if mentor_found:
                    # Update the specific student
                    student_mask = df_google["Student ID"] == student_id
                    if student_mask.any():
                        df_google.loc[student_mask, "Mentor"] = mentor_name
                        df_google.loc[student_mask, "Mentor User ID"] = mentor_user_id
                        success_count += 1
                    else:
                        errors.append(f"Student ID '{student_id}' not found")
                        error_count += 1
                else:
                    errors.append(f"Mentor with emp id {mentor_emp_id} not found")
                    error_count += 1
                    
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
                error_count += 1
        
        # Update Google Sheets if there were successful assignments
        if success_count > 0:
            # Clean the dataframe before updating to handle NaN values
            df_google_clean = df_google.fillna("")  # Replace NaN with empty strings
            df_google_clean = df_google_clean.replace([float('inf'), float('-inf')], "")  # Replace inf values
            
            # Convert to list and ensure all values are JSON serializable
            data_to_update = [df_google_clean.columns.values.tolist()]
            for row in df_google_clean.values:
                clean_row = []
                for value in row:
                    if pd.isna(value) or value == float('inf') or value == float('-inf'):
                        clean_row.append("")
                    else:
                        clean_row.append(str(value))
                data_to_update.append(clean_row)
            
            ws.update(data_to_update)
        
        # Display results
        if success_count > 0:
            st.success(f"✅ Successfully assigned {success_count} students")
        
        if error_count > 0:
            st.warning(f"⚠️ {error_count} assignments failed")
            with st.expander("View Errors"):
                for error in errors:
                    st.write(f"• {error}")
        
        if success_count > 0:
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Error processing file: {e}")

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
            mentor_options = {}
            for _, mentor in available_mentors.iterrows():
                name = mentor.get("Name", "")
                emp_id = mentor.get("Emp Id", "")
                if name and emp_id:
                    mentor_options[name] = emp_id
            
            selected_mentor_name = st.selectbox(
                "Select Mentor to Assign:",
                options=list(mentor_options.keys()),
                key="mentor_selection"
            )
            selected_mentor_emp_id = mentor_options[selected_mentor_name] if selected_mentor_name else None
        
        with col2:
            st.write("")  # Spacing
            st.write("")  # Spacing
            
            # Action buttons
            col_assign, col_unassign = st.columns(2)
            
            with col_assign:
                if st.button("✅ Assign Mentor", type="primary", use_container_width=True):
                    assign_mentor(selected_rows, selected_mentor_emp_id, gs_client)
            
            with col_unassign:
                if st.button("❌ Unassign Mentor", use_container_width=True):
                    unassign_mentor(selected_rows, gs_client)
    
    # Display mentor statistics
    display_mentor_statistics(df_students, available_mentors)

def assign_mentor(selected_students, mentor_emp_id, gs_client):
    """Assign selected students to the specified mentor"""
    try:
        sh = gs_client.open_by_key(st.secrets["my_secrets"]["sheet_id"])
        ws = sh.worksheet("students")
        
        # Get all data from sheet
        data = ws.get_all_records()
        df_google = pd.DataFrame(data)
        
        # Get mentor info from users sheet
        users_ws = sh.worksheet("users")
        users_data = users_ws.get_all_records()
        df_users = pd.DataFrame(users_data)
        
        mentor_info = df_users[df_users["Emp Id"] == mentor_emp_id]
        if mentor_info.empty:
            st.error("❌ Mentor not found")
            return
        
        mentor_name = mentor_info.iloc[0]["Name"]
        mentor_user_id = mentor_info.iloc[0]["Emp Id"]  # Emp Id is the User ID in this system
        
        # Update selected students
        updated_count = 0
        for _, row in selected_students.iterrows():
            student_id = row["Student ID"]
            df_google.loc[df_google["Student ID"] == student_id, "Mentor"] = mentor_name
            df_google.loc[df_google["Student ID"] == student_id, "Mentor User ID"] = mentor_user_id
            updated_count += 1
        
        # Push back to Google Sheets - clean data first
        df_google_clean = df_google.fillna("")
        df_google_clean = df_google_clean.replace([float('inf'), float('-inf')], "")
        
        # Convert to list and ensure all values are JSON serializable
        data_to_update = [df_google_clean.columns.values.tolist()]
        for row in df_google_clean.values:
            clean_row = []
            for value in row:
                if pd.isna(value) or value == float('inf') or value == float('-inf'):
                    clean_row.append("")
                else:
                    clean_row.append(str(value))
            data_to_update.append(clean_row)
        
        ws.update(data_to_update)
        
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
            df_google.loc[df_google["Student ID"] == student_id, "Mentor User ID"] = ""
            updated_count += 1
        
        # Push back to Google Sheets - clean data first
        df_google_clean = df_google.fillna("")
        df_google_clean = df_google_clean.replace([float('inf'), float('-inf')], "")
        
        # Convert to list and ensure all values are JSON serializable
        data_to_update = [df_google_clean.columns.values.tolist()]
        for row in df_google_clean.values:
            clean_row = []
            for value in row:
                if pd.isna(value) or value == float('inf') or value == float('-inf'):
                    clean_row.append("")
                else:
                    clean_row.append(str(value))
            data_to_update.append(clean_row)
        
        ws.update(data_to_update)
        
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