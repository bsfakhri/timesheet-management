import streamlit as st
import pandas as pd
from datetime import datetime
import calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json

# Debugging for initialization
def __init__(self):
    st.write("Starting initialization...")

    # Debug environment variables
    st.write("Checking environment variables...")
    st.write("TIMESHEET_SHEET_ID exists:", bool(st.secrets.get('TIMESHEET_SHEET_ID')))
    st.write("TEACHERS_SHEET_ID exists:", bool(st.secrets.get('TEACHERS_SHEET_ID')))
    st.write("GOOGLE_SHEETS_CREDENTIALS exists:", bool(st.secrets.get('gcp_service_account')))

    try:
        st.set_page_config(
            page_title="Timesheet Management System",
            layout="centered",
            initial_sidebar_state="collapsed"
        )
        st.write("Page config set successfully")

        if 'current_page' not in st.session_state:
            st.session_state.current_page = 'main'
            st.write("Session state initialized")

        self._set_custom_css()
        st.write("Custom CSS set")

        st.write("Initializing Google Sheets...")
        self.sheets_service = self._initialize_google_sheets()
        st.write("Google Sheets initialized")

        self.timesheet_sheet_id = st.secrets["TIMESHEET_SHEET_ID"]
        self.teachers_sheet_id = st.secrets["TEACHERS_SHEET_ID"]
        st.write("Sheet IDs loaded")

    except Exception as e:
        st.error(f"Initialization error: {str(e)}")
        raise e

class TimesheetApp:
    def __init__(self):
        st.set_page_config(
            page_title="Timesheet Management System",
            layout="centered",
            initial_sidebar_state="collapsed"
        )

        if 'current_page' not in st.session_state:
            st.session_state.current_page = 'main'

        self._set_custom_css()
        self.sheets_service = self._initialize_google_sheets()
        self.timesheet_sheet_id = st.secrets["TIMESHEET_SHEET_ID"]
        self.teachers_sheet_id = st.secrets["TEACHERS_SHEET_ID"]

    @staticmethod
    @st.cache_data(ttl=3600)  # Cache CSS for 1 hour
    def _set_custom_css():
        """Set custom CSS with caching to avoid reloading"""
        st.markdown("""
            <style>
            .big-font { font-size: 24px !important; font-weight: bold; }
            .stButton>button { width: 100%; height: 50px; font-size: 18px; margin: 5px 0; border-radius: 10px; }
            .main-header { display: flex; align-items: center; gap: 10px; padding: 10px 0; }
            .status-active { color: #28a745; font-weight: bold; }
            .status-partial { color: #ffc107; font-weight: bold; }
            </style>
        """, unsafe_allow_html=True)

    @staticmethod
    @st.cache_resource
    def _initialize_google_sheets():
        """Initialize and cache Google Sheets service connection"""
        try:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            return build('sheets', 'v4', credentials=credentials)
        except Exception as e:
            st.error(f"Error initializing Google Sheets: {str(e)}")
            raise

    @st.cache_data(ttl=5)  # Cache sheet data for 5 seconds
    def read_sheet_to_df(self, sheet_id, range_name):
        """Read and cache sheet data with 5-second TTL"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])
            if not values:
                return pd.DataFrame()

            df = pd.DataFrame(values[1:], columns=values[0])
            if 'teacher_id' in df.columns:
                df['teacher_id'] = df['teacher_id'].astype(str)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            if 'clock_out' in df.columns:
                df['clock_out'] = df['clock_out'].fillna('')

            df = df.replace(['', 'None', 'NaN', 'nan'], '')
            return df

        except Exception as e:
            st.error(f"Error reading Google Sheet: {str(e)}")
            return pd.DataFrame()

    def main_page(self):
        """Main page of the application"""
        st.markdown("""
            <div class="main-header">
                <span style='font-size: 30px;'>⏰</span>
                <span class="big-font">Timesheet Management System</span>
            </div>
        """, unsafe_allow_html=True)

        teacher_id = st.text_input(
            "Enter ITS",
            placeholder="Enter ITS ID",
            label_visibility="collapsed"
        ).strip()

        programs = ["Select Program", "Rawdat", "Sigaar", "Mukhayyam", "Kibaar", "Camp"]
        program = st.selectbox(
            "Choose Program",
            programs,
            label_visibility="collapsed"
        )

        if teacher_id:
            self.check_active_session.clear()
            has_active, active_program = self.check_active_session(teacher_id)
            if has_active:
                st.warning(f"⚠️ Active session in program: {active_program}")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🕐 Clock In", use_container_width=True):
                if self.handle_clock_in(teacher_id, program):
                    st.success(f"Clocked in successfully at {datetime.now().strftime('%I:%M %p')}")

        with col2:
            if st.button("🕐 Clock Out", use_container_width=True):
                if self.handle_clock_out(teacher_id, program):
                    st.success(f"Clocked out successfully at {datetime.now().strftime('%I:%M %p')}")

        with col3:
            if st.button("📋 History", use_container_width=True):
                if teacher_id:
                    if self.get_teacher_info(teacher_id):
                        st.session_state.current_page = 'history'
                        st.session_state.history_teacher_id = teacher_id
                        st.rerun()
                    else:
                        st.error("Invalid ITS ID")
                else:
                    st.error("Please enter ITS ID")

    def run(self):
        """Main application entry point"""
        if st.session_state.current_page == 'main':
            self.main_page()
        elif st.session_state.current_page == 'history':
            self.show_history_page(st.session_state.get('history_teacher_id', ''))

if __name__ == "__main__":
    app = TimesheetApp()
    app.run()
