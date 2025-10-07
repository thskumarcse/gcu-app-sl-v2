import streamlit as st
import pandas as pd
import gspread
from utility import connect_gsheet, get_dataframe, gs_client, fix_streamlit_layout, set_compact_theme
from datetime import datetime, date, timedelta
import io
import os
import tempfile
import zipfile

# ReportLab imports for PDF generation
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Table, TableStyle,
    Spacer, Paragraph, SimpleDocTemplate, NextPageTemplate, 
    KeepInFrame, KeepTogether, PageBreak, Flowable
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.utils import ImageReader
from xml.sax.saxutils import escape

def app():
    fix_streamlit_layout(padding_top="0.6rem")
    set_compact_theme()
    
    st.header("📊 Mentoring Reports & Analytics")
    
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
        
        # Fetch data from all relevant sheets
        df_students = get_dataframe(gs_client, st.secrets["my_secrets"]["sheet_id"], "students")
        df_mentoring = get_dataframe(gs_client, st.secrets["my_secrets"]["sheet_id"], "mentoring")
        df_attendance = get_dataframe(gs_client, st.secrets["my_secrets"]["sheet_id"], "attendance")
        df_assessment = get_dataframe(gs_client, st.secrets["my_secrets"]["sheet_id"], "assessment")
        
        # Store in session state for other functions
        st.session_state["df_students"] = df_students
        st.session_state["df_mentoring"] = df_mentoring
        st.session_state["df_attendance"] = df_attendance
        st.session_state["df_assessment"] = df_assessment
        
        # Debug: Show available columns (remove this in production)
        if st.checkbox("🔍 Debug: Show Data Columns", key="debug_columns"):
            st.write("**Available Data Columns:**")
            st.write("Mentoring columns:", list(df_mentoring.columns) if not df_mentoring.empty else "No data")
            st.write("Attendance columns:", list(df_attendance.columns) if not df_attendance.empty else "No data")
            st.write("Assessment columns:", list(df_assessment.columns) if not df_assessment.empty else "No data")
        
        # Filter data based on user role
        filtered_students = filter_students_by_role(df_students, current_user, user_role)
        
        if filtered_students.empty:
            st.warning("⚠️ No students available for reporting based on your role.")
            return
        
        # Display report options
        display_report_options(filtered_students, df_mentoring, df_attendance, df_assessment, current_user, user_role)
        
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
        # Mentor can see students assigned to them
        user_name = current_user.get("Name", "")
        return df_students[df_students["Mentor"] == user_name]
    else:
        return pd.DataFrame()

def display_filters(available_students, current_user, user_role):
    """Display filter options based on user role"""
    st.markdown("---")
    st.subheader("🔍 Filter Students")
    
    # Determine which filters to show based on role
    show_department = user_role in ["admin", "mentor_admin"]
    show_semester = user_role in ["admin", "mentor_admin", "coordinator"]
    show_program = True  # All roles can filter by program
    
    col1, col2, col3 = st.columns(3)
    filters = {}
    
    with col1:
        if show_department:
            department_options = ["All"] + sorted(available_students["Department"].astype(str).unique().tolist())
            filters["department_filter"] = st.selectbox("Department", department_options, key="dept_filter")
        else:
            filters["department_filter"] = "All"
    
    with col2:
        if show_semester:
            semester_options = ["All"] + sorted(available_students["Semester"].astype(str).unique().tolist())
            filters["semester_filter"] = st.selectbox("Semester", semester_options, key="sem_filter")
        else:
            filters["semester_filter"] = "All"
    
    with col3:
        program_options = ["All"] + sorted(available_students["Program"].astype(str).unique().tolist())
        filters["program_filter"] = st.selectbox("Program", program_options, key="prog_filter")
    
    return filters

def apply_filters(available_students, filters):
    """Apply selected filters to the dataframe"""
    filtered_df = available_students.copy()
    
    if filters["department_filter"] != "All":
        filtered_df = filtered_df[filtered_df["Department"] == filters["department_filter"]]
    
    if filters["semester_filter"] != "All":
        filtered_df = filtered_df[filtered_df["Semester"] == filters["semester_filter"]]
    
    if filters["program_filter"] != "All":
        filtered_df = filtered_df[filtered_df["Program"] == filters["program_filter"]]
    
    return filtered_df

