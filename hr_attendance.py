import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
from utility_attendance import (
    stepwise_file_upload, split_file, merge_files, move_columns,detect_holidays_staffs,
    weighted_sum_and_replace_columns, calculate_leave_summary_with_wd_leaves,
    calculate_working_days, process_exempted_leaves, merge_files_staffs, pad_month_in_columns
)
from utility import connect_gsheet, get_dataframe, preprocess_date

def fix_streamlit_layout():
    """Fix Streamlit layout issues"""
    # Page config is handled by main.py
    pass

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
    
# -----------------Holiday set up -------------------------
HOLIDAY_LIST = ['29-sep-2025','30-sep-2025','01-oct-2025','02-oct-2025','03-oct-2025',
                '06-oct-2025','18-oct-2025','20-oct-2025','21-oct-2025','23-sep-2025','05-nov-2025','25-dec-2025']

# User extra holidays
misc_holidays = ""  # jubin garg dead
misc_working_days = ""

def app():
    fix_streamlit_layout()
    set_compact_theme()
    
    st.header("HR Attendance")
    
    # File upload section
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("📁 Upload your attendance files - GIMT, GIPS, ADMIN, LEAVE")
        
        # Stepwise file upload
        labels = ["GIMT", "GIPS", "ADMIN", "LEAVE"]
        dfs = stepwise_file_upload(labels, key_prefix="attendance")
        
        # Exempted file upload
        st.markdown("---")
        st.write("Enter the exempted file")
        exempted_file = st.file_uploader(
            "📋 Upload Exempted Leaves File",
            type=['xlsx', 'xls'],
            help="Exempted leaves data (required)",
            label_visibility="collapsed"
        )
        #st.caption("💡 Required exempted leaves data")
        
        if exempted_file is not None:
            try:
                df_exempted = process_exempted_leaves(exempted_file)
                #st.write(df)
            except Exception as e:
                st.error(f"Failed to read file: {e}")
        else:
            st.warning("Please upload a file to continue.")
        
    if len(dfs) == len(labels) and exempted_file is not None:
        st.success("✅ All files uploaded successfully!")
        #st.success("🚀 Attendance processing pipeline ready.")
        
        # User extra holidays
        # this need to be read from input
        # File upload section
        col1, col2 = st.columns(2)
        with col1:
            misc_holidays = st.text_input("Enter list of Misc. holidays - dd-mm-yyyy, dd-mm-yyyy")
                
        with col2:
            misc_working_days = st.text_input("Enter list of Misc. Working days - dd-mm-yyyy, dd-mm-yyyy")        
        #misc_holidays = ""  # jubin garg dead
        #misc_working_days = ""

        # Extend HOLIDAY_LIST (hr_attendance.py lines 148-152)
        misc_holidays_list = [h.strip() for h in misc_holidays.split(',') if h.strip()] if misc_holidays else []
        all_holidays = HOLIDAY_LIST.copy()
        if misc_holidays_list:
            all_holidays.extend(misc_holidays_list)

        # Process files
        try:
            # Step 1: Read files and merge (from notebook)
            df_gimt = dfs.get("GIMT")
            df_admin = dfs.get("ADMIN")
            df_gips = dfs.get("GIPS")
            df_leave_erp = dfs.get("LEAVE")
            
            # Split and merge files
            df_gimt_all, df_gimt_in, df_gimt_out = split_file(df_gimt)
            df_gips_all, df_gips_in, df_gips_out = split_file(df_gips)
            df_admin_all, df_admin_in, df_admin_out = split_file(df_admin)
                        
            # padding columns-names
            df_gimt_in = pad_month_in_columns(df_gimt_in, 'clock_in')
            df_gips_in = pad_month_in_columns(df_gips_in, 'clock_in')
            df_admin_in = pad_month_in_columns(df_admin_in, 'clock_in')
            df_gimt_all = pad_month_in_columns(df_gimt_all, 'clock_in')
            df_gips_all = pad_month_in_columns(df_gips_all, 'clock_in')
            df_admin_all = pad_month_in_columns(df_admin_all, 'clock_in')

            df_gimt_out = pad_month_in_columns(df_gimt_out, 'clock_out')
            df_gips_out = pad_month_in_columns(df_gips_out, 'clock_out')
            df_admin_out = pad_month_in_columns(df_admin_out, 'clock_out')
            df_gimt_all = pad_month_in_columns(df_gimt_all, 'clock_out')
            df_gips_all = pad_month_in_columns(df_gips_all, 'clock_out')
            df_admin_all = pad_month_in_columns(df_admin_all, 'clock_out')    
            
            
            # Detect holidays (hr_attendance.py lines 162-163)
            holidays = detect_holidays_staffs(df_gimt_in, year=2025, misc_holidays=all_holidays, misc_working_days=misc_working_days, verbose=False)
            #print(f"🗓️ Detected {len(holidays)} holidays")

            # Remove holidays (hr_attendance.py lines 167-168)
            cols_to_delete_in = holidays
            cols_to_delete_out = [c.replace('clock_in', 'clock_out') for c in holidays]

            df_gimt_in = df_gimt_in.drop(columns=cols_to_delete_in, axis=1, errors='ignore')
            df_gimt_out = df_gimt_out.drop(columns=cols_to_delete_out, axis=1, errors='ignore')
            df_gips_in = df_gips_in.drop(columns=cols_to_delete_in, axis=1, errors='ignore')
            df_gips_out = df_gips_out.drop(columns=cols_to_delete_out, axis=1, errors='ignore')
            df_admin_in = df_admin_in.drop(columns=cols_to_delete_in, axis=1, errors='ignore')
            df_admin_out = df_admin_out.drop(columns=cols_to_delete_out, axis=1, errors='ignore')
            
            # Calculate from actual data AFTER removing holidays (hr_attendance.py lines 228-229)
            final_working_days = df_gimt_in.columns
            working_days_list = calculate_working_days(df_gimt_in)
            no_working_days = len(df_gimt_in.columns) - 3
            st.write(f"✅ Working days: {no_working_days}")
 
            #print(f"✅ Removed holidays from all dataframes")
            st.write(f"Number of Employees: GIMT={df_gimt_in.shape[0]}, GIPS={df_gips_in.shape[0]}, ADMIN={df_admin_in.shape[0]}")
            
            # -------------- Merge Emp data
            ### Reading EMP data from ERP
            emp_df = pd.read_csv('./data/2015_10_27_employee_list.csv', skiprows=6, encoding='windows-1252')  
            emp_df = emp_df[['Employee ID','Name','Designation','Department']]
            emp_df = emp_df.rename(columns={'Employee ID':'Emp Id'})

            # Reset index to avoid issues
            emp_df.reset_index(drop=True, inplace=True)
            
            # Cell 5: Merge files using merge_files_staffs (like working notebook)
            #print("🔄 Merging files with merge_files_staffs...")
            # this is for report
            #df_fac_all_rp = pd.concat([df_gimt_all, df_gips_all], ignore_index=True)
            #df_admin_all_rp = df_admin_all.copy()
            df_fac_all_rp = pd.concat(
                [df_gimt_all.reset_index(drop=True), 
                df_gips_all.reset_index(drop=True)],
                ignore_index=True
            ).copy(deep=True)

            df_admin_all_rp = df_admin_all.reset_index(drop=True).copy(deep=True)

            # Use merge_files_staffs for all staff (hr_attendance.py lines 174-176)
            # Note: merge_files_staffs expects emp_df as DataFrame, not indexed
            df_gimt_merged = merge_files_staffs(df_gimt_in, df_gimt_out, emp_df.copy(), no_working_days, all_holidays, misc_working_days)
            df_gips_merged = merge_files_staffs(df_gips_in, df_gips_out, emp_df.copy(), no_working_days, all_holidays, misc_working_days)
            df_admin_merged = merge_files_staffs(df_admin_in, df_admin_out, emp_df.copy(), no_working_days, all_holidays, misc_working_days)

            # --------- dataframes for reports
            #df_fac_merged_rp = pd.concat([df_gimt_merged, df_gips_merged],ignore_index=True)
            #df_admin_merged_rp = df_admin_merged.copy()
            
            # 4. Consolidate and Merge with Employee Data
            df_fac_detail = pd.concat([df_gimt_all, df_gips_all], ignore_index=True)
            df_fac_conso = pd.concat([df_gimt_merged, df_gips_merged], ignore_index=True)

            df_admin_detail = df_admin_all.copy()
            df_admin_conso = df_admin_merged.copy()

            #print(f"✅ Faculty consolidated: {df_fac_conso.shape}")
            #print(f"✅ Admin consolidated: {df_admin_conso.shape}")

            # Rename columns for report format
            col_to_rename_staffs = {
                'AM_abs':'actual_AM_abs',
                'PM_abs':'actual_PM_abs',
                'days_abs':'actual_days_abs'
            }
            df_fac_conso.rename(columns=col_to_rename_staffs, inplace=True)
            df_admin_conso.rename(columns=col_to_rename_staffs, inplace=True)

            # ------- Selecting only the working days columns -----------
            common_cols_fac = [col for col in final_working_days if col in df_fac_detail.columns]
            common_cols_admin = [col for col in final_working_days if col in df_admin_detail.columns]

            df_fac_detail = df_fac_detail[common_cols_fac]
            df_admin_detail = df_admin_detail[common_cols_admin]

            # Merge with employee master data
            df_fac_conso_ID = pd.merge(df_fac_conso, emp_df, how='left', on='Emp Id', suffixes=('', '_from_emp'))
            df_admin_conso_ID = pd.merge(df_admin_conso, emp_df, how='left', on='Emp Id', suffixes=('', '_from_emp'))

            # Drop duplicate columns from emp_df
            cols_to_drop_emp = [col for col in df_fac_conso_ID.columns if col.endswith('_from_emp')]
            cols_to_drop_emp = [col for col in df_admin_conso_ID.columns if col.endswith('_from_emp')]

            df_fac_conso_ID = df_fac_conso_ID.drop(columns=cols_to_drop_emp, errors='ignore')
            df_admin_conso_ID = df_admin_conso_ID.drop(columns=cols_to_drop_emp, errors='ignore')
            
            # 5. Process exempted and leave data
            # Process exempted leaves
            df_exempted = process_exempted_leaves(exempted_file)
            df_exempted.rename(columns={'late_count':'exempt_late','half_day_count':'exempt_HD','full_day_count':'exempt_FD'}, inplace=True)
            if 'Name' in df_exempted.columns:
                df_exempted.drop('Name',axis=1,inplace=True)

            # Process LEAVE ERP data  
            if 'From Date' in df_leave_erp.columns:
                df_leave_erp['From Date'] = df_leave_erp['From Date'].apply(preprocess_date)
                df_leave_erp['From Date'] = pd.to_datetime(df_leave_erp['From Date'], errors='coerce')
            if 'To Date' in df_leave_erp.columns:
                df_leave_erp['To Date'] = df_leave_erp['To Date'].apply(preprocess_date)
                df_leave_erp['To Date'] = pd.to_datetime(df_leave_erp['To Date'], errors='coerce')

            #from utility_attendance import calculate_leave_summary_with_wd_leaves
            df_leave_erp_summary = calculate_leave_summary_with_wd_leaves(df_leave_erp, working_days_list)
            df_leave_erp_summary.fillna(0, inplace=True)

            df_leave_erp_summary['Approved leaves (ERP)'] = df_leave_erp_summary['Total WD leaves'] + df_leave_erp_summary['Casual Leave']

            cols_to_drop = [
                "Casual Leave", "Sick Leave", "Duty Leave", "Vacation Leave",
                "Maternity Leave", "Earned Leave", "Paternity Leave",'Total WD leaves'
            ]

            df_leave_erp_summary = df_leave_erp_summary.drop(columns=[c for c in cols_to_drop if c in df_leave_erp_summary.columns], errors="ignore")

            # ----------- 5.1 Merge EXEMPTED and Calculate Final Values
            # Merge EXEMPTED with actual data
            df_fac_actual = df_fac_conso_ID.copy()
            df_admin_actual = df_admin_conso_ID.copy()

            df_fac_actual_exempted = pd.merge(df_fac_actual, df_exempted, how='left', on=['Emp Id'])
            df_admin_actual_exempted = pd.merge(df_admin_actual, df_exempted, how='left', on=['Emp Id'])

            df_fac_actual_exempted.fillna(0, inplace=True)
            df_admin_actual_exempted.fillna(0, inplace=True)
            
            # ------------- #### 5.2 Calculate adjusted values (Half Days, Full Days, Late) -----------
            #from utility_attendance import weighted_sum_and_replace_columns
            for df in [df_fac_actual_exempted, df_admin_actual_exempted]:
                if not df.empty:
                    # Convert to numeric and fill NaN with 0
                    actual_am = pd.to_numeric(df['actual_AM_abs'], errors='coerce').fillna(0) if 'actual_AM_abs' in df.columns else 0
                    actual_pm = pd.to_numeric(df['actual_PM_abs'], errors='coerce').fillna(0) if 'actual_PM_abs' in df.columns else 0
                    actual_days_abs = pd.to_numeric(df['actual_days_abs'], errors='coerce').fillna(0) if 'actual_days_abs' in df.columns else 0
                    actual_late = pd.to_numeric(df['actual_No_of_late'], errors='coerce').fillna(0) if 'actual_No_of_late' in df.columns else 0
                    
                    exempt_hd = pd.to_numeric(df['exempt_HD'], errors='coerce').fillna(0) if 'exempt_HD' in df.columns else 0
                    exempt_fd = pd.to_numeric(df['exempt_FD'], errors='coerce').fillna(0) if 'exempt_FD' in df.columns else 0
                    exempt_late = pd.to_numeric(df['exempt_late'], errors='coerce').fillna(0) if 'exempt_late' in df.columns else 0
                    
                    # Calculate half days (AM_abs + PM_abs - exempt_HD)
                    df['Half Days'] = (actual_am + actual_pm - exempt_hd).clip(lower=0)
                    df['Full Days'] = (actual_days_abs - exempt_fd).clip(lower=0)
                    df['Late'] = (actual_late - exempt_late).clip(lower=0)

            #print("✅ EXEMPTED data merged")
            #print(f"   Faculty: {df_fac_actual_exempted.shape}")

            # --------------- #### 5.3 Merge LEAVE Data and Calculate Observed Leaves ---------------
            # Merge LEAVE with attendance
            df_fac_report = pd.merge(df_fac_actual_exempted, df_leave_erp_summary, how='left', on='Emp Id', suffixes=('','_leave'))
            df_admin_report = pd.merge(df_admin_actual_exempted, df_leave_erp_summary, how='left', on='Emp Id', suffixes=('','_leave'))

            df_fac_report.fillna(0, inplace=True)
            df_admin_report.fillna(0, inplace=True)

            # Calculate Observed Leaves (weighted sum: Half Days=0.5, Full Days=1.0)
            col_to_sum = ['Half Days', 'Full Days']
            df_fac_report = weighted_sum_and_replace_columns(df_fac_report, col_to_sum, 'Observed Leaves', [0.5, 1.0])
            df_admin_report = weighted_sum_and_replace_columns(df_admin_report, col_to_sum, 'Observed Leaves', [0.5, 1.0])

            # Calculate Unauthorized leaves = Absent - Total WD leaves
            if 'Absent' in df_fac_report.columns and 'Total WD leaves' in df_fac_report.columns:
                df_fac_report["Unauthorized leaves"] = (df_fac_report["Absent"] - df_fac_report["Total WD leaves"]).clip(lower=0)
            if 'Absent' in df_admin_report.columns and 'Total WD leaves' in df_admin_report.columns:
                df_admin_report["Unauthorized leaves"] = (df_admin_report["Absent"] - df_admin_report["Total WD leaves"]).clip(lower=0)

            # 
            # 'Unauthorized leaves' df_admin_report
            col_to_select = ['Emp Id', 'Name', 'Designation', 'Department','Working Days', 'Present', 'Absent','Late','Approved leaves (ERP)']
            df_fac_report_final = df_fac_report[col_to_select].copy()
            df_admin_report_final = df_admin_report[col_to_select].copy()

            df_fac_report_final["Unauthorised leaves"] = (df_fac_report_final["Absent"] - df_fac_report_final["Approved leaves (ERP)"]).clip(lower=0)
            df_admin_report_final["Unauthorised leaves"] = (df_admin_report_final["Absent"] - df_admin_report_final["Approved leaves (ERP)"]).clip(lower=0)
            #df_fac_report_final.head() Employee ID

            df_erp_name = emp_df[['Emp Id','Name']].copy()
            #df_erp_name.rename(columns = {'Employee ID': 'Emp Id'}, inplace=True)
            
            # Delete 'Name' if it exist
            #if 'Name' in df_erp_name.columns:
            #    df_erp_name.drop(columns='Name', inplace=True)
            
            df_erp_name = df_erp_name.drop_duplicates()
            df_fac_report_final = df_fac_report_final.drop_duplicates()
            df_admin_report_final = df_admin_report_final.drop_duplicates()
            #df_erp_name.shape
            
            df_erp_name['Emp Id'].duplicated().sum(), df_fac_report_final['Emp Id'].duplicated().sum(),df_admin_report_final['Emp Id'].duplicated().sum()
            
            ### 6. The final report
            #### 6.1 Checking for missing Emp IDs
            missing_ids = df_fac_report_final.loc[df_fac_report_final['Name'].isna(), 'Emp Id']
            #print("Missing Emp Ids (not found in ERP list):")
            #print(missing_ids.tolist())            
            
            #### 6.2 Cleaning before merging
            # Normalise 'Emp Id' 
            for df in [df_fac_report_final, df_admin_report_final, df_erp_name]:
                df['Emp Id'] = df['Emp Id'].astype(str).str.strip().str.upper()
            
            # Delete 'Name' if it exist
            for df in [df_fac_report_final, df_admin_report_final]:
                if 'Name' in df.columns:
                    df.drop(columns='Name', inplace=True)
            
            df_fac_report_final = df_fac_report_final.merge(df_erp_name, how='left', on='Emp Id')
            df_admin_report_final = df_admin_report_final.merge(df_erp_name, how='left', on='Emp Id')
            
            #### 6.3 Identify missing matches after both merges
            #missing_fac = df_fac_report_final.loc[df_fac_report_final['Name'].isna(), 'Emp Id']
            #missing_admin = df_admin_report_final.loc[df_admin_report_final['Name'].isna(), 'Emp Id']

            #print("Missing in Faculty:", len(missing_fac))
            #print("Missing in Admin:", len(missing_admin))
            
            corrected_order = ['Emp Id', 'Name', 'Designation', 'Department', 'Working Days', 'Present',
                'Absent', 'Late', 'Approved leaves (ERP)', 'Unauthorised leaves' ]
            
            corrected_order = [col for col in corrected_order if col in df_fac_report_final.columns]
 
            df_fac_report_final = df_fac_report_final[corrected_order]
            df_admin_report_final = df_admin_report_final[corrected_order]
        
            # Show reports
            st.success("📊 Reports generated successfully!")
            
            # Faculty Report
            st.subheader("👨‍🏫 Faculty Report")
            st.dataframe(df_fac_report_final)
            
            # Admin Report
            st.subheader("👨‍💼 Admin Report")
            st.dataframe(df_admin_report_final)
            
            # Download buttons
            col1, col2 = st.columns(2)
            
            with col1:
                # Faculty Excel 
                faculty_buffer = io.BytesIO()
                with pd.ExcelWriter(faculty_buffer, engine='openpyxl') as writer:
                    df_fac_all_rp.to_excel(writer, sheet_name='Bio details', index=False)
                    df_fac_conso.to_excel(writer, sheet_name='Bio Consolidated', index=False)
                    df_exempted.to_excel(writer, sheet_name='Exempted', index=False)
                    df_leave_erp_summary.to_excel(writer, sheet_name='ERP Leave', index=False)
                    df_fac_report_final.to_excel(writer, sheet_name='Report', index=False)
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
                    df_admin_all_rp.to_excel(writer, sheet_name='Bio details', index=False)
                    df_admin_conso.to_excel(writer, sheet_name='Bio Consolidated', index=False)
                    df_exempted.to_excel(writer, sheet_name='Exempted', index=False)
                    df_leave_erp_summary.to_excel(writer, sheet_name='ERP Leave', index=False)
                    df_admin_report_final.to_excel(writer, sheet_name='Report', index=False)
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