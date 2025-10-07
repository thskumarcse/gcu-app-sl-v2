import streamlit as st
import pandas as pd
import bcrypt
import re
from utility import connect_gsheet, get_dataframe, get_worksheet, \
                    preprocess_date, verify_dob, fix_streamlit_layout, set_compact_theme
from datetime import datetime, date

# ==================== WARNING: DO NOT USE PLAIN-TEXT PASSWORDS IN PRODUCTION ====================
# This code now uses bcrypt for password hashing, which is a significant security improvement.
# Ensure that your `utility.py` functions correctly correctly handle the connection.
# ===============================================================================================

def validate_password(password):
    """
    Validate password strength.
    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."
    
    return True, ""

def validate_user_id(user_id):
    """
    Validate user ID format.
    Returns (is_valid, error_message)
    """
    if not user_id or not user_id.strip():
        return False, "User ID cannot be empty."
    
    if len(user_id) < 3:
        return False, "User ID must be at least 3 characters long."
    
    if not re.match(r"^[a-zA-Z0-9_-]+$", user_id):
        return False, "User ID can only contain letters, numbers, hyphens, and underscores."
    
    return True, ""

def reset_registration_state():
    """Reset registration-related session state variables."""
    st.session_state.can_set_password = False
    if "reg_user_id" in st.session_state:
        del st.session_state.reg_user_id
    if "reg_dob" in st.session_state:
        del st.session_state.reg_dob

def login():
    """
    Handles user login and registration with a Google Sheets backend.
    Returns True if the user is authenticated, False otherwise.
    """
    fix_streamlit_layout(padding_top="0.6rem") 
    set_compact_theme()
    st.markdown("<h2 style='color: #8b00a3; text-align: center;'>GCU</h2>", unsafe_allow_html=True)

    # --- Initialize session state ---
    if "can_set_password" not in st.session_state:
        st.session_state.can_set_password = False
    
    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0

    try:
        gs_client = connect_gsheet()
        df_users = get_dataframe(gs_client, st.secrets["my_secrets"]["sheet_id"], "users")
        
        df_users.rename(columns={"Emp Id": "User ID"}, inplace=True)
        df_users["User ID"] = df_users["User ID"].astype(str).str.strip()

        # Normalize DOB properly
        df_users['Date of Birth'] = df_users['Date of Birth'].apply(preprocess_date)
        df_users['DOB_normalized'] = pd.to_datetime(df_users['Date of Birth'])

        # ✅ Store in session_state for other pages
        st.session_state["df_users"] = df_users

    except Exception as e:
        st.error(f"Failed to connect to user database. Please check credentials. Error: {e}")
        st.stop()

    # --- If already logged in ---
    if st.session_state.get('authenticated'):
        return True

    # --- Mode selection ---
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        mode = st.radio("Select mode:", ["Login", "Register"], horizontal=True)

    # --- Login form ---
    if mode == "Login":
        with st.form("login_form"):
            st.markdown("<h3 style='color: #4a0072; text-align: center;'>Log-In</h3>", unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                user_id = st.text_input("User ID", key="login_user_id", placeholder="Enter your Employee ID")
            with col2:
                password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
            
            submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                # Input validation
                if not user_id or not password:
                    st.warning("Please enter both User ID and Password.")
                else:
                    # Rate limiting
                    if st.session_state.login_attempts >= 5:
                        st.error("Too many failed login attempts. Please try again later.")
                        return False
                    
                    user_record = df_users[df_users['User ID'].astype(str) == user_id]
                    if not user_record.empty:
                        stored_password_str = user_record.iloc[0]['Password']
                        if stored_password_str:
                            stored_hashed_password = stored_password_str.encode('utf-8')
                            if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password):
                                # Successful login
                                st.session_state.authenticated = True
                                st.session_state.user_id = user_id
                                st.session_state.role = user_record.iloc[0]['User Type']
                                st.session_state.current_user = user_record.iloc[0].to_dict()
                                st.session_state.login_attempts = 0  # Reset attempts on success
                                
                                st.success(f"Welcome, {user_record.iloc[0]['Name']} 👋")
                                st.rerun()
                            else:
                                st.session_state.login_attempts += 1
                                st.error("Incorrect password. Please try again.")
                        else:
                            st.error("This user has no password set. Please register.")
                    else:
                        st.session_state.login_attempts += 1
                        st.error("User ID not found.")

    elif mode == "Register":
        with st.form("register_form"):
            st.markdown("<h3 style='color: #4a0072; text-align: center;'>Register</h3>", unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                user_id = st.text_input("User ID", key="reg_user_id", placeholder="Enter your Employee ID")
            with col2:
                dob = st.date_input(
                    "Date of Birth", key="reg_dob", format="YYYY-MM-DD", 
                    min_value=date(1920, 1, 1), max_value=date.today()
                )
            
            check_user_submitted = st.form_submit_button("Verify Identity", use_container_width=True)
            
            if check_user_submitted:
                # Input validation
                user_id_valid, user_id_error = validate_user_id(user_id)
                if not user_id_valid:
                    st.error(user_id_error)
                    st.session_state.can_set_password = False
                elif dob is None:
                    st.warning("Please enter your Date of Birth.")
                    st.session_state.can_set_password = False
                else:
                    user_record = df_users[df_users['User ID'].astype(str) == user_id]
                    if user_record.empty:
                        st.error("User ID not found in the database. Please check the spelling.")
                        st.session_state.can_set_password = False
                    else:
                        spreadsheet_dob = user_record.iloc[0]['Date of Birth']
                        if spreadsheet_dob and verify_dob(spreadsheet_dob, dob):
                            st.success("✅ Identity verification successful! You can now set your password.")
                            st.session_state.can_set_password = True
                            st.session_state.verified_user_id = user_id
                        else:
                            st.error("❌ Incorrect Date of Birth. Please try again.")
                            st.session_state.can_set_password = False
            
            # Password setting section
            if st.session_state.get("can_set_password"):
                st.markdown("---")
                st.markdown("<h4 style='color: #4a0072;'>Set Your Password</h4>", unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    new_password = st.text_input("New Password", type="password", key="reg_new_password", 
                                               placeholder="Enter a strong password")
                with col2:
                    confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password", 
                                                   placeholder="Confirm your password")
                
                # Password strength indicator
                if new_password:
                    is_valid, error_msg = validate_password(new_password)
                    if is_valid:
                        st.success("✅ Password strength: Strong")
                    else:
                        st.warning(f"⚠️ {error_msg}")
                
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    update_password_submitted = st.form_submit_button("Update Password", type="primary", use_container_width=True)

                if update_password_submitted:
                    if not new_password or not confirm_password:
                        st.error("Please enter both password fields.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        is_valid, error_msg = validate_password(new_password)
                        if not is_valid:
                            st.error(error_msg)
                        else:
                            try:
                                hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                                user_id = st.session_state.get("verified_user_id", user_id)
                                row_index = df_users[df_users['User ID'].astype(str) == user_id].index[0]
                                gs_ws = get_worksheet(gs_client, st.secrets["my_secrets"]["sheet_id"], "users")
                                gs_row_number = row_index + 2
                                password_col_index = df_users.columns.get_loc('Password') + 1
                                gs_ws.update_cell(gs_row_number, password_col_index, hashed_password)
                                
                                st.success("🎉 Password updated successfully! You can now log in.")
                                reset_registration_state()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to update password: {e}")

    return st.session_state.get('authenticated', False)