def display_report_options(filtered_students, df_mentoring, df_attendance, df_assessment, current_user, user_role):
    """Display report options with filters similar to mentoring_assign"""
    
    # Display filters and get selected values
    filters = display_filters(filtered_students, current_user, user_role)
    
    # Apply filters
    filtered_students_final = apply_filters(filtered_students, filters)
    
    st.write(f"**Total Students Available:** {len(filtered_students_final)}")
    
    if filtered_students_final.empty:
        st.warning("No students match your filter criteria.")
        return
    
    # Student selection with ALL option
    st.markdown("---")
    st.subheader("📋 Select Student for Report")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Student selection dropdown with ALL option
        student_options = {"ALL": "ALL"}
        for _, student in filtered_students_final.iterrows():
            student_id = student.get("Student ID", "")
            student_name = student.get("Student Name", "")
            display_name = f"{student_name} ({student_id})"
            student_options[display_name] = student_id
        
        # Sort options alphabetically
        sorted_options = sorted(student_options.keys())
        selected_student_display = st.selectbox(
            "Select Student",
            options=sorted_options,
            key="student_selection"
        )
        selected_student_id = student_options[selected_student_display]
    
    with col2:
        # Date range selection
        date_range = st.selectbox(
            "Date Range",
            ["Last 30 days", "Last 3 months", "Last 6 months", "All time"],
            key="date_range"
        )
    
        # Generate report based on selection
        if st.button("📊 Generate Report", type="primary"):
            if selected_student_id == "ALL":
                generate_all_students_report(filtered_students_final, st.session_state["df_mentoring"], st.session_state["df_attendance"], st.session_state["df_assessment"], date_range)
            else:
                generate_individual_student_report(selected_student_id, st.session_state["df_students"], st.session_state["df_mentoring"], st.session_state["df_attendance"], st.session_state["df_assessment"], date_range)

def generate_all_students_report(filtered_students, df_mentoring, df_attendance, df_assessment, date_range):
    """Generate reports for all students and create ZIP file"""
    st.markdown("---")
    st.subheader("📊 Generating Reports for All Students")
    
    # Filter data by date range
    filtered_mentoring = filter_by_date_range(df_mentoring, date_range, "Date")
    filtered_attendance = filter_by_date_range(df_attendance, date_range, "Date")
    filtered_assessment = filter_by_date_range(df_assessment, date_range, "Date")
    
    # Create temporary directory for PDFs
    with tempfile.TemporaryDirectory() as temp_dir:
        generated_pdfs = []
        
        # Progress bar
        progress_bar = st.progress(0)
        total_students = len(filtered_students)
        
        # Generate PDF for each student
        for i, (_, student) in enumerate(filtered_students.iterrows()):
            student_id = student.get("Student ID", "")
            student_name = student.get("Student Name", "")
            
            st.write(f"📄 Generating report for: {student_name} ({student_id})")
            
            pdf_buffer = create_student_pdf_report(student_id, student, filtered_mentoring, filtered_attendance, filtered_assessment)
            
            if pdf_buffer is not None:
                # Save PDF to temporary file
                safe_student_name = "".join(c for c in student_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                pdf_filename = f"{safe_student_name}_{student_id}_mentoring_report.pdf"
                pdf_path = os.path.join(temp_dir, pdf_filename)
                
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_buffer.getvalue())
                
                generated_pdfs.append((pdf_path, pdf_filename))
                st.success(f"✅ Generated: {pdf_filename}")
            else:
                st.error(f"❌ Failed to generate PDF for: {student_name} ({student_id})")
            
            # Update progress
            progress_bar.progress((i + 1) / total_students)
        
        # Create ZIP file
        if generated_pdfs:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for pdf_path, pdf_filename in generated_pdfs:
                    zip_file.write(pdf_path, pdf_filename)
            
            zip_buffer.seek(0)
            
            # Download button
            st.success(f"✅ Generated {len(generated_pdfs)} individual student reports!")
            st.download_button(
                label="📥 Download All Student Reports (ZIP)",
                data=zip_buffer.getvalue(),
                file_name=f'all_students_mentoring_reports_{date_range.replace(" ", "_")}.zip',
                mime="application/zip"
            )
            
            # Show list of generated files
            st.info("📋 Generated PDF files:")
            for _, pdf_filename in generated_pdfs:
                st.write(f"• {pdf_filename}")
        else:
            st.error("❌ No PDFs were generated successfully.")

