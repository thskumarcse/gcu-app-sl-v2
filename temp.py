import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ==== CONFIG ====
SHEET_ID = "1HfGindCUh_ZxsrU9RuOfUb2qm6PWzDooOWBB3a95AgU"
WORKSHEET_NAME = "data"

# ==== GOOGLE SHEETS CONNECTION ====
@st.cache_resource
def connect_gsheet(sheet_id: str, worksheet_name: str):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)

    sh = client.open_by_key(sheet_id)
    ws = sh.worksheet(worksheet_name)
    return ws

# 🔹 Reusable custom header
def small_header(text, size=16):
    st.markdown(
        f"<p style='font-size:{size}px; font-weight:bold; margin:0'>{text}</p>",
        unsafe_allow_html=True
    )

def app():
    small_header("📊 View Data (Multiple Days)", size=14)

    try:
        ws = connect_gsheet(SHEET_ID, WORKSHEET_NAME)
        data = ws.get_all_records()   # fetch all rows as list of dicts

        if data:
            df = pd.DataFrame(data)

            # === Dropdowns ===
            grades = ["All"] + sorted(df["Grade"].dropna().unique().tolist())
            subjects = ["All"] + sorted(df["Subject"].dropna().unique().tolist())

            selected_grade = st.selectbox("Filter by Grade", grades)
            selected_subject = st.selectbox("Filter by Subject", subjects)

            # === Filtering ===
            filtered_df = df.copy()
            if selected_grade != "All":
                filtered_df = filtered_df[filtered_df["Grade"] == selected_grade]
            if selected_subject != "All":
                filtered_df = filtered_df[filtered_df["Subject"] == selected_subject]

            # === Remove Grade & Subject columns ===
            filtered_df = filtered_df.drop(columns=["Grade", "Subject"], errors="ignore")

            st.dataframe(filtered_df, use_container_width=True)
            
            # 🔄 Optional manual refresh button
            #if st.button("🔄 Refresh Data"):
            #    st.experimental_rerun()

        else:
            st.info("No data found in the sheet yet.")

    except Exception as e:
        st.error(f"❌ Error: {e}")


if __name__ == "__main__":
    app()
