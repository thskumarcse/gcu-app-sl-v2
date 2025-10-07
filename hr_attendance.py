import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
from utility_attendance import (
    stepwise_file_upload, split_file, merge_files, move_columns,
    weighted_sum_and_replace_columns, calculate_leave_summary_with_wd_leaves,
    calculate_working_days, process_exempted_leaves
)
from utility import connect_gsheet, get_dataframe, preprocess_date

def fix_streamlit_layout():
    """Fix Streamlit layout issues"""
    st.set_page_config(
        page_title="HR Attendance System",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def set_compact_theme():
    """Set compact theme for better UI"""
    st.markdown("""
    <style>
    .main > div {
        padding-top: 2rem;
    }
    .stSelectbox > div > div {
        background-color: #f0f2f6;
    }
    </style>
    """, unsafe_allow_html=True)

def app():
    fix_streamlit_layout()
    set_compact_theme()
    
    st.header("HR Attendance")
    
    # File upload section
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("📁 Upload your attendance files step by step")
        
        # Working days input
        no_working_days = st.number_input(
            "Number of Working Days",
            min_value=1,
            max_value=31,
            value=20,
            help="Enter the number of working days for this month"
        )
        
        # Stepwise file upload
        labels = ["GIMT", "GIPS", "ADMIN", "LEAVE"]
        dfs = stepwise_file_upload(labels, key_prefix="attendance")
        
        # Exempted file upload
        st.markdown("---")
        exempted_file = st.file_uploader(
            "📋 Upload Exempted Leaves File",
            type=['xlsx', 'xls'],
            help="Exempted leaves data (required)",
            label_visibility="collapsed"
        )
        st.caption("💡 Required exempted leaves data")

    if len(dfs) == len(labels) and exempted_file is not None:
        st.success("✅ All files uploaded successfully!")
        st.success("🚀 Attendance processing pipeline ready.")

        # Process files
        try:
            # Step 1: Read files and merge (from notebook)
            df_gimt = dfs.get("GIMT")
            df_admin = dfs.get("ADMIN")
            df_gips = dfs.get("GIPS")
            df_leave_erp = dfs.get("LEAVE")
            
            # Split and merge files
            df_gimt_all, df_gimt_in, df_gimt_out = split_file(df_gimt)
            df_gimt_merged = merge_files(df_gimt_in, df_gimt_out, no_working_days)

            df_gips_all, df_gips_in, df_gips_out = split_file(df_gips)
            df_gips_merged = merge_files(df_gips_in, df_gips_out, no_working_days)

            df_admin_all, df_admin_in, df_admin_out = split_file(df_admin)
            df_admin_merged = merge_files(df_admin_in, df_admin_out, no_working_days)
            
            # Step 1.1: Faculty Detailed view (GIMT + GIPS only)
            df_fac_detail = pd.concat([df_gimt_all, df_gips_all], ignore_index=True)
            df_fac_conso = pd.concat([df_gimt_merged, df_gips_merged], ignore_index=True)
            df_fac_detail.fillna(0, inplace=True)
            df_fac_conso.fillna(0, inplace=True)
            
            df_admin_detail = df_admin_all.copy()
            df_admin_detail.fillna(0, inplace=True)  

            df_admin_conso = df_admin_merged.copy()
            df_admin_conso.fillna(0, inplace=True)
            
            # Rename columns
            col_to_rename = {'AM_abs':'actual_AM_abs','PM_abs':'actual_PM_abs','days_abs':'actual_days_abs','No_of_late':'actual_No_of_late'}
            df_fac_conso.rename(columns=col_to_rename, inplace=True)
            df_admin_conso.rename(columns=col_to_rename, inplace=True)
            
            # Reorder columns
            desired_order = [
                'Emp Id', 'Names',
                'Working Days', 'Present', 'Absent',
                'actual_AM_abs', 'actual_PM_abs', 'actual_days_abs',
                'half_day_flags', 'late_flags', 'early_flags',
                'actual_No_of_late'
            ]
            desired_order = [col for col in desired_order if col in df_fac_conso.columns]
            df_fac_conso = df_fac_conso[desired_order]
            df_admin_conso = df_admin_conso[desired_order]
            
            # Step 2: Merge with ERP employee data
            client = connect_gsheet()
            df_emp = get_dataframe(client, st.secrets["my_secrets"]["sheet_id"], "users")
            emp_df = df_emp[['Emp Id','Name','Designation','Department']]
            
            # Merge with employee data
            df_fac_detail_ID = pd.merge(df_fac_detail, emp_df, how='left', on='Emp Id')
            df_fac_detail_ID = move_columns(df_fac_detail_ID, {'Name':1,'Designation':2,'Department':3})
            df_fac_detail_ID = df_fac_detail_ID.drop('Names', axis=1)

            df_admin_detail_ID = pd.merge(df_admin_detail, emp_df, how='left', on='Emp Id')
            df_admin_detail_ID = move_columns(df_admin_detail_ID, {'Name':1,'Designation':2,'Department':3})
            df_admin_detail_ID = df_admin_detail_ID.drop('Names', axis=1)
            
            df_fac_conso_ID = pd.merge(df_fac_conso, emp_df, how='left', on='Emp Id')
            df_fac_conso_ID = move_columns(df_fac_conso_ID, {'Name':1,'Designation':2,'Department':3})
            df_fac_conso_ID = df_fac_conso_ID.drop('Names', axis=1)

            df_admin_conso_ID = pd.merge(df_admin_conso, emp_df, how='left', on='Emp Id')
            df_admin_conso_ID = move_columns(df_admin_conso_ID, {'Name':1,'Designation':2,'Department':3})
            df_admin_conso_ID = df_admin_conso_ID.drop('Names', axis=1)
            
            # Step 2.1: Handling half days
            df_fac_actual = df_fac_conso_ID.copy()
            df_admin_actual = df_admin_conso_ID.copy()

            # handling half days
            df_fac_actual['actual_half_day'] = df_fac_actual.apply(lambda x: len(x['actual_AM_abs'])+len(x['actual_PM_abs']),axis=1)
            df_admin_actual['actual_half_day'] = df_admin_actual.apply(lambda x: len(x['actual_AM_abs'])+len(x['actual_PM_abs']),axis=1)

            # handling full days
            df_fac_actual['actual_full_day'] = df_fac_actual.apply(lambda x: len(x['actual_days_abs']),axis=1)
            df_admin_actual['actual_full_day'] = df_admin_actual.apply(lambda x: len(x['actual_days_abs']),axis=1)
            
            col_to_select = ['Emp Id', 'Name', 'Designation', 'Department', 'Working Days', 'Present', 'Absent',
                           'actual_half_day', 'actual_full_day', 'actual_No_of_late']
            df_fac_actual = df_fac_actual[col_to_select]
            df_admin_actual = df_admin_actual[col_to_select]
            
            # Step 3: Exempted leave adjustments
            df_exempted = process_exempted_leaves(exempted_file)
            df_exempted.rename(columns={'late_count':'exempt_late','half_day_count':'exempt_HD','full_day_count':'exempt_FD'}, inplace=True)
            df_exempted.drop('Name',axis=1,inplace=True)
            
            # Merging Actual and Exempted Leaves
            df_fac_actual_exempted = pd.merge(df_fac_actual,df_exempted , how='left', on=['Emp Id'])
            df_fac_actual_exempted.fillna(0, inplace=True)

            df_admin_actual_exempted = pd.merge(df_admin_actual,df_exempted , how='left', on=['Emp Id'])
            df_admin_actual_exempted.fillna(0, inplace=True)
            
            # Calculating the balance Actual and Exempted Leaves
            df_fac_actual_exempted['Half Days'] = np.maximum(df_fac_actual_exempted['actual_half_day'] - df_fac_actual_exempted['exempt_HD'],0)
            df_fac_actual_exempted['Full Days'] = np.maximum(df_fac_actual_exempted['actual_full_day'] - df_fac_actual_exempted['exempt_FD'],0)
            df_fac_actual_exempted['Late'] = np.maximum(df_fac_actual_exempted['actual_No_of_late'] - df_fac_actual_exempted['exempt_late'],0)

            df_admin_actual_exempted['Half Days'] = np.maximum(df_admin_actual_exempted['actual_half_day'] - df_admin_actual_exempted['exempt_HD'],0)
            df_admin_actual_exempted['Full Days'] = np.maximum(df_admin_actual_exempted['actual_full_day'] - df_admin_actual_exempted['exempt_FD'],0)
            df_admin_actual_exempted['Late'] = np.maximum(df_admin_actual_exempted['actual_No_of_late'] - df_admin_actual_exempted['exempt_late'],0)
            
            col_to_select = ['Emp Id', 'Name', 'Designation', 'Department', 'Working Days', 'Present', 'Absent','Half Days','Full Days','Late']
            df_fac_attend_adjusted = df_fac_actual_exempted[col_to_select]
            df_admin_attend_adjusted = df_admin_actual_exempted[col_to_select]
            
            # Step 4: ERP Leave integration
            df_leave_erp["From Date"] = df_leave_erp["From Date"].apply(preprocess_date)
            df_leave_erp["To Date"] = df_leave_erp["To Date"].apply(preprocess_date)
            df_leave_erp["From Date"] = pd.to_datetime(df_leave_erp["From Date"], errors='coerce')
            df_leave_erp["To Date"] = pd.to_datetime(df_leave_erp["To Date"], errors='coerce')
            
            # corrected leaves
            df_leave_erp_summary = calculate_leave_summary_with_wd_leaves(df_leave_erp, calculate_working_days(df_gimt_in)) 
            df_leave_erp_summary.fillna(0, inplace=True)
            
            df_leave_erp_summary['Approved leaves (ERP)'] = df_leave_erp_summary['Total WD leaves'] + df_leave_erp_summary['Casual Leave']
            cols_to_drop = [
                "Casual Leave", "Sick Leave", "Duty Leave", "Vacation Leave",
                "Maternity Leave", "Earned Leave", "Paternity Leave",'Total WD leaves'
            ]
            df_leave_compact = df_leave_erp_summary.drop(columns=[c for c in cols_to_drop if c in df_leave_erp_summary.columns], errors="ignore")
            df_leave_compact = df_leave_compact[['Emp Id','Name','Approved leaves (ERP)']]
            df_leave_compact.drop(columns='Name', axis=1,inplace=True)

            df_fac_report = pd.merge(df_fac_actual_exempted, df_leave_compact , how='left', on=['Emp Id'])
            df_fac_report.fillna(0, inplace=True)

            df_admin_report = pd.merge(df_admin_actual_exempted, df_leave_compact , how='left', on=['Emp Id'])
            df_admin_report.fillna(0, inplace=True)
            
            col_to_sum = ['Half Days','Full Days']
            df_fac_report = weighted_sum_and_replace_columns(df_fac_report, col_to_sum, 'Observed Leaves', [0.5,1.0])
            df_admin_report = weighted_sum_and_replace_columns(df_admin_report, col_to_sum, 'Observed Leaves', [0.5,1.0])

            cols_to_delete = ['actual_half_day','actual_full_day','actual_No_of_late','exempt_late','exempt_HD', 'exempt_FD']
            df_fac_report = df_fac_report.drop(columns=[c for c in cols_to_delete if c in df_fac_report.columns], errors="ignore")
            df_admin_report = df_admin_report.drop(columns=[c for c in cols_to_delete if c in df_admin_report.columns], errors="ignore")
            
            df_fac_report["Unauthorised leaves"] = (df_fac_report["Absent"] - df_fac_report["Approved leaves (ERP)"]).clip(lower=0)
            df_admin_report["Unauthorised leaves"] = (df_admin_report["Absent"] - df_admin_report["Approved leaves (ERP)"]).clip(lower=0)
            
            # Step 5: Final Report
            df_fac_report_print = df_fac_report.copy()
            df_admin_report_print = df_admin_report.copy()

            df_fac_report_print = df_fac_report_print.drop(columns='Observed Leaves')
            df_admin_report_print = df_admin_report_print.drop(columns='Observed Leaves')

            df_fac_report_print = df_fac_report_print.rename(columns={'Approved leaves (ERP)': 'Approved leaves'})
            df_admin_report_print = df_admin_report_print.rename(columns={'Approved leaves (ERP)': 'Approved leaves'})
            
            # Show reports
            st.success("📊 Reports generated successfully!")
            
            # Faculty Report
            st.subheader("👨‍🏫 Faculty Report")
            st.dataframe(df_fac_report_print)
            
            # Admin Report
            st.subheader("👨‍💼 Admin Report")
            st.dataframe(df_admin_report_print)
            
            # Download buttons
            col1, col2 = st.columns(2)
            
            with col1:
                # Faculty Excel
                faculty_buffer = io.BytesIO()
                with pd.ExcelWriter(faculty_buffer, engine='openpyxl') as writer:
                    df_fac_detail_ID.to_excel(writer, sheet_name='Bio details', index=False)
                    df_fac_conso_ID.to_excel(writer, sheet_name='Bio Consolidated', index=False)
                    df_fac_actual_exempted.to_excel(writer, sheet_name='Exempted', index=False)
                    df_leave_erp_summary.to_excel(writer, sheet_name='ERP Leave', index=False)
                    df_fac_report_print.to_excel(writer, sheet_name='Report', index=False)
                faculty_buffer.seek(0)
                
                st.download_button(
                    label="📥 Download Faculty Report",
                    data=faculty_buffer.getvalue(),
                    file_name=f"faculty_attendance_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with col2:
                # Admin Excel
                admin_buffer = io.BytesIO()
                with pd.ExcelWriter(admin_buffer, engine='openpyxl') as writer:
                    df_admin_detail_ID.to_excel(writer, sheet_name='Bio details', index=False)
                    df_admin_conso_ID.to_excel(writer, sheet_name='Bio Consolidated', index=False)
                    df_admin_actual_exempted.to_excel(writer, sheet_name='Exempted', index=False)
                    df_leave_erp_summary.to_excel(writer, sheet_name='ERP Leave', index=False)
                    df_admin_report_print.to_excel(writer, sheet_name='Report', index=False)
                admin_buffer.seek(0)
                
                st.download_button(
                    label="📥 Download Admin Report",
                    data=admin_buffer.getvalue(),
                    file_name=f"admin_attendance_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
        except Exception as e:
            st.error(f"❌ Error in processing: {str(e)}")
            import traceback
            st.write(traceback.format_exc())
    
    else:
        st.info("📋 Please upload all required files to proceed")

if __name__ == "__main__":
    app()
