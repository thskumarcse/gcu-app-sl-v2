import streamlit as st
import pandas as pd
import numpy as np  
from datetime import datetime, timedelta

# Set of special employee IDs allowed till 9:25
LATE_ALLOWED_IDS = {'GCU010013', 'GCU010017', 'GCU010025', 'GCU030010', 'GCU010005', 'GCU020004'}


def stepwise_file_upload(labels=None, key_prefix="attendance"):
    """
    Step-by-step uploader: only one uploader visible at a time.
    Once uploaded, it disappears and the next uploader shows.
    Stores results in st.session_state.
    
    Returns a dict {label: DataFrame}.
    """

    if labels is None:
        labels = ["File1", "File2"]

    dfs_key = f"{key_prefix}_dfs"
    idx_key = f"{key_prefix}_index"

    # Reset button
    if st.button("🔄 Reset Uploads"):
        st.session_state.pop(dfs_key, None)
        st.session_state.pop(idx_key, None)
        st.rerun()

    # Initialize session state
    if dfs_key not in st.session_state:
        st.session_state[dfs_key] = {}
        st.session_state[idx_key] = 0

    current_index = st.session_state[idx_key]

    # If all files done → return
    if current_index >= len(labels):
        return st.session_state[dfs_key]

    label = labels[current_index]

    uploaded_file = st.file_uploader(
        f"Upload {label} file:",
        type=["csv", "xlsx", "xls"],
        key=f"{key_prefix}_uploader_{current_index}"
    )

    if uploaded_file:
        try:
            # Example special rule for LEAVE file
            if label == "LEAVE":
                df = pd.read_csv(uploaded_file, skiprows=6, encoding="windows-1252")
            elif uploaded_file.name.lower().endswith(".csv"):
                try:
                    df = pd.read_csv(uploaded_file, encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(uploaded_file, encoding="latin-1")
            else:
                df = pd.read_excel(uploaded_file)

            # Save and move to next step
            st.session_state[dfs_key][label] = df
            st.session_state[idx_key] += 1
            st.rerun()

        except Exception as e:
            st.error(f"❌ Failed to read {uploaded_file.name}: {e}")

    return st.session_state[dfs_key]

def merge_files(df_in, df_out, no_working_days):
    total_days = len(calculate_working_days(df_in))
    cols_in = [col for col in df_in.columns if col.startswith('clock_in_') and 'nan' not in col]
    cols_out = [col for col in df_out.columns if col.startswith('clock_out_') and 'nan' not in col]

    late_df = calculate_late(df_in, cols_in)
    early_df = calculate_early(df_out, cols_out)
    holiday_cols = detect_holidays(df_in)  # detects holidays from clock-in data

    merged_data = []

    for i in range(len(df_in)):
        emp_id = df_in.loc[i, 'Emp ID']
        name = df_in.loc[i, 'Names']
        #present = df_in.loc[i, 'Present']

        late_flags = [
            col.replace('clock_in_', '')
            for col in cols_in
            if late_df.loc[i, col] == 'Late' and col not in holiday_cols
        ]

        in_date_keys = [col.replace('clock_in_', '') for col in cols_in]
        out_col_map = {col.replace('clock_out_', ''): col for col in cols_out}

        designation = df_in.loc[i, 'Designation'] if 'Designation' in df_in.columns else ''

        early_flags = []
        half_day_flags = []
        morning_abs = []
        afternoon_abs = []

        for date in in_date_keys:
            col_in = f'clock_in_{date}'
            col_out = f'clock_out_{date}'

            if col_in in holiday_cols or col_out in holiday_cols:
                continue  # Skip holidays

            in_val = str(df_in.loc[i, col_in]) if col_in in df_in.columns else '0'
            out_val = str(df_out.loc[i, col_out]) if col_out in df_out.columns else '0'

            try:
                clock_in = datetime.strptime(in_val, '%H:%M:%S') if in_val != '0' else None
            except:
                clock_in = None
            try:
                clock_out = datetime.strptime(out_val, '%H:%M:%S') if out_val != '0' else None
            except:
                clock_out = None

            # --- NEW LOGIC FOR DRIVER DESIGNATION ---
            if designation == 'Driver':
                # If a Driver has at least one punch, consider it a full present day.
                if not clock_in and not clock_out:
                    # No punches at all, considered fully absent for the day
                    morning_abs.append(date)
                    afternoon_abs.append(date)
                # else: If there's at least one punch, do not add to morning_abs, afternoon_abs, half_day_flags
                continue # Skip the rest of the standard half-day logic for drivers
            # --- END NEW LOGIC FOR DRIVER DESIGNATION ---

            # Default full absence
            if not clock_in and not clock_out:
                morning_abs.append(date)
                afternoon_abs.append(date)
                continue

            # Half-day logic
            if not clock_in and clock_out:
                morning_abs.append(date)
                half_day_flags.append(date)
            elif clock_in and not clock_out:
                afternoon_abs.append(date)
                half_day_flags.append(date)
            else:
                if clock_in and clock_in > datetime.strptime('10:30:00', '%H:%M:%S'):
                    morning_abs.append(date)
                    half_day_flags.append(date)

                if clock_out:
                    if datetime.strptime('12:15:00', '%H:%M:%S') <= clock_out < datetime.strptime('15:30:00', '%H:%M:%S'):
                        afternoon_abs.append(date)
                        half_day_flags.append(date)

                # Early leave if before threshold
                if clock_out and clock_out < datetime.strptime('15:45:00', '%H:%M:%S'):
                    early_flags.append(date)

        # Final adjustments
        morning_set = set(morning_abs)
        afternoon_set = set(afternoon_abs)
        day_abs = list(morning_set & afternoon_set)

        morning_abs = list(morning_set - set(day_abs))
        afternoon_abs = list(afternoon_set - set(day_abs))

        merged_data.append({
            'Emp ID': emp_id,
            'Names': name,
            #'Present': present,
            'late_flags': late_flags,
            'early_flags': early_flags,
            'half_day_flags': half_day_flags,
            'AM_abs': morning_abs,
            'PM_abs': afternoon_abs,
            'days_abs': day_abs,
            'No_of_AM_abs': len(morning_abs),
            'No_of_PM_abs': len(afternoon_abs),
            'No_of_late': len(late_flags),
            'No_of_day_abs': len(day_abs),
        })

    df = pd.DataFrame(merged_data)
    df = drop_columns_by_prefix(df, 'Unnamed')
    df.fillna(0, inplace=True)
    columns_to_sum = ['No_of_AM_abs','No_of_PM_abs','No_of_day_abs']
    df = weighted_sum_and_replace_columns(df, columns_to_sum, 'Absent', [0.5,0.5,1.0])
    df['Working Days'] = no_working_days
    df['Absent'] = df['Working Days'] - (total_days - df['Absent'])
    df['Present'] = no_working_days - df['Absent'] 
    return df

def split_file(df):
    dates = calculate_date_month(df)
    gap = 13

    idx_name = list(range(4, len(df), gap))
    idx_in = list(range(7, len(df), gap))
    idx_out = list(range(8, len(df), gap))

    df_bio = df.iloc[idx_name].copy()
    df_in = df.iloc[idx_in].copy()
    df_out = df.iloc[idx_out].copy()

    # Assign dynamic column names
    if len(dates) == df_in.shape[1] == df_out.shape[1]:
        df_in.columns = [f'clock_in_{d}' for d in dates]
        df_out.columns = [f'clock_out_{d}' for d in dates]
    else:
        raise ValueError("Mismatch between extracted dates and clock columns")

    # Drop any spurious nan columns
    df_in = df_in.loc[:, ~df_in.columns.str.contains("nan", case=False)]
    df_out = df_out.loc[:, ~df_out.columns.str.contains("nan", case=False)]

    # Biometric info cleanup
    df_bio = df_bio.rename(columns={
        'Monthly Attendance Summary': 'Emp ID',
        'Unnamed: 2': 'Names',
        'Unnamed: 7': 'Present',
    })

    # Reset indexes
    for d in (df_bio, df_in, df_out):
        d.reset_index(drop=True, inplace=True)

    # Combine
    df_all = pd.concat([df_bio, df_in, df_out], axis=1).fillna(0)
    df_all = drop_columns_by_prefix(df_all, "Unnamed")
    df_all.drop(columns="Present", axis=1, inplace=True, errors="ignore")

    return df_all, pd.concat([df_bio, df_in], axis=1).fillna(0), pd.concat([df_bio, df_out], axis=1).fillna(0)


# This function calcualtes late entries
# -------------------- Function: Calculate Late Entries --------------------
def calculate_late(df, cols_in):
    def classify(clock_in_str, emp_id):
        if str(clock_in_str) == '0':
            return 'Absent'
        try:
            clock_in = datetime.strptime(str(clock_in_str), '%H:%M:%S')
            threshold = datetime.strptime('09:25:00', '%H:%M:%S') if emp_id in LATE_ALLOWED_IDS else datetime.strptime('08:45:00', '%H:%M:%S')
            return 'Late' if clock_in > threshold else 'On Time'
        except:
            return 'Invalid'

    return pd.DataFrame({
        col: df.apply(lambda row: classify(row[col], row['Emp ID']), axis=1)
        for col in cols_in
    })


# NEW
def calculate_early(df, cols_out):
    """
    Flags early leave, absent, on-time, and holidays for each employee.

    Parameters
    ----------
    df : pd.DataFrame
        Attendance dataframe with clock_out columns.
    cols_out : list[str]
        Columns like ['clock_out_08_01', 'clock_out_08_02', ...].

    Returns
    -------
    pd.DataFrame
        Flags per employee per day with values:
        'Holiday', 'Absent', 'Early Leave', 'On Time', or 'Invalid'.
    """
    threshold = datetime.strptime("15:45:00", "%H:%M:%S")
    early_leave_map = {}

    # --- Step 1: Detect Holiday columns (>= 90% leave early) ---
    for col in cols_out:
        times = pd.to_datetime(
            df[col].astype(str).replace("0", pd.NA),
            errors="coerce",
            format="%H:%M:%S"
        )
        total_count = times.notna().sum()
        early_count = (times < threshold).sum()

        if total_count > 0 and (early_count / total_count) >= 0.9:
            early_leave_map[col] = "Holiday"
        else:
            early_leave_map[col] = "Normal"

    # --- Step 2: Flag per row ---
    result = pd.DataFrame(index=df.index)

    for col in cols_out:
        flags = []
        holiday_status = early_leave_map[col]

        if holiday_status == "Holiday":
            result[col] = "Holiday"
            continue

        for val in df[col]:
            if str(val) == "0" or pd.isna(val):
                flags.append("Absent")
            else:
                try:
                    clock_out = datetime.strptime(str(val), "%H:%M:%S")
                    if clock_out < threshold:
                        flags.append("Early Leave")
                    else:
                        flags.append("On Time")
                except Exception:
                    flags.append("Invalid")
        result[col] = flags

    return result

def calculate_working_days(df, threshold=0.95):
    """
    Identify valid working days from biometric data by excluding dates 
    where the absentee ratio (NaN or '0') is >= threshold.

    Parameters:
    - df (pd.DataFrame): Biometric clock-in data.
    - threshold (float): Max absentee ratio to still count as working (default 0.95).

    Returns:
    - List[str]: Working days in 'MM_DD' format.
    """
    # Extract relevant clock_in columns
    clock_in_cols = [col for col in df.columns if col.startswith("clock_in_")]
    if not clock_in_cols:
        return []

    total_employees = len(df)

    # ✅ Vectorized: no .str at all
    values = df[clock_in_cols].astype(str)
    absent_mask = values.isna() | values.eq("0")

    # Ratio of absentees per column
    absent_ratio = absent_mask.sum(axis=0) / total_employees

    # Columns where absentee ratio < threshold → working days
    working_days = [
        col.replace("clock_in_", "") 
        for col in clock_in_cols 
        if absent_ratio[col] < threshold
    ]

    return working_days



# this detect holidays
def detect_holidays(df_clock_in, threshold=0.9):
    """
    Detect holidays in biometric data by marking dates (columns) 
    where the absentee ratio is >= threshold.

    Parameters:
    - df_clock_in (pd.DataFrame): Clock-in data.
    - threshold (float): Ratio of absentees required to mark as holiday (default 0.9).

    Returns:
    - List[str]: Columns considered holidays.
    """
    clock_in_cols = [col for col in df_clock_in.columns if col.startswith("clock_in_")]
    if not clock_in_cols:
        return []

    total_employees = len(df_clock_in)

    # Absent if NaN or '0'
    absent_mask = df_clock_in[clock_in_cols].isna() | df_clock_in[clock_in_cols].astype(str).eq("0")

    # Ratio of absentees per column
    absent_ratio = absent_mask.sum(axis=0) / total_employees

    # Columns where absentee ratio ≥ threshold → holidays
    holiday_cols = [col for col in clock_in_cols if absent_ratio[col] >= threshold]

    return holiday_cols

def drop_columns_by_prefix(df, prefixes):
    if isinstance(prefixes, str):
        prefixes = [prefixes]
    return df.loc[:, ~df.columns.str.startswith(tuple(prefixes))]

def weighted_sum_and_replace_columns(df, cols, new_col, weights):
    if len(cols) != len(weights):
        raise ValueError("Length mismatch between cols and weights")
    df[new_col] = np.dot(df[cols], weights)
    return df.drop(columns=cols)

def calculate_date_month(df, date_row_idx=6):
    """
    Extract full date labels (e.g., '3_01', '3_02', ..., '4_01') from a biometric DataFrame.

    Assumes:
    - Date range string is in the first cell of the first row: 'March-01-2024 To April-01-2024'
    - Raw day numbers are in `date_row_idx` (default 6).
    """

    # --- Step 1: Extract and parse date range ---
    date_range = str(df.iloc[0, 0])
    try:
        start_date, end_date = date_range.split(" To ")
        start_month = datetime.strptime(start_date.split("-")[0].strip(), "%B").month
        end_month = datetime.strptime(end_date.split("-")[0].strip(), "%B").month
        month_numbers = [start_month, end_month]
    except Exception as e:
        raise ValueError(f"Invalid date range format in first cell: {date_range}") from e

    # --- Step 2: Build date labels ---
    raw_dates = df.iloc[date_row_idx]
    dates_full = []
    month_index = 0
    prev_day = 0

    for item in raw_dates:
        try:
            day = int(str(item).strip())
        except ValueError:
            # Non-numeric (e.g., NaN, 'Clock In')
            dates_full.append("nan")
            continue

        # Detect month change
        if day < prev_day and month_index < len(month_numbers) - 1:
            month_index += 1

        prev_day = day
        full_date = f"{month_numbers[month_index]}_{day:02d}"
        dates_full.append(full_date)

    return dates_full

def get_attendance_data(label: str, kind: str = "all"):
    """
    Retrieve attendance data from session_state.

    Parameters
    ----------
    label : str
        One of ["GIMT", "GIPS", "ADMIN", "LEAVE", "EXEMPTED"].
    kind : str
        - For GIMT, GIPS, ADMIN → one of ["all", "in", "out"]
        - For LEAVE, EXEMPTED → use "raw"

    Returns
    -------
    pd.DataFrame or None
    """
    splits = st.session_state.get("attendance_splits", {})
    if label not in splits:
        return None

    return splits[label].get(kind)

def move_columns(df, col_index_map):
    cols = list(df.columns)
    for col, new_index in sorted(col_index_map.items(), key=lambda x: x[1]):
        if col in cols:
            cols.insert(new_index, cols.pop(cols.index(col)))
    return df[cols]  # <-- Ensure it returns a DataFrame


def weighted_sum_and_replace_columns(
    df: pd.DataFrame,
    columns_to_sum: list,
    new_column_name: str,
    weights: list,
    fillna=0,
    drop: bool = True,
):
    """
    Compute a weighted sum of multiple columns, create a new column, 
    and optionally drop originals.

    Args:
        df : pd.DataFrame
            Input DataFrame
        columns_to_sum : list[str]
            Columns to combine
        new_column_name : str
            Name of the new weighted column
        weights : list[float]
            Weights matching the columns
        fillna : scalar, default 0
            Value to fill NaNs before computation
        drop : bool, default True
            Whether to drop the original columns after creating the weighted sum

    Returns:
        pd.DataFrame
    """
    # --- Validation ---
    if len(columns_to_sum) != len(weights):
        raise ValueError("Length of columns_to_sum and weights must match.")

    missing = [col for col in columns_to_sum if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns in DataFrame: {missing}")

    # --- Weighted sum ---
    arr = df[columns_to_sum].fillna(fillna).to_numpy(dtype=float)
    weighted = np.dot(arr, np.array(weights, dtype=float))
    df[new_column_name] = weighted

    # --- Drop originals if requested ---
    if drop:
        df.drop(columns=columns_to_sum, inplace=True)

    return df

def calculate_leave_summary_with_wd_leaves(df, working_days_list):
    df = df.copy()
    df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

    # Normalize column names
    rename_map = {
        "Employee ID": "Emp ID",
        "Name": "Name",
        "Leave Type": "Leave Type",
        "From Date": "From Date",
        "To Date": "To Date",
        "Status": "Status",
        "Total Days": "Total Days",
    }
    df.rename(columns={c: rename_map[c] for c in rename_map if c in df.columns}, inplace=True)

    # Approved only
    df = df[df["Status"] == "Approved"].copy()

    # Build working-day lookup
    current_year = datetime.now().year
    working_days_set = {
        datetime(current_year, int(m), int(d)).date()
        for m, d in (wd.split("_") for wd in working_days_list if "_" in wd)
    }

    # Normalize dates
    df["From Date"] = pd.to_datetime(df["From Date"], dayfirst=True, errors="coerce")
    df["To Date"] = pd.to_datetime(df["To Date"], dayfirst=True, errors="coerce")
    df["Total Days"] = pd.to_numeric(df["Total Days"], errors="coerce").fillna(0)

    # Filter out unwanted leave types
    exclude = ["Extraordinary Leave", "Casual Leave"]
    df = df[~df["Leave Type"].isin(exclude)].copy()

    # Expand leave spans
    rows = []
    for _, row in df.iterrows():
        emp_id = row["Emp ID"]
        ltype = row["Leave Type"]
        days = row["Total Days"]
        if days == 0.5:  # half-day
            if row["From Date"].date() in working_days_set:
                rows.append((emp_id, 0.5))
        else:
            if pd.notnull(row["From Date"]) and pd.notnull(row["To Date"]):
                rng = pd.date_range(row["From Date"], row["To Date"], freq="D")
                wd_count = sum(1 for d in rng if d.date() in working_days_set)
                rows.append((emp_id, wd_count))

    # Aggregate WD leaves
    wd_leaves = pd.DataFrame(rows, columns=["Emp ID", "WD_leave"])
    wd_leaves = wd_leaves.groupby("Emp ID", as_index=False)["WD_leave"].sum()

    # Summarize leave types
    leave_summary = df.groupby(["Emp ID", "Name", "Leave Type"], as_index=False)["Total Days"].sum()
    leave_summary = leave_summary.pivot(index=["Emp ID", "Name"], columns="Leave Type", values="Total Days").fillna(0).reset_index()

    # Merge
    final = leave_summary.merge(wd_leaves, on="Emp ID", how="left").fillna({"WD_leave": 0})
    final.rename(columns={"WD_leave": "Total WD leaves"}, inplace=True)

    return final

def calculate_working_days(df, threshold=0.95):
    """
    Identify valid working days from biometric data by excluding dates where
    >= threshold proportion of employees are absent.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with biometric clock-in data.
    threshold : float, default 0.95
        Percentage of absentees to mark a day as non-working.

    Returns
    -------
    list[str]
        Working days in 'MM_DD' format.
    """
    clock_in_cols = [c for c in df.columns if c.startswith("clock_in_")]
    if not clock_in_cols:
        return []

    total_employees = len(df)
    # Boolean mask: absent if value is NaN or '0'
    absent_mask = (df[clock_in_cols].isna()) | (df[clock_in_cols].astype(str).str.strip() == "0")

    # Absent ratio per column
    absent_ratio = absent_mask.sum(axis=0) / total_employees

    # Keep days below threshold
    working_cols = absent_ratio[absent_ratio < threshold].index
    working_days = [col.replace("clock_in_", "") for col in working_cols]

    return working_days
