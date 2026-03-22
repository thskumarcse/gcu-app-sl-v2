import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import os
from utility_attendance import (
    stepwise_file_upload, split_file, merge_files, move_columns,
    weighted_sum_and_replace_columns, calculate_leave_summary_with_wd_leaves,
    process_exempted_leaves,
    HOLIDAY_LIST,
    faculty_calendar_working_context,
)
from utility import preprocess_date


def _normalize_emp_id_series(s):
    """Align biometric / sheet / leave Emp Id values for merges (Excel often yields '123.0')."""
    out = s.astype(str).str.strip()
    out = out.replace({"nan": "", "None": "", "<NA>": ""}, regex=False)
    out = out.str.replace(r"\.0$", "", regex=True)
    return out


def _header_key(c):
    return str(c).strip().lower().replace("_", " ")


def _pick_first_column(df, header_candidates):
    """Return first column whose normalized header is in candidates or equals one of them."""
    want = {str(x).strip().lower().replace("_", " ") for x in header_candidates}
    for col in df.columns:
        if _header_key(col) in want:
            return col
    return None


def _pick_emp_id_column(df):
    col = _pick_first_column(
        df,
        {"emp id", "employee id", "emp_id", "employee code", "employee no", "employee number"},
    )
    if col:
        return col
    for c in df.columns:
        h = _header_key(c)
        if "emp" in h and "id" in h:
            return c
    return None


def _standardize_master_df(raw_df):
    """
    Map a users worksheet or similar to Emp Id, Name, Designation, Department.
    """
    empty = pd.DataFrame(columns=["Emp Id", "Name", "Designation", "Department"])
    if raw_df is None or raw_df.empty:
        return empty

    eid_c = _pick_emp_id_column(raw_df)
    name_c = _pick_first_column(
        raw_df,
        {"name", "employee name", "full name", "emp name", "staff name"},
    )
    des_c = _pick_first_column(
        raw_df,
        {"designation", "designations", "title", "job title", "post"},
    )
    dep_c = _pick_first_column(
        raw_df,
        {"department", "departments", "dept", "department name"},
    )

    if eid_c is None:
        return empty

    out = pd.DataFrame()
    out["Emp Id"] = raw_df[eid_c]
    out["Name"] = raw_df[name_c] if name_c else ""
    out["Designation"] = raw_df[des_c] if des_c else ""
    out["Department"] = raw_df[dep_c] if dep_c else ""
    return out


def _employee_master_from_leave_export(df_leave):
    """Fallback ERP identity from uploaded leave export (one row per Emp Id)."""
    empty = pd.DataFrame(columns=["Emp Id", "Name", "Designation", "Department"])
    if df_leave is None or df_leave.empty:
        return empty
    eid_c = _pick_emp_id_column(df_leave)
    if eid_c is None:
        return empty
    name_c = _pick_first_column(
        df_leave,
        {"name", "employee name", "full name", "emp name"},
    )
    des_c = _pick_first_column(
        df_leave,
        {"designation", "title", "job title"},
    )
    dep_c = _pick_first_column(
        df_leave,
        {"department", "dept", "department name"},
    )
    cols = [eid_c]
    if name_c:
        cols.append(name_c)
    if des_c:
        cols.append(des_c)
    if dep_c:
        cols.append(dep_c)
    sub = df_leave[cols].drop_duplicates(subset=[eid_c], keep="first").copy()
    rename = {eid_c: "Emp Id"}
    if name_c:
        rename[name_c] = "Name"
    if des_c:
        rename[des_c] = "Designation"
    if dep_c:
        rename[dep_c] = "Department"
    sub.rename(columns=rename, inplace=True)
    for c in ("Name", "Designation", "Department"):
        if c not in sub.columns:
            sub[c] = ""
    return sub[["Emp Id", "Name", "Designation", "Department"]]