def generate_individual_student_report(student_id, df_students, df_mentoring, df_attendance, df_assessment, date_range):
    """Generate comprehensive individual student report with page display and PDF"""
    st.markdown("---")
    st.subheader(f"👤 Individual Student Report")
    
    # Get student info
    student_info = df_students[df_students["Student ID"] == student_id].iloc[0]
    
    # Filter data by date range
    filtered_mentoring = filter_by_date_range(df_mentoring, date_range, "Date")
    filtered_attendance = filter_by_date_range(df_attendance, date_range, "Date")
    filtered_assessment = filter_by_date_range(df_assessment, date_range, "Date")
    
    # Display student basic info
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Student Name", student_info.get("Student Name", "N/A"))
    with col2:
        st.metric("Student ID", student_info.get("Student ID", "N/A"))
    with col3:
        st.metric("Program", student_info.get("Program", "N/A"))
    with col4:
        st.metric("Semester", student_info.get("Semester", "N/A"))
    
    # Mentoring interactions
    # Check if "Student" column exists, otherwise use "Student ID"
    student_col = "Student" if "Student" in filtered_mentoring.columns else "Student ID"
    student_mentoring = filtered_mentoring[filtered_mentoring[student_col] == student_id]
    
    st.markdown("### 📝 Mentoring Interactions")
    if not student_mentoring.empty:
        # Display mentoring interactions table
        display_cols = ["Date", "Issue", "Interaction Type", "Remarks", "Mentor"]
        available_cols = [col for col in display_cols if col in student_mentoring.columns]
        
        st.dataframe(
            student_mentoring[available_cols],
            use_container_width=True,
            hide_index=True
        )
        
        # Mentoring statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Interactions", len(student_mentoring))
        with col2:
            if "Issue" in student_mentoring.columns:
                most_common_issue = student_mentoring["Issue"].mode().iloc[0] if not student_mentoring["Issue"].mode().empty else "N/A"
                st.metric("Most Common Issue", most_common_issue)
        with col3:
            if "Interaction Type" in student_mentoring.columns:
                most_common_type = student_mentoring["Interaction Type"].mode().iloc[0] if not student_mentoring["Interaction Type"].mode().empty else "N/A"
                st.metric("Most Common Type", most_common_type)
    else:
        st.info("No mentoring interactions found for this student in the selected period.")
    
    # Attendance data
    student_attendance = filtered_attendance[filtered_attendance["Student ID"] == student_id]
    
    st.markdown("### 📅 Attendance Overview")
    if not student_attendance.empty:
        # Calculate attendance statistics
        total_classes = len(student_attendance)
        # Calculate present classes safely
        if not student_attendance.empty and "Status" in student_attendance.columns:
            try:
                present_classes = len(student_attendance[student_attendance["Status"].astype(str).str.lower() == "present"])
            except Exception:
                present_classes = 0
        else:
            present_classes = 0
        attendance_percentage = (present_classes / total_classes * 100) if total_classes > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Classes", total_classes)
        with col2:
            st.metric("Present Classes", present_classes)
        with col3:
            st.metric("Attendance %", f"{attendance_percentage:.1f}%")
        
        # Display attendance table
        display_cols = ["Date", "Status", "Subject"]
        available_cols = [col for col in display_cols if col in student_attendance.columns]
        
        if available_cols:
            st.dataframe(
                student_attendance[available_cols],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("No attendance data found for this student in the selected period.")
    
    # Assessment data
    student_assessment = filtered_assessment[filtered_assessment["Student ID"] == student_id]
    
    st.markdown("### 📊 Assessment Performance")
    if not student_assessment.empty:
        # Calculate assessment statistics
        if "Marks" in student_assessment.columns:
            avg_marks = student_assessment["Marks"].mean()
            max_marks = student_assessment["Marks"].max()
            min_marks = student_assessment["Marks"].min()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Average Marks", f"{avg_marks:.1f}")
            with col2:
                st.metric("Highest Marks", f"{max_marks:.1f}")
            with col3:
                st.metric("Lowest Marks", f"{min_marks:.1f}")
        
        # Display assessment table
        display_cols = ["Date", "Subject", "Marks", "Grade"]
        available_cols = [col for col in display_cols if col in student_assessment.columns]
        
        if available_cols:
            st.dataframe(
                student_assessment[available_cols],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("No assessment data found for this student in the selected period.")
    
    # Generate PDF report
    st.markdown("---")
    st.subheader("📄 Generate PDF Report")
    
    pdf_buffer = create_student_pdf_report(student_id, student_info, filtered_mentoring, filtered_attendance, filtered_assessment)
    
    if pdf_buffer is not None:
        # Download button
        student_name = student_info.get("Student Name", "Unknown")
        st.success("✅ Student mentoring report generated successfully!")
        st.download_button(
            label="📥 Download Student Report",
            data=pdf_buffer.getvalue(),
            file_name=f'{student_name}_{student_id}_mentoring_report.pdf',
            mime="application/pdf"
        )
    else:
        st.error("❌ Failed to generate PDF report.")

def generate_mentor_performance_report(df_mentoring, df_students, current_user, user_role, date_range):
    """Generate mentor performance report"""
    st.markdown("---")
    st.subheader("👨‍🏫 Mentor Performance Report")
    
    # Filter mentoring data by date range
    filtered_mentoring = filter_by_date_range(df_mentoring, date_range, "Date")
    
    if filtered_mentoring.empty:
        st.info("No mentoring data found for the selected period.")
        return
    
    # Get mentor data based on role
    if user_role in ["admin", "mentor_admin"]:
        # Show all mentors
        mentor_data = filtered_mentoring.groupby("Mentor").agg({
            "Student": "nunique",
            "Date": "count"
        }).rename(columns={"Student": "Unique Students", "Date": "Total Interactions"})
    else:
        # Show only current mentor
        mentor_name = current_user.get("Name", "")
        mentor_data = filtered_mentoring[filtered_mentoring["Mentor"] == mentor_name].groupby("Mentor").agg({
            "Student": "nunique",
            "Date": "count"
        }).rename(columns={"Student": "Unique Students", "Date": "Total Interactions"})
    
    if mentor_data.empty:
        st.info("No mentoring data found for your role in the selected period.")
        return
    
    # Display mentor performance metrics
    st.markdown("### 📊 Performance Metrics")
    
    for mentor, data in mentor_data.iterrows():
        st.markdown(f"#### {mentor}")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Interactions", data["Total Interactions"])
        with col2:
            st.metric("Unique Students", data["Unique Students"])
        with col3:
            avg_interactions = data["Total Interactions"] / data["Unique Students"] if data["Unique Students"] > 0 else 0
            st.metric("Avg Interactions/Student", f"{avg_interactions:.1f}")
    
    # Issue analysis
    st.markdown("### 🔍 Issue Analysis")
    if "Issue" in filtered_mentoring.columns:
        issue_counts = filtered_mentoring["Issue"].value_counts()
        
        st.markdown("#### Distribution of Issues")
        issue_df = pd.DataFrame({
            "Issue": issue_counts.index,
            "Count": issue_counts.values
        })
        st.bar_chart(issue_df.set_index("Issue"))
    
    # Interaction type analysis
    st.markdown("### 📞 Interaction Type Analysis")
    if "Interaction Type" in filtered_mentoring.columns:
        interaction_counts = filtered_mentoring["Interaction Type"].value_counts()
        
        st.markdown("#### Interaction Types Distribution")
        interaction_df = pd.DataFrame({
            "Interaction Type": interaction_counts.index,
            "Count": interaction_counts.values
        })
        st.bar_chart(interaction_df.set_index("Interaction Type"))

def generate_overview_report(df_mentoring, df_students, df_attendance, df_assessment, current_user, user_role, date_range):
    """Generate department/semester overview report"""
    st.markdown("---")
    st.subheader("🏫 Department/Semester Overview")
    
    # Filter data by date range
    filtered_mentoring = filter_by_date_range(df_mentoring, date_range, "Date")
    filtered_attendance = filter_by_date_range(df_attendance, date_range, "Date")
    filtered_assessment = filter_by_date_range(df_assessment, date_range, "Date")
    
    # Get scope based on role
    if user_role in ["admin", "mentor_admin"]:
        scope_students = df_students
        scope_name = "All Students"
    elif user_role == "hod":
        user_dept = current_user.get("Department", "")
        scope_students = df_students[df_students["Department"] == user_dept]
        scope_name = f"{user_dept} Department"
    elif user_role == "coordinator":
        user_semester = current_user.get("Semester", "")
        scope_students = df_students[df_students["Semester"] == user_semester]
        scope_name = f"Semester {user_semester}"
    else:
        scope_students = pd.DataFrame()
        scope_name = "No Access"
    
    if scope_students.empty:
        st.info("No students available for overview based on your role.")
        return
    
    st.markdown(f"### 📊 {scope_name} Overview")
    
    # Basic statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Students", len(scope_students))
    
    with col2:
        mentored_students = len(scope_students[scope_students["Mentor"].notna() & (scope_students["Mentor"] != "")])
        st.metric("Mentored Students", mentored_students)
    
    with col3:
        if not filtered_mentoring.empty:
            total_interactions = len(filtered_mentoring)
            st.metric("Total Interactions", total_interactions)
        else:
            st.metric("Total Interactions", 0)
    
    with col4:
        if not filtered_attendance.empty and "Status" in filtered_attendance.columns:
            # Safely calculate average attendance percentage
            try:
                avg_attendance = filtered_attendance.groupby("Student ID")["Status"].apply(
                    lambda x: (x.astype(str).str.lower() == "present").sum() / len(x) * 100
                ).mean()
                st.metric("Avg Attendance %", f"{avg_attendance:.1f}%")
            except Exception:
                st.metric("Avg Attendance %", "N/A")
        else:
            st.metric("Avg Attendance %", "N/A")
    
    # Mentoring activity over time
    if not filtered_mentoring.empty and "Date" in filtered_mentoring.columns:
        st.markdown("### 📈 Mentoring Activity Over Time")
        daily_interactions = filtered_mentoring.groupby("Date").size().reset_index(name="Interactions")
        
        st.markdown("#### Daily Mentoring Interactions")
        st.line_chart(daily_interactions.set_index("Date"))
    
    # Department/Semester breakdown
    if user_role in ["admin", "mentor_admin"]:
        st.markdown("### 🏢 Department Breakdown")
        dept_stats = scope_students.groupby("Department").agg({
            "Student ID": "count",
            "Mentor": lambda x: (x.notna() & (x != "")).sum()
        }).rename(columns={"Student ID": "Total Students", "Mentor": "Mentored Students"})
        
        st.markdown("#### Students by Department")
        st.bar_chart(dept_stats["Total Students"])

def filter_by_date_range(df, date_range, date_column):
    """Filter dataframe by date range"""
    if df.empty or date_column not in df.columns:
        return df
    
    # Convert date column to datetime
    df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
    
    # Calculate date threshold
    today = pd.Timestamp.now().date()
    if date_range == "Last 30 days":
        threshold = today - timedelta(days=30)
    elif date_range == "Last 3 months":
        threshold = today - timedelta(days=90)
    elif date_range == "Last 6 months":
        threshold = today - timedelta(days=180)
    else:  # All time
        return df
    
    # Convert threshold to datetime for comparison
    threshold_dt = pd.Timestamp(threshold)
    
    # Filter by date
    return df[df[date_column] >= threshold_dt]

class NumberedCanvas(canvas.Canvas):
    """Custom canvas for page numbering."""
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """Add total page count to each page."""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_number(self, page_count):
        page = f"Page {self._pageNumber} of {page_count}"
        self.setFont("Helvetica", 9)
        width, height = A4
        self.drawCentredString(width / 2.0, 30, page)

def draw_header_with_logo(canvas, doc, student_info, logo_path):
    """Draw header with logo for mentoring report."""
    try:
        width, height = A4
        usable_width = width - doc.leftMargin - doc.rightMargin

        # Logo
        try:
            if logo_path and os.path.exists(logo_path):
                canvas.drawImage(logo_path, 50, height - 140, width=80, height=80, mask='auto')
            else:
                print(f"⚠️ Logo not found at {logo_path}")
        except Exception as e:
            print(f"❌ Error drawing logo: {e}")
            pass

        # Titles
        canvas.setFont("Times-Roman", 18)
        canvas.drawCentredString(width / 2, height - 60, "Girijananda Chowdhury University")
        canvas.setFont("Times-Roman", 14)
        canvas.drawCentredString(width / 2, height - 85, "MENTORING REPORT")
        canvas.setFont("Times-Roman", 12)
        canvas.drawCentredString(width / 2, height - 100, f"Student: {student_info.get('Student Name', 'N/A')}")
        canvas.drawCentredString(width / 2, height - 115, f"Student ID: {student_info.get('Student ID', 'N/A')}")
        
        # Student data table
        info_data = [
            [f"Program: {student_info.get('Program', 'N/A')}", f"Semester: {student_info.get('Semester', 'N/A')}"],
            [f"Department: {student_info.get('Department', 'N/A')}", f"Mentor: {student_info.get('Mentor', 'N/A')}"],
        ]
        info_table = Table(info_data, colWidths=[250, 250])
        info_table.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("ALIGN", (0,0), (0,-1), "LEFT"),
            ("ALIGN", (1,0), (1,-1), "LEFT"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ]))
        table_width, table_height = info_table.wrap(0, 0)
        info_table.drawOn(canvas, 50, height - 150 - table_height)
        
    except Exception as e:
        print(f"❌ Error in draw_header_with_logo: {e}")
        import traceback
        print(traceback.format_exc())
        raise

