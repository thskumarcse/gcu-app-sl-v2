import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import altair as alt
from utility import connect_gsheet

# --- GOOGLE SHEETS CONNECTION ---
# This function is cached to prevent re-running on every page reload.


def app():
    st.header("Admit Card")
    try:
        # Step 1: connect client
        client = connect_gsheet()

        # Step 2: open sheet by ID
        sh = client.open_by_key(st.secrets["my_secrets"]["sheet_id"])

     

    except Exception as e:
        st.error(f"An error occurred: {e}")
        return

        