def _identity_master_from_detail(detail_id_df):
    """
    Name, Designation, Department from `df_fac_detail_ID` / `df_admin_detail_ID`
    (already merged with ERP in step 2). One row per Emp Id for Report / Clock joins.
    """
    cols = ["Emp Id", "Name", "Designation", "Department"]
    if detail_id_df is None or detail_id_df.empty or "Emp Id" not in detail_id_df.columns:
        return pd.DataFrame(columns=cols)
    m = detail_id_df.copy()
    out = pd.DataFrame()
    out["Emp Id"] = m["Emp Id"]
    for c in ("Name", "Designation", "Department"):
        out[c] = m[c] if c in m.columns else ""
    out["Emp Id"] = _normalize_emp_id_series(out["Emp Id"])
    out = out.drop_duplicates(subset=["Emp Id"], keep="first")
    for c in ("Name", "Designation", "Department"):
        out[c] = (
            out[c].astype(str).replace({"nan": "", "None": ""}, regex=False).str.strip()
        )
    return out[cols]


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

def _find_input_present_column(df_in):
    """Resolve CSV 'Present' column (case-insensitive)."""
    for c in df_in.columns:
        if str(c).strip().lower() == 'present':
            return c
    return None


def _apply_present_bio_cap(df, emp_present_col='Present'):
    """
    i. If present_bio > Present then Present = present_bio
    ii. If Present > Working Days then Present = Working Days
    Recalculate Absent = Working Days - Present (floor at 0).
    """
    if 'present_bio' not in df.columns:
        return df
    present = pd.to_numeric(df.get(emp_present_col, 0), errors='coerce').fillna(0.0)
    present_bio_vals = pd.to_numeric(df['present_bio'], errors='coerce').fillna(0.0)
    working_days = pd.to_numeric(df.get('Working Days', 0), errors='coerce').fillna(0.0)
    updated = np.where(present_bio_vals > present, present_bio_vals, present)
    updated = np.minimum(updated, working_days)
    df[emp_present_col] = updated
    df['Absent'] = (working_days - updated).clip(lower=0.0)
    return df


def _apply_present_bio(df_merged, df_in):
    src = _find_input_present_column(df_in)
    if src is None:
        return df_merged

    present_bio = df_in[['Emp Id', src]].copy()
    present_bio.rename(columns={src: 'present_bio'}, inplace=True)
    df_merged = pd.merge(df_merged, present_bio, how='left', on='Emp Id')
    return _apply_present_bio_cap(df_merged)

EXEMPTED_SHEET_COLUMNS = ['Emp Id', 'Name', 'exempt_late', 'exempt_HD', 'exempt_FD']


def _exempted_export_df(df):
    """Exempted Excel sheet: fixed columns only."""
    return df.reindex(columns=EXEMPTED_SHEET_COLUMNS)


def _fillna_numeric_only(df):
    """Avoid fillna(0) on object columns (would corrupt Name / Designation / Department)."""
    out = df.copy()
    num_cols = out.select_dtypes(include=[np.number]).columns
    if len(num_cols):
        out[num_cols] = out[num_cols].fillna(0)
    return out


def _report_apply_erp_identity(report_df, master_df):
    """
    Report sheet: Name, Designation, Department from the same master as Bio details
    (`df_fac_detail_ID` / `df_admin_detail_ID` via `master_df`). Emp Id normalized for join.
    """
    report_df = report_df.copy()
    lead = ["Emp Id", "Name", "Designation", "Department"]
    if master_df is None or master_df.empty:
        for c in ("Name", "Designation", "Department"):
            if c not in report_df.columns:
                report_df[c] = ""
        report_df["Emp Id"] = _normalize_emp_id_series(report_df["Emp Id"])
        rest = [c for c in report_df.columns if c not in lead]
        return report_df[[c for c in lead if c in report_df.columns] + rest]

    master = master_df[["Emp Id", "Name", "Designation", "Department"]].copy()
    master["Emp Id"] = _normalize_emp_id_series(master["Emp Id"])
    report_df["Emp Id"] = _normalize_emp_id_series(report_df["Emp Id"])
    master = master.drop_duplicates(subset=["Emp Id"], keep="first")
    out = report_df.drop(columns=["Name", "Designation", "Department"], errors="ignore")
    out = pd.merge(out, master, on="Emp Id", how="left")
    rest = [c for c in out.columns if c not in lead]
    return out[lead + rest]


