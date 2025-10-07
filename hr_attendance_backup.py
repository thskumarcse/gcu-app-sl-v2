import warnings
import io
import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
import altair as alt
from utility import connect_gsheet, get_dataframe, gs_client, preprocess_date, \
                    fix_streamlit_layout, set_compact_theme
from utility_attendance import stepwise_file_upload, split_file, merge_files, move_columns,\
                               weighted_sum_and_replace_columns, calculate_leave_summary_with_wd_leaves,\
                               calculate_working_days, merge_with_emp_data, process_exempted_leaves
#import xlsxwriter
from datetime import datetime, timedelta
warnings.filterwarnings("ignore")
from datetime import date

# --- GOOGLE SHEETS CONNECTION ---
# This function is cached to prevent re-running on every page reload.
#DEV_MODE = True
DEV_MODE = False   # toggle here for testing

# ----------------- helpers -----------------
def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names: strip spaces, title-case, unify underscores/spaces."""
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        #.str.replace("_", " ")
        #.str.title()
    )
    return df


# ----------------- main app -----------------
def app():
    fix_streamlit_layout(padding_top="0.6rem")
    set_compact_theme()
    
    # Display header immediately at the top
    st.header("HR Attendance")
    
    # ---- Initialize empty dataframes ----
    df_gimt_all = df_gips_all = df_admin_all = pd.DataFrame()
    df_gimt_in = df_gimt_out = df_gimt_merged = pd.DataFrame()
    df_gips_in = df_gips_out = df_gips_merged = pd.DataFrame()
    df_admin_in = df_admin_out = df_admin_merged = pd.DataFrame()
    df_fac_all = pd.DataFrame()
    df_exempted = None
    df_leave_erp = pd.DataFrame()
    no_working_days = 20  # default
    
    # ------- this is specailly for DEV_MODE=False -----------
    splits = {
        "gimt": {
            "all": df_gimt_all,
            "in": df_gimt_in,
            "out": df_gimt_out,
            "merged": df_gimt_merged,
        }
    }    
    if DEV_MODE:
        # --- Load sample local files ---
        # Development Mode - Loading sample data
        no_working_days = 20
        
        try:
            df_gimt = pd.read_excel('./data/GIMT_MonthlyAttendanceSummaryReport.xlsx')
            df_gimt_all, df_gimt_in, df_gimt_out = split_file(df_gimt)
            df_gimt_merged = merge_files(df_gimt_in, df_gimt_out, no_working_days)

            # Create splits dictionary for DEV_MODE
            splits = {
                "gimt": {
                    "all": df_gimt_all,
                    "in": df_gimt_in,
                    "out": df_gimt_out,
                    "merged": df_gimt_merged,
                }
            }
            
            # TODO: Load df_gips, df_admin in DEV_MODE if available
            df_fac_all = df_gimt_merged.copy()
            # DEV_MODE setup complete
            
        except Exception as e:
            st.error(f"❌ Failed to load sample data in DEV_MODE: {e}")
            st.write("Make sure the file './data/GIMT_MonthlyAttendanceSummaryReport.xlsx' exists")
            splits = {}

    else:
        # Main content area - compact layout
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.info("📋 Upload 4 files in order: GIMT, GIPS, ADMIN, LEAVE. Then upload EXEMPTED separately.")
        
        with col2:
            no_working_days = st.number_input("📅 Working Days", min_value=1, value=22, help="Enter number of working days")

        # Only 4 files for stepwise upload
        labels = ["GIMT", "GIPS", "ADMIN", "LEAVE"]
        dfs = stepwise_file_upload(labels, key_prefix="attendance")

        if len(dfs) == len(labels):
            st.success("✅ First 4 files uploaded successfully!")
            st.success("🚀 Attendance processing pipeline ready.")

            splits = {}
            
            # Initialize all variables to avoid scope issues
            df_fac_detail = pd.DataFrame()
            df_fac_conso = pd.DataFrame()
            df_admin_detail = pd.DataFrame()
            df_admin_conso = pd.DataFrame()
            df_fac_detail_ID = pd.DataFrame()
            df_admin_detail_ID = pd.DataFrame()
            df_fac_conso_ID = pd.DataFrame()
            df_admin_conso_ID = pd.DataFrame()
            df_fac_actual = pd.DataFrame()
            df_admin_actual = pd.DataFrame()
            df_fac_actual_exempted = pd.DataFrame()
            df_admin_actual_exempted = pd.DataFrame()
            df_fac_report = pd.DataFrame()
            df_admin_report = pd.DataFrame()
            emp_df = pd.DataFrame()
            
            # Initialize emp_df with actual data
            emp_cols_needed = [c for c in ['Emp Id', 'Name', 'Designation', 'Department'] if c in df_emp.columns]
            emp_df = df_emp[emp_cols_needed].copy()

            # Process GIMT, GIPS, ADMIN (split + merge)
            for label in ["GIMT", "GIPS", "ADMIN"]:
                df_raw = dfs.get(label)
                if df_raw is not None:
                    try:
                        df_all, df_in, df_out = split_file(df_raw)
                        df_merged = merge_files(df_in, df_out, no_working_days)

                        splits[label.lower()] = {
                            "all": df_all,
                            "in": df_in,
                            "out": df_out,
                            "merged": df_merged,
                        }

                        st.write(f"✔️ {label} Split + Merge Done")
                        st.write(f"{label} shape → {df_all.shape}")
                    except Exception as e:
                        st.error(f"⚠️ Failed to process {label}: {e}")
                        st.write(f"Error details: {str(e)}")
                        import traceback
                        st.write("Full traceback:")
                        st.code(traceback.format_exc())
                else:
                    st.warning(f"⚠️ No data found for {label}")

            # LEAVE (keep as DataFrame)
            df_leave = dfs.get("LEAVE")
            if df_leave is not None:
                splits["LEAVE"] = {"raw": df_leave}
                st.write(f"✔️ LEAVE uploaded (DataFrame)")
                st.write(f"LEAVE shape → {df_leave.shape}")

            # Upload EXEMPTED separately
            # Compact exempted file uploader
            st.markdown("---")
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.markdown("**📁 EXEMPTED File (Optional)**")
                exempted_file = st.file_uploader(
                    "Choose EXEMPTED file", 
                    type=["xlsx"], 
                    key="exempted_upload",
                    help="Exempted leaves data (optional)",
                    label_visibility="collapsed"
                )
                st.caption("💡 Optional exempted leaves data")
            if exempted_file is not None:
                try:
                    df_exempted_excel = pd.ExcelFile(exempted_file)
                    splits["EXEMPTED"] = {"raw": df_exempted_excel}
                    st.write("✔️ EXEMPTED uploaded as ExcelFile")
                    st.write(f"Sheets available → {df_exempted_excel.sheet_names}")
                except Exception as e:
                    st.error(f"⚠️ Failed to read EXEMPTED as ExcelFile: {e}")

            # Save in session
            st.session_state["attendance_splits"] = splits

            # ---- From here onwards: safe to assume files are available ----
            # e.g. Google Sheet employee master
            try:
                client = connect_gsheet()
                df_emp = get_dataframe(client, st.secrets["my_secrets"]["sheet_id"], "users")
                df_emp['Date of Birth'] = df_emp['Date of Birth'].apply(preprocess_date)
                df_emp['Date of Birth'] = pd.to_datetime(df_emp['Date of Birth'])
            except Exception as e:
                st.error(f"❌ Error connecting to Google Sheets: {e}")
                return

            # ---------- Extract processed DataFrames from splits ----------
            df_gimt_all     = splits.get("gimt", {}).get("all", pd.DataFrame())
            df_gimt_merged  = splits.get("gimt", {}).get("merged", pd.DataFrame())

            df_gips_all     = splits.get("gips", {}).get("all", pd.DataFrame())
            df_gips_merged  = splits.get("gips", {}).get("merged", pd.DataFrame())

            df_admin_all    = splits.get("admin", {}).get("all", pd.DataFrame())
            df_admin_merged = splits.get("admin", {}).get("merged", pd.DataFrame())

            df_leave        = splits.get("LEAVE", {}).get("raw", pd.DataFrame())
            df_exempted     = splits.get("EXEMPTED", {}).get("raw", None)  # ExcelFile, not DF

            # Process splits dictionary

            # ---------- Combine Faculty & Admin ----------
            # Update the initialized variables with actual data
            df_fac_detail = (
                pd.concat([df_gimt_all, df_gips_all], ignore_index=True).fillna(0)
                if not (df_gimt_all.empty and df_gips_all.empty)
                else pd.DataFrame()
            )

            df_fac_conso = (
                pd.concat([df_gimt_merged, df_gips_merged], ignore_index=True).fillna(0)
                if not (df_gimt_merged.empty and df_gips_merged.empty)
                else pd.DataFrame()
            )

            df_admin_detail = df_admin_all.copy().fillna(0) if not df_admin_all.empty else pd.DataFrame()
            df_admin_conso  = df_admin_merged.copy().fillna(0) if not df_admin_merged.empty else pd.DataFrame()

            # Combined data processing

            # ---------- Verify Emp Id column exists ----------
            if "Emp Id" not in df_emp.columns:
                st.error("ERP user sheet missing column 'Emp Id' (please ensure a column for employee id exists).")
                st.write("Columns in ERP:", df_emp.columns.tolist())
                return

            # Check for common variations of Emp Id column
            emp_id_variations = ['Emp Id', 'EmpId', 'Employee Id', 'EmployeeId', 'Employee ID', 'EMP_ID', 'emp_id']
            found_emp_id_col = None
            
            if not df_fac_detail.empty:
                for col in emp_id_variations:
                    if col in df_fac_detail.columns:
                        found_emp_id_col = col
                        break
            
            if found_emp_id_col and found_emp_id_col != 'Emp Id':
                df_fac_detail = df_fac_detail.rename(columns={found_emp_id_col: 'Emp Id'})
            elif not df_fac_detail.empty and not found_emp_id_col:
                st.error("❌ No employee ID column found in attendance data. Expected one of:", emp_id_variations)
                st.write("Columns in attendance:", df_fac_detail.columns.tolist())
                return

            # ---------- Prepare consolidated DataFrames ----------
            # rename and reorder for consolidated dataframes safely (only pick existing cols)
            # Based on working notebook: AM_abs -> actual_AM_abs, PM_abs -> actual_PM_abs, etc.
            col_to_rename = {
                'AM_abs': 'actual_AM_abs', 
                'PM_abs': 'actual_PM_abs', 
                'days_abs': 'actual_days_abs', 
                'No_of_late': 'actual_No_of_late'
            }
            # apply rename if those keys exist
            df_fac_conso.rename(columns=col_to_rename, inplace=True)
            df_admin_conso.rename(columns=col_to_rename, inplace=True)

            # safe desired order construction - based on working notebook
            desired_order = [
                'Emp Id', 'Names', 'Working Days', 'Present', 'Absent',
                'actual_AM_abs', 'actual_PM_abs', 'actual_days_abs',
                'half_day_flags', 'late_flags', 'early_flags',
                'actual_No_of_late'
            ]
            # keep only existing
            desired_order = [c for c in desired_order if c in df_fac_conso.columns]
            if not df_fac_conso.empty:
                df_fac_conso = df_fac_conso[desired_order]

            desired_order_admin = [c for c in desired_order if c in df_admin_conso.columns]
            if not df_admin_conso.empty:
                df_admin_conso = df_admin_conso[desired_order_admin]

            # ---------- Merge with ERP employee data ----------
            # emp_df already initialized above

            try:
                # Ensure both dataframes have the 'Emp Id' column
                if not df_fac_detail.empty and 'Emp Id' not in df_fac_detail.columns:
                    st.error("❌ Faculty detail data missing 'Emp Id' column after processing")
                    return
                if 'Emp Id' not in emp_df.columns:
                    st.error("❌ ERP data missing 'Emp Id' column")
                    return
                
                # Ensure 'Emp Id' columns are the same data type for merging
                df_fac_detail['Emp Id'] = df_fac_detail['Emp Id'].astype(str)
                emp_df['Emp Id'] = emp_df['Emp Id'].astype(str)
                
                # Merging faculty detail with ERP data
                df_fac_detail_ID = pd.merge(df_fac_detail, emp_df, how='left', on='Emp Id')
                st.success(f"✅ Faculty detail merge successful. Result shape: {df_fac_detail_ID.shape}")
                
                # move columns if function available; ignore if it fails
                try:
                    df_fac_detail_ID = move_columns(df_fac_detail_ID, {'Name': 1, 'Designation': 2, 'Department': 3})
                except Exception:
                    pass
                if 'Names' in df_fac_detail_ID.columns:
                    try:
                        df_fac_detail_ID = df_fac_detail_ID.drop(columns=['Names'])
                    except Exception:
                        pass
            except Exception as e:
                st.error(f"❌ Merge faculty detail with ERP failed: {e}")
                st.write("**Faculty detail columns:**", df_fac_detail.columns.tolist())
                st.write("**ERP columns:**", emp_df.columns.tolist())
                st.write("**Faculty detail sample data:**")
                if not df_fac_detail.empty:
                    st.dataframe(df_fac_detail.head(2))
                else:
                    st.write("No data")
                return

            try:
                if not df_admin_detail.empty and 'Emp Id' in df_admin_detail.columns:
                    # Ensure 'Emp Id' columns are the same data type for merging
                    df_admin_detail['Emp Id'] = df_admin_detail['Emp Id'].astype(str)
                    
                    # Merging admin detail with ERP data
                    df_admin_detail_ID = pd.merge(df_admin_detail, emp_df, how='left', on='Emp Id')
                    st.success(f"✅ Admin detail merge successful. Result shape: {df_admin_detail_ID.shape}")
                    
                    try:
                        df_admin_detail_ID = move_columns(df_admin_detail_ID, {'Name': 1, 'Designation': 2, 'Department': 3})
                    except Exception:
                        pass
                    if 'Names' in df_admin_detail_ID.columns:
                        df_admin_detail_ID = df_admin_detail_ID.drop(columns=['Names'], errors='ignore')
                else:
                    # if admin detail empty, create empty df with ERP cols
                    df_admin_detail_ID = pd.DataFrame(columns=(list(emp_df.columns) + list(df_admin_detail.columns)))
            except Exception as e:
                st.warning(f"⚠️ Admin detail merge failed: {e}")
                # if admin detail empty, create empty df with ERP cols
                df_admin_detail_ID = pd.DataFrame(columns=(list(emp_df.columns) + list(df_admin_detail.columns)))

            try:
                if not df_fac_conso.empty and 'Emp Id' in df_fac_conso.columns:
                    # Ensure 'Emp Id' columns are the same data type for merging
                    df_fac_conso['Emp Id'] = df_fac_conso['Emp Id'].astype(str)
                    
                    # Merging faculty consolidated with ERP data
                    df_fac_conso_ID = pd.merge(df_fac_conso, emp_df, how='left', on='Emp Id')
                    st.success(f"✅ Faculty consolidated merge successful. Result shape: {df_fac_conso_ID.shape}")
                    
                    if not df_fac_conso_ID.empty:
                        try:
                            df_fac_conso_ID = move_columns(df_fac_conso_ID, {'Name': 1, 'Designation': 2, 'Department': 3})
                        except Exception:
                            pass
                        df_fac_conso_ID = df_fac_conso_ID.drop(columns=['Names'], errors='ignore')
                else:
                    df_fac_conso_ID = pd.DataFrame()
            except Exception as e:
                st.warning(f"⚠️ Faculty consolidated merge failed: {e}")
                df_fac_conso_ID = pd.DataFrame()

            try:
                if not df_admin_conso.empty and 'Emp Id' in df_admin_conso.columns:
                    # Ensure 'Emp Id' columns are the same data type for merging
                    df_admin_conso['Emp Id'] = df_admin_conso['Emp Id'].astype(str)
                    
                    # Merging admin consolidated with ERP data
                    df_admin_conso_ID = pd.merge(df_admin_conso, emp_df, how='left', on='Emp Id')
                    st.success(f"✅ Admin consolidated merge successful. Result shape: {df_admin_conso_ID.shape}")
                    
                    if not df_admin_conso_ID.empty:
                        try:
                            df_admin_conso_ID = move_columns(df_admin_conso_ID, {'Name': 1, 'Designation': 2, 'Department': 3})
                        except Exception:
                            pass
                        df_admin_conso_ID = df_admin_conso_ID.drop(columns=['Names'], errors='ignore')
                else:
                    df_admin_conso_ID = pd.DataFrame()
            except Exception as e:
                st.warning(f"⚠️ Admin consolidated merge failed: {e}")
                df_admin_conso_ID = pd.DataFrame()

            # ---------- Display consolidated previews ----------
            if not df_fac_conso_ID.empty:
                st.write(f"This is the consolidate faculty biometric data {df_fac_conso_ID.shape}")
                st.dataframe(df_fac_conso_ID.head(3))
            if not df_admin_conso_ID.empty:
                st.write(f"This is the consolidate admin biometric data {df_admin_conso_ID.shape}")
                st.dataframe(df_admin_conso_ID.head(3))

            # ---------- Step: compute actual counts ----------
            # create copies to work on
            df_fac_actual = df_fac_conso_ID.copy() if not df_fac_conso_ID.empty else pd.DataFrame()
            df_admin_actual = df_admin_conso_ID.copy() if not df_admin_conso_ID.empty else pd.DataFrame()

            # safe creation of actual_* columns as lists/strings - based on working notebook
            def safe_len(value):
                """Safely get length of a value, handling various data types"""
                if value is None:
                    return 0
                try:
                    # Handle pandas Series or numpy arrays
                    if hasattr(value, 'isna'):
                        if value.isna().any():
                            return 0
                    elif hasattr(value, '__len__'):
                        return len(value)
                    else:
                        return 0
                except:
                    return 0
            
            if not df_fac_actual.empty:
                df_fac_actual['actual_half_day'] = df_fac_actual.apply(lambda x: safe_len(x.get('actual_AM_abs', [])) + safe_len(x.get('actual_PM_abs', [])), axis=1)
                df_fac_actual['actual_full_day'] = df_fac_actual.apply(lambda x: safe_len(x.get('actual_days_abs', [])), axis=1)
            if not df_admin_actual.empty:
                df_admin_actual['actual_half_day'] = df_admin_actual.apply(lambda x: safe_len(x.get('actual_AM_abs', [])) + safe_len(x.get('actual_PM_abs', [])), axis=1)
                df_admin_actual['actual_full_day'] = df_admin_actual.apply(lambda x: safe_len(x.get('actual_days_abs', [])), axis=1)

            # add actual_No_of_late fallback - based on working notebook
            if 'actual_No_of_late' not in df_fac_actual.columns:
                df_fac_actual['actual_No_of_late'] = 0
            if 'actual_No_of_late' not in df_admin_actual.columns:
                df_admin_actual['actual_No_of_late'] = 0

            # pick columns for actual attendance data - based on working notebook
            col_to_select = [c for c in ['Emp Id', 'Name', 'Designation', 'Department', 'Working Days', 'Present', 'Absent', 'actual_half_day', 'actual_full_day', 'actual_No_of_late'] if c in df_fac_actual.columns]
            df_fac_actual = df_fac_actual[col_to_select] if not df_fac_actual.empty else pd.DataFrame(columns=col_to_select)
            df_admin_actual = df_admin_actual[[c for c in col_to_select if c in df_admin_actual.columns]] if not df_admin_actual.empty else pd.DataFrame(columns=col_to_select)

            # ---------- Step 3: Exempted leaves processing ----------
            try:
                # process_exempted_leaves expects an ExcelFile or path; df_exempted is ExcelFile for PROD or passed in DEV
                if df_exempted is not None:
                    df_exempted_processed = process_exempted_leaves(df_exempted)
                else:
                    # if no exempted provided create empty DF with expected columns
                    df_exempted_processed = pd.DataFrame(columns=['Emp Id','late_count','half_day_count','full_day_count','Name'])
                
                # normalize names
                df_exempted_processed = clean_columns(df_exempted_processed)
                
                # rename expected columns to unified tokens - based on working notebook
                rename_map = {
                    'late_count': 'exempt_late',
                    'half_day_count': 'exempt_HD', 
                    'full_day_count': 'exempt_FD'
                }
                df_exempted_processed.rename(columns=rename_map, inplace=True)
                
                # Fix column name mismatch: 'Emp ID' -> 'Emp Id'
                if 'Emp ID' in df_exempted_processed.columns:
                    df_exempted_processed.rename(columns={'Emp ID': 'Emp Id'}, inplace=True)
                
                # drop Name if present (we use ERP name)
                df_exempted_processed = df_exempted_processed.drop(columns=['Name'], errors='ignore')
                
            except Exception as e:
                st.warning(f"Exempted processing failed or no exempted data: {e}")
                df_exempted_processed = pd.DataFrame(columns=['Emp Id','Exempt_Late','Exempt_Hd','Exempt_Fd'])


                # ---------- merge exempted with actuals ----------


                try:


            # Ensure 'Emp Id' columns are the same data type for merging

            if not df_fac_actual.empty and 'Emp Id' in df_fac_actual.columns:

                df_fac_actual['Emp Id'] = df_fac_actual['Emp Id'].astype(str)

            if not df_admin_actual.empty and 'Emp Id' in df_admin_actual.columns:

                df_admin_actual['Emp Id'] = df_admin_actual['Emp Id'].astype(str)

            if not df_exempted_processed.empty and 'Emp Id' in df_exempted_processed.columns:

                df_exempted_processed['Emp Id'] = df_exempted_processed['Emp Id'].astype(str)

            
            df_fac_actual_exempted = pd.merge(df_fac_actual, df_exempted_processed, how='left', on='Emp Id').fillna(0)

            df_admin_actual_exempted = pd.merge(df_admin_actual, df_exempted_processed, how='left', on='Emp Id').fillna(0)

                except Exception as e:


            st.error(f"Failed to merge exempted data: {e}")

            return


                # compute adjusted Half/Full/Late after exemption - based on working notebook


                for df in [df_fac_actual_exempted, df_admin_actual_exempted]:


            if not df.empty:

                # Use safe column access instead of df.get() to avoid ambiguous truth value errors

                actual_half_day = df['actual_half_day'] if 'actual_half_day' in df.columns else 0

                actual_full_day = df['actual_full_day'] if 'actual_full_day' in df.columns else 0

                actual_late = df['actual_No_of_late'] if 'actual_No_of_late' in df.columns else 0

                exempt_hd = df['exempt_HD'] if 'exempt_HD' in df.columns else 0

                exempt_fd = df['exempt_FD'] if 'exempt_FD' in df.columns else 0

                exempt_late = df['exempt_late'] if 'exempt_late' in df.columns else 0

            
                df['Half Days'] = np.maximum(actual_half_day - exempt_hd, 0)

                df['Full Days'] = np.maximum(actual_full_day - exempt_fd, 0)

                df['Late'] = np.maximum(actual_late - exempt_late, 0)


                # select final columns for adjusted attendance


                col_to_select_final = [c for c in ['Emp Id', 'Name', 'Designation', 'Department', 'Working Days', 'Present', 'Absent', 'Half Days', 'Full Days', 'Late'] if c in df_fac_actual_exempted.columns]


                df_fac_attend_adjusted = df_fac_actual_exempted[col_to_select_final] if not df_fac_actual_exempted.empty else pd.DataFrame(columns=col_to_select_final)


                df_admin_attend_adjusted = df_admin_actual_exempted[col_to_select_final] if not df_admin_actual_exempted.empty else pd.DataFrame(columns=col_to_select_final)



                # ---------- Step 4: ERP Leave data processing ----------


                try:


            if not df_leave_erp.empty:

                # ensure date columns exist and preprocess

                if 'From Date' in df_leave_erp.columns:

                    df_leave_erp['From Date'] = df_leave_erp['From Date'].apply(preprocess_date)

                    df_leave_erp['From Date'] = pd.to_datetime(df_leave_erp['From Date'], errors='coerce')

                if 'To Date' in df_leave_erp.columns:

                    df_leave_erp['To Date'] = df_leave_erp['To Date'].apply(preprocess_date)

                    df_leave_erp['To Date'] = pd.to_datetime(df_leave_erp['To Date'], errors='coerce')


                # calculate working days from biometric IN data if available (fallback to no_working_days)

                try:

                    wd = calculate_working_days(df_gimt_in) if not df_gimt_in.empty else no_working_days

                    df_leave_erp_summary = calculate_leave_summary_with_wd_leaves(df_leave_erp, wd)

                    df_leave_erp_summary.fillna(0, inplace=True)

                except Exception as e:

                    st.warning(f"Leave summary calculation failed: {e}")

                    df_leave_erp_summary = pd.DataFrame(columns=['Emp Id', 'Total WD leaves', 'Casual Leave'])

            else:

                df_leave_erp_summary = pd.DataFrame(columns=['Emp Id'])

                except Exception as e:


            st.warning(f"ERP leave processing error: {e}")

            df_leave_erp_summary = pd.DataFrame(columns=['Emp Id'])


                # create compact leave table


                if not df_leave_erp_summary.empty:


            # Use safe column access instead of df.get() to avoid ambiguous truth value errors

            total_wd_leaves = df_leave_erp_summary['Total WD leaves'] if 'Total WD leaves' in df_leave_erp_summary.columns else 0

            casual_leave = df_leave_erp_summary['Casual Leave'] if 'Casual Leave' in df_leave_erp_summary.columns else 0

            df_leave_erp_summary['Total WD leaves'] = total_wd_leaves + casual_leave

            cols_to_drop = [c for c in ["Casual Leave", "Sick Leave", "Duty Leave", "Vacation Leave", "Maternity Leave", "Earned Leave", "Paternity Leave"] if c in df_leave_erp_summary.columns]

            df_leave_compact = df_leave_erp_summary.drop(columns=cols_to_drop, errors='ignore')

            if 'Emp Id' in df_leave_compact.columns and 'Total WD leaves' in df_leave_compact.columns:

                df_leave_compact = df_leave_compact[['Emp Id', 'Total WD leaves']]

            else:

                df_leave_compact = pd.DataFrame(columns=['Emp Id', 'Total WD leaves'])

            # remove Name column (we use ERP names in merges)

            df_leave_compact = df_leave_compact.drop(columns=['Name'], errors='ignore')

                else:


            df_leave_compact = pd.DataFrame(columns=['Emp Id', 'Total WD leaves'])


                # ---------- Step 5: combine observed leaves and ERP leaves to create report ----------


                try:


            # Ensure 'Emp Id' columns are the same data type for merging

            if not df_fac_actual_exempted.empty and 'Emp Id' in df_fac_actual_exempted.columns:

                df_fac_actual_exempted['Emp Id'] = df_fac_actual_exempted['Emp Id'].astype(str)

            if not df_admin_actual_exempted.empty and 'Emp Id' in df_admin_actual_exempted.columns:

                df_admin_actual_exempted['Emp Id'] = df_admin_actual_exempted['Emp Id'].astype(str)

            if not df_leave_compact.empty and 'Emp Id' in df_leave_compact.columns:

                df_leave_compact['Emp Id'] = df_leave_compact['Emp Id'].astype(str)

            
            df_fac_report = pd.merge(df_fac_actual_exempted, df_leave_compact, how='left', on='Emp Id').fillna(0)

            df_admin_report = pd.merge(df_admin_actual_exempted, df_leave_compact, how='left', on='Emp Id').fillna(0)

                except Exception as e:


            st.error(f"Failed to merge observed and ERP leaves: {e}")

            return


                # Weighted sum (Half Days = 0.5, Full Days = 1.0) => Observed Leaves


                col_to_sum = ['Half Days', 'Full Days']


                df_fac_report = weighted_sum_and_replace_columns(df_fac_report, col_to_sum, 'Observed Leaves', [0.5, 1.0]) if not df_fac_report.empty else df_fac_report


                df_admin_report = weighted_sum_and_replace_columns(df_admin_report, col_to_sum, 'Observed Leaves', [0.5, 1.0]) if not df_admin_report.empty else df_admin_report



                # cleanup intermediate columns (tolerant of missing cols) - based on working notebook


                cols_to_delete = ['actual_half_day','actual_full_day','actual_No_of_late','exempt_late','exempt_HD','exempt_FD']


                df_fac_report = df_fac_report.drop(columns=[c for c in cols_to_delete if c in df_fac_report.columns], errors='ignore')


                df_admin_report = df_admin_report.drop(columns=[c for c in cols_to_delete if c in df_admin_report.columns], errors='ignore')



                # Unauthorized leaves = Absent - Total WD leaves


                if 'Absent' in df_fac_report.columns and 'Total WD leaves' in df_fac_report.columns:


            df_fac_report["Unauthorized leaves"] = (df_fac_report["Absent"] - df_fac_report["Total WD leaves"]).clip(lower=0)

                if 'Absent' in df_admin_report.columns and 'Total WD leaves' in df_admin_report.columns:


            df_admin_report["Unauthorized leaves"] = (df_admin_report["Absent"] - df_admin_report["Total WD leaves"]).clip(lower=0)


                # ---------- Step 6: Prepare Excel output and provide download ----------


                try:


            # faculty workbook

            sheets_fac = ['Bio details','Bio Consolidated','Exempted','ERP Leave','ERP-Observed Leaves','Report']

            dataframes_fac = [

                df_fac_detail_ID if 'df_fac_detail_ID' in locals() else pd.DataFrame(),

                df_fac_conso_ID if 'df_fac_conso_ID' in locals() else pd.DataFrame(),

                df_fac_actual_exempted if not df_fac_actual_exempted.empty else pd.DataFrame(),

                df_leave_erp_summary if not df_leave_erp_summary.empty else pd.DataFrame(),

                df_fac_report if not df_fac_report.empty else pd.DataFrame(),

                df_fac_report.drop(columns=['Observed Leaves'], errors='ignore') if 'Observed Leaves' in df_fac_report.columns else df_fac_report

            ]


            out_fac = io.BytesIO()

            with pd.ExcelWriter(out_fac, engine="xlsxwriter") as writer:

                for sheet, frame in zip(sheets_fac, dataframes_fac):

                    frame.to_excel(writer, sheet_name=sheet, index=False)

            out_fac.seek(0)

            st.download_button(

                label="📥 Download Faculty Report (Excel)",

                data=out_fac,

                file_name="report_faculties_V2.xlsx",

                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

        )
        st.success("Faculty Report ready for download.")
            except Exception as e:

        st.error(f"Failed to prepare faculty Excel: {e}")

            try:

        # staff workbook
        sheets_admin = ['Bio details','Bio Consolidated','Exempted','ERP Leave','ERP-Observed Leaves','Report']
        dataframes_admin = [
            df_admin_detail_ID if 'df_admin_detail_ID' in locals() else pd.DataFrame(),
            df_admin_conso_ID if 'df_admin_conso_ID' in locals() else pd.DataFrame(),
            df_admin_actual_exempted if not df_admin_actual_exempted.empty else pd.DataFrame(),
            df_leave_erp_summary if not df_leave_erp_summary.empty else pd.DataFrame(),
            df_admin_report if not df_admin_report.empty else pd.DataFrame(),
            df_admin_report.drop(columns=['Observed Leaves'], errors='ignore') if 'Observed Leaves' in df_admin_report.columns else df_admin_report
        ]

        out_adm = io.BytesIO()
        with pd.ExcelWriter(out_adm, engine="xlsxwriter") as writer:
            for sheet, frame in zip(sheets_admin, dataframes_admin):
                frame.to_excel(writer, sheet_name=sheet, index=False)
        out_adm.seek(0)
        st.download_button(
            label="📥 Download Staff Report (Excel)",
            data=out_adm,
            file_name="report_staffs_V2.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.success("Staff Report ready for download.")
            except Exception as e:

        st.error(f"Failed to prepare staff Excel: {e}")

    else:
        # Files not uploaded yet - show upload instructions
        st.info("📋 Please upload the 4 required files to begin processing.")

    # End of app()