def draw_footer(canvas, doc, date_value, student_info):
    """Draw footer with date and signature."""
    width, height = A4
    canvas.setFont("Helvetica", 10)
    canvas.drawString(50, 60, f"Date : {date_value}")
    canvas.drawRightString(width - 55, 70, "Controller of Examinations")
    canvas.drawRightString(width - 40, 60, "Girijananda Chowdhury University")

def create_student_pdf_report(student_id, student_info, df_mentoring, df_attendance, df_assessment):
    """Create PDF report for a single student"""
    try:
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = BaseDocTemplate(buffer, pagesize=A4)
        doc.showFooter = True

        # Logo path
        logo_dir = os.path.join(os.getcwd(), "logo_dir")
        logo_path = os.path.join(logo_dir, "logo.png")
        if not os.path.exists(logo_path):
            logo_path = None

        # Styles
        styles = getSampleStyleSheet()
        
        # Table style matching exam_results
        table_style = TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("FONTNAME", (0,0), (-1,-1), "Times-Roman"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("FONTNAME", (0,0), (-1,0), "Times-Bold"),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("ALIGN", (1,1), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ])

        # Frames
        frame_first = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 160, id='first_frame')
        frame_later = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height + 50, id='later_frame')

        # Page templates
        first_page_template = PageTemplate(
            id='FirstPage',
            frames=[frame_first],
            onPage=lambda c, d: draw_header_with_logo(c, d, student_info, logo_path)
        )
        
        middle_page_template = PageTemplate(
            id='MiddlePages',
            frames=[frame_later]
        )
        
        last_page_template = PageTemplate(
            id='LastPage',
            frames=[frame_later],
            onPageEnd=lambda c, d: draw_footer(c, d, datetime.now().strftime("%d-%m-%Y"), student_info)
        )
        
        doc.addPageTemplates([first_page_template, middle_page_template, last_page_template])

        # Elements
        elements = []
        
        # Start with first page template
        elements.append(NextPageTemplate('FirstPage'))
        
        # Get student data
        # Check column names for mentoring data
        mentoring_student_col = "Student" if "Student" in df_mentoring.columns else "Student ID"
        student_mentoring = df_mentoring[df_mentoring[mentoring_student_col] == student_id] if not df_mentoring.empty else pd.DataFrame()
        student_attendance = df_attendance[df_attendance["Student ID"] == student_id] if not df_attendance.empty else pd.DataFrame()
        student_assessment = df_assessment[df_assessment["Student ID"] == student_id] if not df_assessment.empty else pd.DataFrame()
        
        # Add mentoring interactions table
        if not student_mentoring.empty:
            elements.extend(create_mentoring_table(student_mentoring, table_style))
            elements.append(Spacer(1, 20))
        
        # Add attendance table
        if not student_attendance.empty:
            elements.append(NextPageTemplate('MiddlePages'))
            elements.extend(create_attendance_table(student_attendance, table_style))
            elements.append(Spacer(1, 20))
        
        # Add assessment table
        if not student_assessment.empty:
            if student_mentoring.empty and student_attendance.empty:
                pass  # Keep first page template
            else:
                elements.append(NextPageTemplate('LastPage'))
            elements.extend(create_assessment_table(student_assessment, table_style))
            elements.append(Spacer(1, 20))

        # Build PDF
        try:
            doc.build(elements)
            buffer.seek(0)
            return buffer
        except Exception as e:
            st.error(f"❌ PDF build failed: {e}")
            return None
            
    except Exception as e:
        st.error(f"❌ Error creating PDF: {e}")
        return None

