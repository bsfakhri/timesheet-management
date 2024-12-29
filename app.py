import streamlit as st
import pandas as pd
from datetime import datetime
import os
import calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
import json

class TimesheetApp:
    def __init__(self):
        st.set_page_config(
            page_title="AL JAMEAH AL SAYFIYAH TRUST Timesheet",
            layout="centered",
            initial_sidebar_state="collapsed"
        )
        
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 'main'
            
        self._set_custom_css()
        load_dotenv()
        self.sheets_service = self._initialize_google_sheets()
        self.timesheet_sheet_id = st.secrets["TIMESHEET_SHEET_ID"]
        self.teachers_sheet_id = st.secrets["TEACHERS_SHEET_ID"]

    @staticmethod
    @st.cache_data(ttl=3600)  # Cache CSS for 1 hour
    def _set_custom_css():
        """Set custom CSS with caching"""
        st.markdown("""
            <style>
            .big-font {
                font-size: 24px !important;
                font-weight: bold;
            }
            .stButton>button {
                width: 100%;
                height: 50px;
                font-size: 18px;
                margin: 5px 0;
                border-radius: 10px;
            }
            .main-header {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 10px 0;
            }
            .status-active {
                color: #28a745;
                font-weight: bold;
            }
            .status-partial {
                color: #ffc107;
                font-weight: bold;
            }
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

    @st.cache_data(ttl=30)  # Cache sheet data for 30 seconds
    def read_sheet_to_df(_self, sheet_id, range_name):
        """Read and cache sheet data"""
        try:
            result = _self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return pd.DataFrame()
                
            df = pd.DataFrame(values[1:], columns=values[0])
            
            # Ensure consistent data types
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

    def get_program_cap(self, program):
        """Get the maximum hours cap for a program"""
        program_caps = {
            "Rawdat": 2.0,
            "Rawdat + Admin Work": 2.5,
            "Sigaar": 2.0,
            "Mukhayyam": 4.0,
            "Kibaar": 2.0,
            "Camp": 4.0
        }
        return program_caps.get(program, 2.0)  # Default to 2.0 if program not found

    def round_partial_hour(self, minutes):
        """Round minutes according to the specified rules"""
        if minutes <= 15:
            return 0.25
        elif minutes <= 30:
            return 0.50
        elif minutes <= 45:
            return 0.75
        else:
            return 1.0

    def adjust_hours(self, actual_hours, program):
        """
        Adjust hours based on program cap and rounding rules
        """
        program_cap = self.get_program_cap(program)
        
        # If exceeds cap, return cap
        if actual_hours > program_cap:
            return program_cap
            
        # Calculate whole hours and remaining minutes
        whole_hours = int(actual_hours)
        remaining_minutes = round((actual_hours - whole_hours) * 60)
        
        # Apply rounding rules for partial hour
        partial_hour = self.round_partial_hour(remaining_minutes)
        
        return float(whole_hours + partial_hour)
    def append_to_sheet(self, sheet_id, range_name, values):
        """Append values to Google Sheet"""
        try:
            body = {'values': values}
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            # Clear caches after successful append
            self.read_sheet_to_df.clear()
            self.check_active_session.clear()
            return True
        except Exception as e:
            st.error(f"Error appending to Google Sheet: {str(e)}")
            return False

    def update_sheet_cell(self, sheet_id, range_name, value):
        """Update specific cell in Google Sheet"""
        try:
            body = {'values': [[value]]}
            result = self.sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            # Clear caches after successful update
            self.read_sheet_to_df.clear()
            self.check_active_session.clear()
            return True
        except Exception as e:
            st.error(f"Error updating Google Sheet: {str(e)}")
            return False

    @st.cache_data(ttl=30)  # Cache teacher info for 30 seconds
    def get_teacher_info(_self, teacher_id):
        """Get and cache teacher information"""
        try:
            teachers_df = _self.read_sheet_to_df(_self.teachers_sheet_id, 'A:C')  # Modified to remove budgeted_hours column
            if not teachers_df.empty:
                teacher_id = str(teacher_id).strip()
                teachers_df['teacher_id'] = teachers_df['teacher_id'].astype(str).str.strip()
                teacher = teachers_df[teachers_df['teacher_id'] == teacher_id]
                if not teacher.empty:
                    return teacher.iloc[0].to_dict()
            return None
        except Exception as e:
            st.error(f"Error getting teacher info: {str(e)}")
            return None

    @st.cache_data(ttl=5)  # Cache active session check for 5 seconds
    def check_active_session(_self, teacher_id):
        """Check and cache active session status"""
        try:
            timesheet_df = _self.read_sheet_to_df(_self.timesheet_sheet_id, 'A:H')
            if timesheet_df.empty:
                return False, None
                
            teacher_id = str(teacher_id).strip()
            timesheet_df['teacher_id'] = timesheet_df['teacher_id'].astype(str).str.strip()
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # Ensure clock_out is properly handled
            timesheet_df['clock_out'] = timesheet_df['clock_out'].fillna('')
            
            active_session = timesheet_df[
                (timesheet_df['teacher_id'] == teacher_id) & 
                (timesheet_df['date'] == current_date) &
                (timesheet_df['clock_out'].str.strip() == '')
            ]
            
            if not active_session.empty:
                return True, active_session.iloc[0]['program']
            return False, None
            
        except Exception as e:
            st.error(f"Error checking active session: {str(e)}")
            return False, None

    def handle_clock_in(self, teacher_id, program):
        """Handle clock in with improved validation"""
        try:
            teacher_id = str(teacher_id).strip()
            
            if not teacher_id or program == "Select Program":
                st.error("Please enter ITS ID and select a program")
                return False
                
            if not self.get_teacher_info(teacher_id):
                st.error("Invalid ITS ID")
                return False
            
            # Clear cache and check active session
            self.check_active_session.clear()
            has_active, active_program = self.check_active_session(teacher_id)
            
            if has_active:
                st.error(f"Cannot clock in. You have an active session in program: {active_program}")
                return False
                
            timesheet_df = self.read_sheet_to_df(self.timesheet_sheet_id, 'A:H')
            
            current_date = datetime.now().strftime('%Y-%m-%d')
            current_time = datetime.now().strftime('%H:%M:%S')
            
            new_entry = [
                len(timesheet_df) + 1 if not timesheet_df.empty else 1,
                teacher_id,
                current_date,
                current_time,
                '',  # clock_out
                0,   # actual_hours
                0,   # adjusted_hours
                program
            ]
            
            success = self.append_to_sheet(
                self.timesheet_sheet_id, 
                'A:H', 
                [new_entry]
            )
            
            return success
            
        except Exception as e:
            st.error(f"Error during clock in: {str(e)}")
            return False

    def handle_clock_out(self, teacher_id, program):
        """Handle clock out with improved validation and caching"""
        try:
            teacher_id = str(teacher_id).strip()
            
            if not teacher_id:
                st.error("Please enter ITS ID")
                return False
                
            if not self.get_teacher_info(teacher_id):
                st.error("Invalid ITS ID")
                return False

            # Clear cache and check active session
            self.check_active_session.clear()
            has_active, active_program = self.check_active_session(teacher_id)
            
            if not has_active:
                st.error("No active clock-in found for today!")
                return False

            timesheet_df = self.read_sheet_to_df(self.timesheet_sheet_id, 'A:H')
            current_date = datetime.now().strftime('%Y-%m-%d')
            current_time = datetime.now()
            
            # Ensure consistent data types
            timesheet_df['teacher_id'] = timesheet_df['teacher_id'].astype(str).str.strip()
            timesheet_df['clock_out'] = timesheet_df['clock_out'].fillna('')
            
            mask = (
                (timesheet_df['teacher_id'] == teacher_id) & 
                (timesheet_df['date'] == current_date) &
                (timesheet_df['clock_out'].str.strip() == '')
            )
            
            active_sessions = timesheet_df[mask]
            
            if active_sessions.empty:
                st.error("No active clock-in found for today!")
                return False
            
            active_row = active_sessions.iloc[0]
            row_number = timesheet_df[mask].index[0] + 2
            
            if program != "Select Program" and program != active_row['program']:
                st.error(f"Program mismatch. You clocked in for {active_row['program']}")
                return False
            
            try:
                clock_in_time = datetime.strptime(f"{current_date} {active_row['clock_in']}", '%Y-%m-%d %H:%M:%S')
                actual_hours = (current_time - clock_in_time).total_seconds() / 3600
                adjusted_hours = self.adjust_hours(actual_hours, active_row['program'])
            except ValueError as e:
                st.error(f"Error calculating hours: {str(e)}")
                return False

            # Update all fields in a sequence
            success = all([
                self.update_sheet_cell(
                    self.timesheet_sheet_id,
                    f'E{row_number}',
                    current_time.strftime('%H:%M:%S')
                ),
                self.update_sheet_cell(
                    self.timesheet_sheet_id,
                    f'F{row_number}',
                    round(actual_hours, 2)
                ),
                self.update_sheet_cell(
                    self.timesheet_sheet_id,
                    f'G{row_number}',
                    round(adjusted_hours, 2)
                )
            ])
            
            return success
            
        except Exception as e:
            st.error(f"Error during clock out: {str(e)}")
            return False
        
    @staticmethod
    @st.cache_data(ttl=60)
    def format_clock_time(time_str):
        """Format clock time with caching"""
        try:
            if not time_str or pd.isna(time_str) or time_str == '' or time_str is None:
                return 'Active ⚡'
            parsed_time = datetime.strptime(str(time_str).strip(), '%H:%M:%S')
            return parsed_time.strftime('%I:%M %p')
        except Exception:
            return 'Invalid Time'
            
    @staticmethod
    @st.cache_data(ttl=60)
    def format_time_for_sorting(time_str):
        """Format time for sorting with caching"""
        try:
            if time_str == 'Active ⚡' or time_str == 'Invalid Time':
                return '23:59:59'
            return datetime.strptime(time_str, '%I:%M %p').strftime('%H:%M:%S')
        except Exception:
            return '00:00:00'

    @st.cache_data(ttl=30)
    def get_monthly_entries(_self, teacher_id, year, month):
        """Get and cache monthly entries"""
        try:
            timesheet_df = _self.read_sheet_to_df(_self.timesheet_sheet_id, 'A:H')
            if timesheet_df.empty:
                return pd.DataFrame()
            
            timesheet_df['date'] = pd.to_datetime(timesheet_df['date'], format='%Y-%m-%d')
            timesheet_df['teacher_id'] = timesheet_df['teacher_id'].astype(str).str.strip()
            
            mask = (
                (timesheet_df['teacher_id'] == str(teacher_id).strip()) &
                (timesheet_df['date'].dt.year == year) &
                (timesheet_df['date'].dt.month == month)
            )
            return timesheet_df[mask]
        except Exception as e:
            st.error(f"Error getting monthly entries: {str(e)}")
            return pd.DataFrame()

    def main_page(self):
        """Main page of the application"""
        st.markdown("""
            <div class="main-header">
                <span style='font-size: 30px;'>⏰</span>
                <span class="big-font">AL JAMEAH AL SAYFIYAH TRUST Timesheet</span>
            </div>
        """, unsafe_allow_html=True)

        teacher_id = st.text_input(
            "Enter ITS",
            placeholder="Enter ITS ID",
            label_visibility="collapsed"
        ).strip()
        
        programs = ["Select Program", "Rawdat","Rawdat + Admin Work", "Sigaar", "Mukhayyam", "Kibaar", "Camp"]
        program = st.selectbox(
            "Choose Program",
            programs,
            label_visibility="collapsed"
        )

        if teacher_id:
            # Clear cache before checking active session
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

    def show_history_page(self, teacher_id):
        """Show timesheet history page"""
        if st.button("← Back", key="back_button"):
            st.session_state.current_page = 'main'
            st.rerun()
            
        st.markdown("""
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 24px;">📅 Timesheet History</span>
            </div>
        """, unsafe_allow_html=True)
        
        teacher = self.get_teacher_info(teacher_id)
        if teacher:
            st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 10px; margin: 20px 0;">
                    <span style="font-size: 40px;">👤</span>
                    <div>
                        <div style="font-size: 24px;">{teacher_id} - {teacher['name']}</div>
                        <div style="color: gray;">Last 2 Months History</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            current_month = datetime.now().month
            current_year = datetime.now().year
            
            months = []
            for i in range(2):
                month = current_month - i
                year = current_year
                if month <= 0:
                    month += 12
                    year -= 1
                months.append((year, month))
            
            tabs = st.tabs([f"{calendar.month_name[m[1]]} {m[0]}" for m in months])
            
            for idx, (year, month) in enumerate(months):
                with tabs[idx]:
                    entries = self.get_monthly_entries(teacher_id, year, month)
                    if not entries.empty:
                        display_df = entries.copy()
                        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
                        display_df['clock_in'] = display_df['clock_in'].apply(self.format_clock_time)
                        display_df['clock_out'] = display_df['clock_out'].apply(self.format_clock_time)
                        
                        try:
                            display_df['sort_datetime'] = pd.to_datetime(
                                display_df['date'] + ' ' + display_df['clock_in'].apply(
                                    lambda x: self.format_time_for_sorting(x) if pd.notna(x) else '00:00:00'
                                ),
                                format='%Y-%m-%d %H:%M:%S'
                            )
                        except Exception as e:
                            st.error(f"Error creating sort datetime: {str(e)}")
                            display_df['sort_datetime'] = pd.to_datetime(display_df['date'])
                        
                        display_df = display_df.sort_values('sort_datetime', ascending=False)
                        columns_to_display = ['date', 'program', 'clock_in', 'clock_out', 'actual_hours', 'adjusted_hours']
                        display_df = display_df[columns_to_display]
                        
                        
                        
                        # Display the dataframe without scrolling
                        # Calculate height based on number of rows (approximately 35px per row plus 40px header)
                        height = len(display_df) * 35 + 40
                        st.dataframe(display_df, use_container_width=True, height=height)
                        
                        # Convert adjusted_hours to float and calculate total
                        display_df['adjusted_hours'] = pd.to_numeric(display_df['adjusted_hours'], errors='coerce')
                        total_adjusted_hours = display_df['adjusted_hours'].sum()
                        
                        # Display total with proper formatting
                        st.markdown(
                            f"""
                            <div style="text-align: right; padding: 10px; background-color: #f0f2f6; border-radius: 5px; margin-top: 10px;">
                                <strong>Total Adjusted Hours: {total_adjusted_hours:.2f}</strong>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        st.info(f"No entries for {calendar.month_name[month]} {year}")

    def run(self):
        """Main application entry point"""
        if st.session_state.current_page == 'main':
            self.main_page()
        elif st.session_state.current_page == 'history':
            self.show_history_page(st.session_state.get('history_teacher_id', ''))

if __name__ == "__main__":
    app = TimesheetApp()
    app.run()