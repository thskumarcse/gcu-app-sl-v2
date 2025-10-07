import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime, date
import re



# ========== Google Sheets Helper ==========
# We will use st.cache_resource to cache the connection


# this is working for deployement using secretes.toml
def connect_gsheet():
    """
    Connects to Google Sheets using Streamlit secrets.
    Returns a gspread client object.
    """
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])

        # fix literal "\n" if present
        if "\\n" in creds_dict["private_key"]:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(creds)
        return client

    except Exception as e:
        st.error(f"Failed to connect to Google Sheets. Error: {e}")
        st.stop()


# 🔹 Initialize a global gspread client when this file is imported

try:
    gs_client = connect_gsheet()
except Exception as e:
    gs_client = None
    st.error(f"Global gs_client not initialized: {e}")


# this is old one without create_if_missing
def get_worksheet_old(client, sheet_id, worksheet_name):
    
    #Returns a specific worksheet object from the client connection.
    #Includes error handling for missing spreadsheets or worksheets.
    
    try:
        return client.open_by_key(sheet_id).worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{worksheet_name}' not found. Please check the worksheet name.")
        st.stop()
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Spreadsheet with key '{sheet_id}' not found. Please check the sheet ID.")
        st.stop()
    except Exception as e:
        st.error(f"An unexpected error occurred while accessing the sheet: {e}")
        st.stop()

        
def get_worksheet(client, sheet_id, worksheet_name, create_if_missing=False, header=None):
    """
    Returns a specific worksheet object from the client connection.
    Can create the worksheet with a header if it doesn't exist.
    
    Args:
        client: gspread client object.
        sheet_id (str): Google Sheet ID.
        worksheet_name (str): Name of the worksheet/tab.
        create_if_missing (bool): If True, creates the worksheet if not found.
        header (list): If provided, adds this header row when creating a new worksheet.
    """
    try:
        return client.open_by_key(sheet_id).worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        if create_if_missing:
            st.warning(f"Worksheet '{worksheet_name}' not found. Creating it...")
            sh = client.open_by_key(sheet_id)
            ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=20)
            if header:
                ws.append_row(header)
            return ws
        else:
            st.error(f"Worksheet '{worksheet_name}' not found. Please check the name.")
            st.stop()
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Spreadsheet with key '{sheet_id}' not found. Please check the sheet ID.")
        st.stop()
    except Exception as e:
        st.error(f"An unexpected error occurred while accessing the sheet: {e}")
        st.stop()

        


def get_dataframe(client, sheet_id, worksheet_name):
    """
    Reads data from a Google Sheet into a DataFrame.
    """
    ws = get_worksheet(client, sheet_id, worksheet_name)
    data = ws.get_all_records()
    return pd.DataFrame(data)

def append_row(client, sheet_id, worksheet_name, row):
    """
    Appends a row to a Google Sheet.
    """
    ws = get_worksheet(client, sheet_id, worksheet_name)
    ws.append_row(row)

# ========== UI Helpers ==========
def small_header(text, size=16):
    st.markdown(
        f"<p style='font-size:{size}px; font-weight:bold; margin:0'>{text}</p>",
        unsafe_allow_html=True
    )