def create_mentoring_table(df_mentoring, table_style):
    """Create mentoring interactions table"""
    # Prepare data
    data = [["Date", "Issue", "Interaction Type", "Remarks", "Mentor"]]
    
    for _, row in df_mentoring.iterrows():
        data.append([
            str(row.get('Date', '')),
            str(row.get('Issue', '')),
            str(row.get('Interaction Type', '')),
            str(row.get('Remarks', '')),
            str(row.get('Mentor', ''))
        ])
    
    # Create table
    table = Table(data, colWidths=[80, 100, 80, 150, 100])
    table.setStyle(table_style)
    
    # Label style
    label_style = ParagraphStyle(
        'Label',
        parent=getSampleStyleSheet()['Normal'],
        fontSize=10,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    
    label = "Mentoring Interactions:"
    return [KeepTogether([Paragraph(label, label_style), Spacer(1, 6), table])]

def create_attendance_table(df_attendance, table_style):
    """Create attendance table"""
    # Prepare data
    data = [["Date", "Status", "Subject"]]
    
    for _, row in df_attendance.iterrows():
        data.append([
            str(row.get('Date', '')),
            str(row.get('Status', '')),
            str(row.get('Subject', ''))
        ])
    
    # Create table
    table = Table(data, colWidths=[100, 80, 200])
    table.setStyle(table_style)
    
    # Label style
    label_style = ParagraphStyle(
        'Label',
        parent=getSampleStyleSheet()['Normal'],
        fontSize=10,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    
    label = "Attendance Record:"
    return [KeepTogether([Paragraph(label, label_style), Spacer(1, 6), table])]

def create_assessment_table(df_assessment, table_style):
    """Create assessment table"""
    # Prepare data
    data = [["Date", "Subject", "Marks", "Grade"]]
    
    for _, row in df_assessment.iterrows():
        data.append([
            str(row.get('Date', '')),
            str(row.get('Subject', '')),
            str(row.get('Marks', '')),
            str(row.get('Grade', ''))
        ])
    
    # Create table
    table = Table(data, colWidths=[100, 150, 80, 80])
    table.setStyle(table_style)
    
    # Label style
    label_style = ParagraphStyle(
        'Label',
        parent=getSampleStyleSheet()['Normal'],
        fontSize=10,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    
    label = "Assessment Performance:"
    return [KeepTogether([Paragraph(label, label_style), Spacer(1, 6), table])]