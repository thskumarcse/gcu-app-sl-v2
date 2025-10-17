import streamlit as st
import pandas as pd
import gspread
from utility import connect_gsheet, get_dataframe, gs_client, fix_streamlit_layout, set_compact_theme
from datetime import datetime, date

def app():
    fix_streamlit_layout(padding_top="0.6rem")
    set_compact_theme()
    
    # Add custom CSS for light green button
    st.markdown("""
    <style>
    .stButton > button[kind="secondary"] {
        background-color: #90EE90 !important;
        color: #000000 !important;
        border: 1px solid #90EE90 !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: #7FDD7F !important;
        border: 1px solid #7FDD7F !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.header("📝 Mentoring Data Input")
    
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
        
        # Fetch data from students sheet
        df_students = get_dataframe(gs_client, st.secrets["my_secrets"]["sheet_id"], "students")
        
        # Filter students to show only mentees of the logged-in person
        mentees = get_mentees_for_user(df_students, current_user, user_role)
        
        if mentees.empty:
            st.warning("⚠️ No mentees assigned to you.")
            return
        
        st.write(f"**Your Mentees:** {len(mentees)}")
        
        # Display the data input form
        display_mentoring_form(mentees, current_user, user_role, gs_client)
        
        # Display recent mentoring records
        display_recent_records(gs_client)
        
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return

def get_mentees_for_user(df_students, current_user, user_role):
    """Get mentees assigned to the logged-in user"""
    if user_role == "mentor":
        # For mentors, get students assigned to them by name
        user_name = current_user.get("Name", "")
        return df_students[df_students["Mentor"] == user_name]
    elif user_role in ["admin", "mentor_admin"]:
        # For admin/mentor_admin, they can see all students as their mentees
        return df_students
    elif user_role == "hod":
        # For HOD, get students from their department
        user_dept = current_user.get("Department", "")
        return df_students[df_students["Department"] == user_dept]
    elif user_role == "coordinator":
        # For coordinator, get students from their semester
        user_semester = current_user.get("Semester", "")
        return df_students[df_students["Semester"] == user_semester]
    else:
        return pd.DataFrame()

def display_mentoring_form(mentees, current_user, user_role, gs_client):
    """Display the mentoring data input form"""
    st.markdown("---")
    st.subheader("📋 Add New Mentoring Interaction")
    
    # Create form
    with st.form("mentoring_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Semester dropdown - first dropdown
            semester_options = ["All"] + sorted(mentees["Semester"].astype(str).unique().tolist())
            selected_semester = st.selectbox(
                "Semester",
                options=semester_options,
                help="Select the semester to filter students"
            )
            
            # Filter students based on selected semester
            if selected_semester == "All":
                filtered_mentees = mentees
            else:
                filtered_mentees = mentees[mentees["Semester"] == selected_semester]
            
            # Student dropdown - dependent on semester selection
            student_options = {}
            for _, student in filtered_mentees.iterrows():
                student_id = student.get("Student ID", "")
                student_name = student.get("Student Name", "")
                program = student.get("Program", "")
                semester = student.get("Semester", "")
                display_name = f"{student_name} ({student_id}) - {program} Sem {semester}"
                student_options[display_name] = student_id
            
            selected_student_display = st.selectbox(
                "Students",
                options=list(student_options.keys()),
                help="Choose your mentee for this mentoring interaction"
            )
            selected_student_id = student_options[selected_student_display]
            
            # Date selector
            interaction_date = st.date_input(
                "Date of Interaction",
                value=date.today(),
                help="Select the date when the interaction took place"
            )
        
        with col2:
            # Issue dropdown
            issue_options = [
                "Not coming to class",
                "Poor Attendance", 
                "Poor Marks",
                "Casual Meeting"
            ]
            selected_issue = st.selectbox(
                "Issue/Reason",
                options=issue_options,
                help="Select the main issue or reason for the interaction"
            )
            
            # Interaction Type dropdown
            interaction_type_options = [
                "Call",
                "Whatsapp",
                "Mail", 
                "Text",
                "Physical Meet"
            ]
            selected_interaction_type = st.selectbox(
                "Interaction Type",
                options=interaction_type_options,
                help="Select the method of interaction"
            )
        
        # Remarks text area
        remarks = st.text_area(
            "Remarks/Details",
            placeholder="Enter detailed remarks about the interaction...",
            help="Provide additional details about the mentoring interaction",
            height=100
        )
        
        # Submit button
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            submitted = st.form_submit_button("💾 Save Interaction", type="secondary", use_container_width=True)
        
        if submitted:
            # Validate form
            if not selected_student_id or not selected_issue or not selected_interaction_type:
                st.error("❌ Please fill in all required fields.")
                return
            
            # Save to Google Sheets
            save_mentoring_data(
                interaction_date,
                selected_student_id,
                selected_issue,
                selected_interaction_type,
                remarks,
                current_user,
                gs_client
            )

def save_mentoring_data(date_val, student_id, issue, interaction_type, remarks, current_user, gs_client):
    """Save mentoring data to Google Sheets"""
    try:
        # Get the mentoring worksheet
        sh = gs_client.open_by_key(st.secrets["my_secrets"]["sheet_id"])
        
        # Try to get existing worksheet, create if doesn't exist
        try:
            ws = sh.worksheet("mentoring")
        except gspread.exceptions.WorksheetNotFound:
            # Create the worksheet with headers
            ws = sh.add_worksheet(title="mentoring", rows=1000, cols=10)
            # Add headers
            headers = ["Date", "Student", "Issue", "Interaction Type", "Remarks", "Mentor", "Created By", "Created At"]
            ws.append_row(headers)
            st.info("📋 Created new 'mentoring' worksheet with headers.")
        
        # Prepare data row
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mentor_name = current_user.get("Name", "Unknown")
        created_by = current_user.get("Name", "Unknown")
        
        data_row = [
            date_val.strftime("%Y-%m-%d"),
            student_id,
            issue,
            interaction_type,
            remarks or "",
            mentor_name,
            created_by,
            current_time
        ]
        
        # Append the data
        ws.append_row(data_row)
        
        st.success(f"✅ Successfully saved mentoring interaction for Student ID: {student_id}")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Failed to save mentoring data: {e}")

def display_recent_records(gs_client):
    """Display recent mentoring records"""
    st.markdown("---")
    st.subheader("📊 Recent Mentoring Records")
    
    try:
        # Get mentoring data
        sh = gs_client.open_by_key(st.secrets["my_secrets"]["sheet_id"])
        
        try:
            ws = sh.worksheet("mentoring")
            data = ws.get_all_records()
            df_mentoring = pd.DataFrame(data)
            
            if df_mentoring.empty:
                st.info("📝 No mentoring records found. Start by adding your first interaction above.")
                return
            
            # Display recent records (last 10)
            recent_records = df_mentoring.tail(10)
            
            # Format the display
            display_cols = ["Date", "Student", "Issue", "Interaction Type", "Remarks", "Mentor"]
            if "Created At" in recent_records.columns:
                display_cols.append("Created At")
            
            # Show only available columns
            available_cols = [col for col in display_cols if col in recent_records.columns]
            
            st.dataframe(
                recent_records[available_cols],
                use_container_width=True,
                hide_index=True
            )
            
            # Show statistics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Interactions", len(df_mentoring))
            
            with col2:
                unique_students = df_mentoring["Student"].nunique() if "Student" in df_mentoring.columns else 0
                st.metric("Students Mentored", unique_students)
            
            with col3:
                if "Issue" in df_mentoring.columns:
                    most_common_issue = df_mentoring["Issue"].mode().iloc[0] if not df_mentoring["Issue"].mode().empty else "N/A"
                    st.metric("Most Common Issue", most_common_issue)
                else:
                    st.metric("Most Common Issue", "N/A")
            
            with col4:
                if "Interaction Type" in df_mentoring.columns:
                    most_common_type = df_mentoring["Interaction Type"].mode().iloc[0] if not df_mentoring["Interaction Type"].mode().empty else "N/A"
                    st.metric("Most Common Type", most_common_type)
                else:
                    st.metric("Most Common Type", "N/A")
                    
        except gspread.exceptions.WorksheetNotFound:
            st.info("📝 No mentoring records found. The 'mentoring' worksheet doesn't exist yet.")
            
    except Exception as e:
        st.error(f"❌ Error loading mentoring records: {e}")

def get_student_display_name(student):
    """Get formatted display name for student"""
    student_id = student.get("Student ID", "")
    student_name = student.get("Student Name", "")
    program = student.get("Program", "")
    semester = student.get("Semester", "")
    return f"{student_name} ({student_id}) - {program} Sem {semester}"