def pretty_print_record(row, expand_state, exclude_cols=["Grade", "Subject", "Date"]):
    """
    Display a single record in a collapsible expander with polished header → value layout.
    """
    title = f"{row.get('Grade','')} - {row.get('Subject','')} ({row.get('Date','')})"
    with st.expander(title, expanded=expand_state):
        st.markdown(
            "<div style='background-color:#f9f9f9; padding:15px; border-radius:10px; "
            "box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-bottom:15px;'>",
            unsafe_allow_html=True
        )
        for col, val in row.items():
            if col not in exclude_cols:
                st.markdown(
                    f"""
                    <div style='display: flex; flex-wrap: wrap; padding:6px 0; border-bottom:1px solid #eee;'>
                        <div style='flex: 0 0 140px; text-align:right; font-weight:600; color:#333;'>{col}:</div>
                        <div style='flex: 1; text-align:left; margin-left:10px; color:#555;'>{val}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        st.markdown("</div>", unsafe_allow_html=True)

def expand_collapse_controls():
    """
    Returns True if all records should be expanded, False otherwise.
    """
    if "expand_all" not in st.session_state:
        st.session_state.expand_all = False

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔽 Expand All"):
            st.session_state.expand_all = True
    with col2:
        if st.button("🔼 Collapse All"):
            st.session_state.expand_all = False

    return st.session_state.expand_all

# ========== Responsive Helpers ==========
def responsive_filters(*filter_widgets, breakpoint=768):
    """
    Arranges Streamlit filter widgets in a row for large screens
    and stacks them vertically on small screens.
    `filter_widgets` is a list of callables that return a Streamlit widget.
    """
    width = st.session_state.get("screen_width", 1024)
    values = []
    if width > breakpoint:
        cols = st.columns(len(filter_widgets))
        for col, widget_func in zip(cols, filter_widgets):
            with col:
                values.append(widget_func())
    else:
        for widget_func in filter_widgets:
            values.append(widget_func())
    return values

def styled_dataframe(df):
    """
    Returns a dataframe styled for smaller screens with readable fonts.
    """
    return df.style.set_table_styles([
        {"selector": "th", "props": [("font-size", "12px")]},
        {"selector": "td", "props": [("font-size", "12px")]}
    ])

def detect_screen_width():
    """
    Detects the current window width and stores it in st.session_state['screen_width'].
    
    NOTE: This is a complex pattern and may not be reliable in all environments.
    A simpler approach is to rely on Streamlit's dynamic columns.
    """
    if "screen_width" not in st.session_state:
        st.session_state.screen_width = 1024
        
        js_code = """
        <script>
        window.parent.postMessage({type: 'streamlit:setComponentValue', value: window.innerWidth, id: 'screen_width'}, '*');
        </script>
        """
        components.html(js_code)
        


def preprocess_date(value):
    """
    Normalizes a value to a datetime.date object.

    Handles pd.NaT, pd.Timestamp, datetime objects, and common date strings.
    
    Parameters:
    - value: The input value to convert.

    Returns:
    - A datetime.date object if conversion is successful, otherwise None.
    """
    # 1. Handle missing values (NaN, None, empty strings, pd.NaT)
    if pd.isna(value) or value is None or (isinstance(value, str) and not value.strip()):
        return None
    
    # 2. Handle datetime/timestamp objects first, as they are a subclass of date
    if isinstance(value, pd.Timestamp):
        return value.date()

    if isinstance(value, datetime):
        return value.date()

    # 3. Handle datetime.date objects directly
    if isinstance(value, date):
        return value

    # 4. Handle string values
    if isinstance(value, str):
        # Clean the string by stripping whitespace and common non-date characters
        cleaned_value = value.strip().replace("/", "-")
        
        # Define a list of common date formats to try
        date_formats = ["%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y"]

        for fmt in date_formats:
            try:
                # Attempt to parse the cleaned string with each format
                return datetime.strptime(cleaned_value, fmt).date()
            except (ValueError, TypeError):
                # If a ValueError occurs, continue to the next format
                continue
    
    # 5. Return None if the type is not handled
    return None

    
   
def get_authorized_pages_for_role(role: str):
    if role == "admin":
        # Admin should get everything - ALL modules and ALL pages
        return [
            "Attendance", "Feedback",
            "Transcript", "Mark Sheet", "Admit Card", "Results", "All Programs Results",
            "Mentor-Mentee", "Data Input", "Reports"
        ]
    elif role == "exam":
        return ["Transcript", "Mark Sheet", "Admit Card", "Results", "All Programs Results"]
    elif role == "hr":
        return ["Attendance", "Feedback"]
    elif role == "mentor_admin":
        return ["Mentor-Mentee", "Data Input", "Reports"]
    elif role == "hod":
        return ["Mentor-Mentee", "Data Input", "Reports"]
    elif role == "coordinator":
        return ["Mentor-Mentee", "Data Input", "Reports"]
    elif role == "mentor":
        return ["Mentor-Mentee", "Data Input", "Reports"]
    else:
        return []
    

def verify_dob(spreadsheet_dob, input_dob):
    """
    Compare a Date of Birth from spreadsheet with the one entered by user.

    Args:
        spreadsheet_dob: value from the sheet (string, datetime, Timestamp, or date)
        input_dob: datetime.date object from st.date_input

    Returns:
        bool: True if dates match, False otherwise
    """
    parsed_dob = None

    if pd.isna(spreadsheet_dob):
        return False

    # Convert based on type
    if isinstance(spreadsheet_dob, str):
        parsed_dob = pd.to_datetime(spreadsheet_dob, errors="coerce", dayfirst=True)
        if pd.notna(parsed_dob):
            parsed_dob = parsed_dob.date()
    elif isinstance(spreadsheet_dob, pd.Timestamp):
        parsed_dob = spreadsheet_dob.date()
    elif isinstance(spreadsheet_dob, datetime):
        parsed_dob = spreadsheet_dob.date()
    elif isinstance(spreadsheet_dob, date):
        parsed_dob = spreadsheet_dob
    else:
        parsed_dob = None

    # Compare
    return parsed_dob == input_dob

def fix_streamlit_layout(padding_top: str = "1rem", padding_sides: str = "1rem"):
    """
    Fixes Streamlit page layout by reducing the default padding/margins.

    Args:
        padding_top (str): CSS value for top padding (default: "1rem").
        padding_sides (str): CSS value for left/right padding (default: "1rem").
    """
    st.markdown(
        f"""
        <style>
            .block-container {{
                padding-top: {padding_top};
                padding-left: {padding_sides};
                padding-right: {padding_sides};
            }}
        </style>
        """,
        unsafe_allow_html=True
    )

def set_compact_theme():
    st.markdown(
        """
        <style>
        /* Global font size and family */
        html, body, [class*="css"] {
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px; /* Smaller base text */
        }

        /* Shrink headers */
        h1, h2, h3, h4, h5, h6 {
            font-size: 1.1em !important;
            font-weight: 600 !important;
            margin: 0.4em 0 !important;
        }

        /* Compact sidebar */
        section[data-testid="stSidebar"] {
            font-size: 12px !important;
        }

        /* Compact inputs (text, number, password, etc.) */
        input, textarea {
            font-size: 13px !important;
            padding: 4px 6px !important;
        }

        /* Compact dropdowns & selectbox */
        div[data-baseweb="select"] {
            font-size: 13px !important;
            min-height: 28px !important;
        }

        /* Compact radio & checkbox */
        div[data-baseweb="radio"], div[data-baseweb="checkbox"] {
            font-size: 13px !important;
            margin: 2px 0 !important;
        }

        /* Buttons */
        .stButton>button {
            font-size: 13px !important;
            padding: 4px 10px !important;
        }

        /* Dataframes & tables */
        .stDataFrame, .stTable {
            font-size: 12px !important;
        }

        /* --- Compact styling for option_menu --- */
        ul[data-testid="stSidebarNav"] li, 
        div[data-testid="stSidebar"] .nav-link,
        div[data-testid="stSidebar"] .nav-link-selected {
            font-size: 13px !important;
            padding: 4px 8px !important;
            white-space: normal !important;   /* allow wrapping */
            word-wrap: break-word !important; /* break long words */
            line-height: 1.2em !important;    /* tighter line spacing */
        }

        /* Reduce spacing between menu items */
        ul[data-testid="stSidebarNav"] li {
            margin: 2px 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