def _build_clock_sheet(df_in, df_out, report_df):
    base = report_df[['Emp Id', 'Name', 'Present', 'Absent']].copy()
    clock_in_cols = [c for c in df_in.columns if c.startswith('clock_in_')]
    clock_out_cols = [c for c in df_out.columns if c.startswith('clock_out_')]
    clock_df = df_in[['Emp Id'] + clock_in_cols].merge(
        df_out[['Emp Id'] + clock_out_cols],
        on='Emp Id',
        how='left'
    )
    return base.merge(clock_df, on='Emp Id', how='left')

def _has_streamlit_secrets():
    secrets_paths = [
        os.path.join(os.path.expanduser("~"), ".streamlit", "secrets.toml"),
        os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
    ]
    return any(os.path.exists(p) for p in secrets_paths)

def app():
    fix_streamlit_layout()
    set_compact_theme()
    
    st.header("HR Attendance")
    
    # File upload section
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("📁 Upload your attendance files step by step")
        st.caption(
            "Working days are computed from the GIMT file: Sundays, 1st & 3rd Saturdays, "
            "and the declared holiday list in code (`utility_attendance.HOLIDAY_LIST`). "
            "Add ad‑hoc holidays or forced working days below."
        )
        extra_holidays_csv = st.text_input(
            "Extra holidays (comma-separated, dd-mmm-yyyy)",
            "",
            help="Additional closed days for this run only.",
            key="hr_extra_holidays",
        )
        extra_working_csv = st.text_input(
            "Extra working days (comma-separated, dd-mmm-yyyy)",
            "",
            help="Days that count as working even if they fall on Sun / 1st–3rd Sat / listed holiday.",
            key="hr_extra_working",
        )
        wd_override = st.number_input(
            "Manual working-day count (0 = auto from calendar)",
            min_value=0,
            max_value=31,
            value=0,
            help="Override the computed count only if needed.",
            key="hr_wd_override",
        )

        # Stepwise file upload
        labels = ["GIMT", "GIPS", "ADMIN", "LEAVE"]
        dfs = stepwise_file_upload(labels, key_prefix="attendance")
        
        # Exempted file upload
        st.markdown("---")
        st.markdown("**Upload Exempted file** — *required*")
        exempted_file = st.file_uploader(
            "Choose exempted leaves file (.xlsx / .xls)",
            type=["xlsx", "xls"],
            help="Required: late / half-day / full-day exempted counts per employee.",
            key="hr_exempted_upload",
        )

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
            hol_gimt, working_mm_dd_gimt, computed_wd_gimt = faculty_calendar_working_context(
                df_gimt_in,
                declared_holidays=HOLIDAY_LIST,
                extra_holidays_csv=extra_holidays_csv,
                extra_working_csv=extra_working_csv,
            )
            no_working_days_gimt = wd_override if wd_override > 0 else computed_wd_gimt
            st.info(
                f"**Working days (GIMT):** {no_working_days_gimt}"
                + ("" if wd_override <= 0 else " (manual override)")
                + f" — computed from calendar: {computed_wd_gimt}"
            )

            df_gimt_merged = merge_files(
                df_gimt_in, df_gimt_out, no_working_days_gimt, holiday_cols=hol_gimt
            )
            df_gimt_merged = _apply_present_bio(df_gimt_merged, df_gimt_in)

            df_gips_all, df_gips_in, df_gips_out = split_file(df_gips)
            hol_gips, _, computed_wd_gips = faculty_calendar_working_context(
                df_gips_in,
                declared_holidays=HOLIDAY_LIST,
                extra_holidays_csv=extra_holidays_csv,
                extra_working_csv=extra_working_csv,
            )
            no_working_days_gips = wd_override if wd_override > 0 else computed_wd_gips
            if computed_wd_gips != computed_wd_gimt and wd_override <= 0:
                st.warning(
                    f"GIPS working-day count ({computed_wd_gips}) differs from GIMT ({computed_wd_gimt}); "
                    "using each file’s own count for that block."
                )
            df_gips_merged = merge_files(
                df_gips_in, df_gips_out, no_working_days_gips, holiday_cols=hol_gips
            )
            df_gips_merged = _apply_present_bio(df_gips_merged, df_gips_in)

            df_admin_all, df_admin_in, df_admin_out = split_file(df_admin)
            hol_adm, _, computed_wd_admin = faculty_calendar_working_context(
                df_admin_in,
                declared_holidays=HOLIDAY_LIST,
                extra_holidays_csv=extra_holidays_csv,
                extra_working_csv=extra_working_csv,
            )
            no_working_days_admin = wd_override if wd_override > 0 else computed_wd_admin
            if computed_wd_admin != computed_wd_gimt and wd_override <= 0:
                st.warning(
                    f"Admin working-day count ({computed_wd_admin}) differs from GIMT ({computed_wd_gimt}); "
                    "using each file’s own count for that block."
                )
            df_admin_merged = merge_files(
                df_admin_in, df_admin_out, no_working_days_admin, holiday_cols=hol_adm
            )
            df_admin_merged = _apply_present_bio(df_admin_merged, df_admin_in)

            for _df in (
                df_gimt_merged,
                df_gips_merged,
                df_admin_merged,
                df_gimt_all,
                df_gips_all,
                df_admin_all,
                df_gimt_in,
                df_gimt_out,
                df_gips_in,
                df_gips_out,
                df_admin_in,
                df_admin_out,
            ):
                if _df is not None and "Emp Id" in _df.columns:
                    _df["Emp Id"] = _normalize_emp_id_series(_df["Emp Id"])
            
            # Step 1.1: Faculty Detailed view (GIMT + GIPS only)
            df_fac_detail = pd.concat([df_gimt_all, df_gips_all], ignore_index=True)
            df_fac_conso = pd.concat([df_gimt_merged, df_gips_merged], ignore_index=True)
            df_fac_detail = _fillna_numeric_only(df_fac_detail)
            df_fac_conso = _fillna_numeric_only(df_fac_conso)

            df_admin_detail = df_admin_all.copy()
            df_admin_detail = _fillna_numeric_only(df_admin_detail)

            df_admin_conso = df_admin_merged.copy()
            df_admin_conso = _fillna_numeric_only(df_admin_conso)
            
            # Rename columns
            col_to_rename = {'AM_abs':'actual_AM_abs','PM_abs':'actual_PM_abs','days_abs':'actual_days_abs','No_of_late':'actual_No_of_late'}
            df_fac_conso.rename(columns=col_to_rename, inplace=True)
            df_admin_conso.rename(columns=col_to_rename, inplace=True)
            
            # Reorder columns
            desired_order = [
                'Emp Id', 'Names',
                'Working Days', 'Present', 'present_bio', 'Absent',
                'actual_AM_abs', 'actual_PM_abs', 'actual_days_abs',
                'half_day_flags', 'late_flags', 'early_flags',
                'actual_No_of_late'
            ]
            desired_order = [col for col in desired_order if col in df_fac_conso.columns]
            df_fac_conso = df_fac_conso[desired_order]
            df_admin_conso = df_admin_conso[desired_order]
            
            # Step 2: Merge with ERP employee data (from data/emp_master_data.csv)
            _emp_csv_path = os.path.join("data", "emp_master_data.csv")
            try:
                raw_emp = pd.read_csv(_emp_csv_path, dtype=str)
                emp_df = _standardize_master_df(raw_emp)
                if emp_df.empty:
                    raise RuntimeError("empty_emp_master_csv")
            except Exception as _e:
                st.warning(
                    f"⚠️ Could not load employee master from '{_emp_csv_path}' ({_e}). "
                    "Name, Designation and Department will be blank for unmatched employees."
                )
                emp_df = pd.DataFrame(columns=["Emp Id", "Name", "Designation", "Department"])

            emp_df["Emp Id"] = _normalize_emp_id_series(emp_df["Emp Id"])

            for _bio in (df_fac_detail, df_admin_detail, df_fac_conso, df_admin_conso):
                _bio["Emp Id"] = _normalize_emp_id_series(_bio["Emp Id"])

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
            
            col_to_select = [
                'Emp Id', 'Name', 'Designation', 'Department', 'Working Days', 'Present',
            ]
            if 'present_bio' in df_fac_actual.columns:
                col_to_select.append('present_bio')
            col_to_select.extend(
                ['Absent', 'actual_half_day', 'actual_full_day', 'actual_No_of_late']
            )
            col_to_select = [c for c in col_to_select if c in df_fac_actual.columns]
            df_fac_actual = df_fac_actual[col_to_select]
            col_to_select_adm = [c for c in col_to_select if c in df_admin_actual.columns]
            df_admin_actual = df_admin_actual[col_to_select_adm]
            
            # Step 3: Exempted leave adjustments
            df_exempted = process_exempted_leaves(exempted_file)
            df_exempted.rename(columns={'late_count':'exempt_late','half_day_count':'exempt_HD','full_day_count':'exempt_FD'}, inplace=True)
            df_exempted.drop('Name',axis=1,inplace=True)
            df_exempted["Emp Id"] = _normalize_emp_id_series(df_exempted["Emp Id"])
            
            # Merging Actual and Exempted Leaves
            df_fac_actual_exempted = pd.merge(df_fac_actual, df_exempted, how='left', on=['Emp Id'])
            df_fac_actual_exempted = _fillna_numeric_only(df_fac_actual_exempted)

            df_admin_actual_exempted = pd.merge(df_admin_actual, df_exempted, how='left', on=['Emp Id'])
            df_admin_actual_exempted = _fillna_numeric_only(df_admin_actual_exempted)
            
            # Calculating the balance Actual and Exempted Leaves
            df_fac_actual_exempted['Half Days'] = np.maximum(df_fac_actual_exempted['actual_half_day'] - df_fac_actual_exempted['exempt_HD'],0)
            df_fac_actual_exempted['Full Days'] = np.maximum(df_fac_actual_exempted['actual_full_day'] - df_fac_actual_exempted['exempt_FD'],0)
            df_fac_actual_exempted['Late'] = np.maximum(df_fac_actual_exempted['actual_No_of_late'] - df_fac_actual_exempted['exempt_late'],0)

            df_admin_actual_exempted['Half Days'] = np.maximum(df_admin_actual_exempted['actual_half_day'] - df_admin_actual_exempted['exempt_HD'],0)
            df_admin_actual_exempted['Full Days'] = np.maximum(df_admin_actual_exempted['actual_full_day'] - df_admin_actual_exempted['exempt_FD'],0)
            df_admin_actual_exempted['Late'] = np.maximum(df_admin_actual_exempted['actual_No_of_late'] - df_admin_actual_exempted['exempt_late'],0)
            
            col_to_select = [
                'Emp Id', 'Name', 'Designation', 'Department', 'Working Days', 'Present',
            ]
            if 'present_bio' in df_fac_actual_exempted.columns:
                col_to_select.append('present_bio')
            col_to_select.extend(['Absent', 'Half Days', 'Full Days', 'Late'])
            col_to_select = [c for c in col_to_select if c in df_fac_actual_exempted.columns]
            df_fac_attend_adjusted = df_fac_actual_exempted[col_to_select]
            col_to_select_adm2 = [c for c in col_to_select if c in df_admin_actual_exempted.columns]
            df_admin_attend_adjusted = df_admin_actual_exempted[col_to_select_adm2]
            
            # Step 4: ERP Leave integration
            df_leave_erp = df_leave_erp.copy()
            if "Emp Id" in df_leave_erp.columns:
                df_leave_erp["Emp Id"] = _normalize_emp_id_series(df_leave_erp["Emp Id"])

            df_leave_erp["From Date"] = df_leave_erp["From Date"].apply(preprocess_date)
            df_leave_erp["To Date"] = df_leave_erp["To Date"].apply(preprocess_date)
            df_leave_erp["From Date"] = pd.to_datetime(df_leave_erp["From Date"], errors='coerce')
            df_leave_erp["To Date"] = pd.to_datetime(df_leave_erp["To Date"], errors='coerce')
            
            # corrected leaves
            df_leave_erp_summary = calculate_leave_summary_with_wd_leaves(
                df_leave_erp, working_mm_dd_gimt
            ) 
            df_leave_erp_summary.fillna(0, inplace=True)

            # Sum all ERP leave-type columns (pivot). Do not use Total WD + 'Casual Leave' only:
            # leave labels vary (e.g. CL vs Casual Leave), and Extraordinary is excluded from Total WD.
            _erp_meta = {'Emp Id', 'Name', 'Total WD leaves', 'Approved leaves (ERP)'}
            _leave_cols = [c for c in df_leave_erp_summary.columns if c not in _erp_meta]
            _leave_mat = df_leave_erp_summary[_leave_cols].apply(pd.to_numeric, errors='coerce').fillna(0.0)
            df_leave_erp_summary['Approved leaves (ERP)'] = _leave_mat.sum(axis=1)

            cols_to_drop = [
                "Casual Leave", "Sick Leave", "Duty Leave", "Vacation Leave",
                "Maternity Leave", "Earned Leave", "Paternity Leave",'Total WD leaves'
            ]
            df_leave_compact = df_leave_erp_summary.drop(columns=[c for c in cols_to_drop if c in df_leave_erp_summary.columns], errors="ignore")
            df_leave_compact = df_leave_compact[['Emp Id','Name','Approved leaves (ERP)']]
            df_leave_compact.drop(columns='Name', axis=1,inplace=True)

            df_fac_report = pd.merge(df_fac_actual_exempted, df_leave_compact, how='left', on=['Emp Id'])
            df_fac_report = _fillna_numeric_only(df_fac_report)

            df_admin_report = pd.merge(df_admin_actual_exempted, df_leave_compact, how='left', on=['Emp Id'])
            df_admin_report = _fillna_numeric_only(df_admin_report)
            
            col_to_sum = ['Half Days','Full Days']
            df_fac_report = weighted_sum_and_replace_columns(df_fac_report, col_to_sum, 'Observed Leaves', [0.5,1.0])
            df_admin_report = weighted_sum_and_replace_columns(df_admin_report, col_to_sum, 'Observed Leaves', [0.5,1.0])

            # Align Present/Absent with post-exemption half/full totals (same basis as Exempted sheet).
            for _rep in (df_fac_report, df_admin_report):
                _wd = pd.to_numeric(_rep['Working Days'], errors='coerce').fillna(0.0)
                _obs = pd.to_numeric(_rep['Observed Leaves'], errors='coerce').fillna(0.0)
                _rep['Absent'] = _obs
                _rep['Present'] = (_wd - _obs).clip(lower=0.0)

            # Input-file Present → present_bio; cap final Present (same rules as after merge_files).
            for _rep in (df_fac_report, df_admin_report):
                _apply_present_bio_cap(_rep)

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

            df_fac_report_print = df_fac_report_print.drop(columns=['present_bio'], errors='ignore')
            df_admin_report_print = df_admin_report_print.drop(columns=['present_bio'], errors='ignore')

            fac_identity = _identity_master_from_detail(df_fac_detail_ID)
            adm_identity = _identity_master_from_detail(df_admin_detail_ID)
            df_fac_report_print = _report_apply_erp_identity(
                df_fac_report_print, fac_identity
            )
            df_admin_report_print = _report_apply_erp_identity(
                df_admin_report_print, adm_identity
            )

            # Build clock-in/out sheets
            df_fac_clock_sheet = _build_clock_sheet(
                pd.concat([df_gimt_in, df_gips_in], ignore_index=True),
                pd.concat([df_gimt_out, df_gips_out], ignore_index=True),
                df_fac_report_print
            )
            df_admin_clock_sheet = _build_clock_sheet(
                df_admin_in,
                df_admin_out,
                df_admin_report_print
            )
            
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
                    _exempted_export_df(df_fac_actual_exempted).to_excel(
                        writer, sheet_name='Exempted', index=False
                    )
                    df_leave_erp_summary.to_excel(writer, sheet_name='ERP Leave', index=False)
                    df_fac_clock_sheet.to_excel(writer, sheet_name='Clock In Out', index=False)
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
                    _exempted_export_df(df_admin_actual_exempted).to_excel(
                        writer, sheet_name='Exempted', index=False
                    )
                    df_leave_erp_summary.to_excel(writer, sheet_name='ERP Leave', index=False)
                    df_admin_clock_sheet.to_excel(writer, sheet_name='Clock In Out', index=False)
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