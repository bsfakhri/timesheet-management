import streamlit as st
import pandas as pd
from datetime import datetime
import os
import calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
import json
# New imports for PDF generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
import base64
import pytz

class TimesheetApp:
    def __init__(self):
        """Initialize the Timesheet application with enhanced features"""
        st.set_page_config(
            page_title="AL JAMEAH AL SAYFIYAH TRUST Timesheet",
            layout="centered",
            initial_sidebar_state="collapsed"
        )
        
        # Initialize session state
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 'main'
        
        # Initialize PDF export state
        if 'pdf_download' not in st.session_state:
            st.session_state.pdf_download = None
            
        self._set_custom_css()
        load_dotenv()
        self.sheets_service = self._initialize_google_sheets()
        self.timesheet_sheet_id = st.secrets["TIMESHEET_SHEET_ID"]
        self.teachers_sheet_id = st.secrets["TEACHERS_SHEET_ID"]

    @staticmethod
    @st.cache_data(ttl=3600)  # Cache CSS for 1 hour
    def _set_custom_css():
        """Set custom CSS with additional styles for program totals and PDF export"""
        st.markdown("""
            <style>
            /* Base styles */
            .big-font {
                font-size: 24px !important;
                font-weight: bold;
            }
            
            /* Button styles */
            .stButton>button {
                width: 100%;
                height: 50px;
                font-size: 18px;
                margin: 5px 0;
                border-radius: 10px;
                transition: all 0.3s ease;
            }
            
            .stButton>button:hover {
                transform: translateY(-1px);
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            
            /* Header styles */
            .main-header {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 10px 0;
                border-bottom: 1px solid #eee;
                margin-bottom: 20px;
            }
            
            /* Status indicators */
            .status-active {
                color: #28a745;
                font-weight: bold;
                display: inline-flex;
                align-items: center;
                gap: 5px;
            }
            
            .status-active::before {
                content: "●";
                font-size: 12px;
            }
            
            .status-partial {
                color: #ffc107;
                font-weight: bold;
                display: inline-flex;
                align-items: center;
                gap: 5px;
            }
            
            .status-partial::before {
                content: "●";
                font-size: 12px;
            }
            
            /* Program summary styles */
            .program-summary {
                background-color: #f8f9fa;
                border-radius: 12px;
                padding: 24px;
                margin: 20px 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                border: 1px solid #e9ecef;
            }
            
            .program-summary h3 {
                color: #2c3e50;
                font-size: 1.25rem;
                font-weight: 600;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 2px solid #e9ecef;
            }
            
            .program-total {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 0;
                border-bottom: 1px solid #e9ecef;
                transition: background-color 0.2s ease;
            }
            
            .program-total:hover {
                background-color: #f1f3f5;
            }
            
            .program-total:last-child {
                border-bottom: none;
            }
            
            .program-name {
                font-weight: 500;
                color: #495057;
                font-size: 1.05rem;
            }
            
            .program-hours {
                font-weight: 600;
                color: #2c3e50;
                font-size: 1.05rem;
                background-color: #e9ecef;
                padding: 4px 12px;
                border-radius: 6px;
            }

            /* Total hours display */
            .total-hours {
                text-align: right;
                padding: 12px;
                background-color: #f8f9fa;
                border-radius: 0 0 8px 8px;
                border-top: 2px solid #e9ecef;
                font-weight: 600;
                color: #2c3e50;
                font-size: 1.1rem;
            }
            
            /* Export section styles */
            .export-section {
                margin: 24px 0;
                padding: 20px;
                background-color: #f8f9fa;
                border-radius: 12px;
                border: 1px solid #e9ecef;
                text-align: center;
            }
            
            .export-section p {
                color: #495057;
                margin-bottom: 15px;
            }
            # Add this to your existing CSS
            .export-button {
                background-color: #2c3e50;
                color: white;
                padding: 10px 15px;
                border-radius: 5px;
                text-align: center;
                font-weight: 500;
                margin: 10px 0;
                cursor: pointer;
                transition: all 0.3s ease;
            }

            .export-button:hover {
                background-color: #1a252f;
                transform: translateY(-1px);
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            
            .download-button {
                background-color: #28a745;
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                text-decoration: none;
                display: inline-block;
                margin: 10px 0;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.3s ease;
                border: none;
                box-shadow: 0 2px 4px rgba(40, 167, 69, 0.2);
            }
            
            .download-button:hover {
                background-color: #218838;
                transform: translateY(-1px);
                box-shadow: 0 4px 6px rgba(40, 167, 69, 0.3);
            }
            
            /* Additional utility classes */
            .text-muted {
                color: #6c757d;
            }
            
            .text-center {
                text-align: center;
            }
            
            .mt-4 {
                margin-top: 1rem;
            }
            
            .mb-4 {
                margin-bottom: 1rem;
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
# Part 2
    @st.cache_data(ttl=30)  # Cache sheet data for 30 seconds
    def read_sheet_to_df(_self, sheet_id, range_name):
        """Read and cache sheet data with enhanced error handling"""
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
            if 'adjusted_hours' in df.columns:
                df['adjusted_hours'] = pd.to_numeric(df['adjusted_hours'], errors='coerce')
            
            # Clean data
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
        Returns float value of adjusted hours
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
        """
        Append values to Google Sheet with enhanced error handling
        Returns bool indicating success
        """
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
        """
        Update specific cell in Google Sheet with enhanced error handling
        Returns bool indicating success
        """
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
        """
        Get and cache teacher information
        Returns dict with teacher details or None if not found
        """
        try:
            teachers_df = _self.read_sheet_to_df(_self.teachers_sheet_id, 'A:C')
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
        """
        Check and cache active session status
        Returns tuple (bool has_active, str active_program or None)
        """
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
        

# Part 3

    def handle_clock_in(self, teacher_id, program):
            """
            Handle clock in with improved validation and data consistency
            Returns bool indicating success
            """
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
                current_time = self.get_london_time().strftime('%H:%M:%S')
                
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
        """
        Handle clock out with improved validation and precise hour calculation
        Returns bool indicating success
        """
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
            current_time = self.get_london_time()
            
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
                # Parse the clock-in time as a naive datetime
                clock_in_time = datetime.strptime(f"{current_date} {active_row['clock_in']}", '%Y-%m-%d %H:%M:%S')
                
                # Make the current time naive for consistent comparison
                current_time_naive = current_time.replace(tzinfo=None)
                
                # Calculate hours as before
                actual_hours = (current_time_naive - clock_in_time).total_seconds() / 3600
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
        """
        Format clock time with enhanced handling of edge cases
        Returns formatted time string
        """
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
        """
        Format time for consistent sorting
        Returns sortable time string
        """
        try:
            if time_str == 'Active ⚡' or time_str == 'Invalid Time':
                return '23:59:59'
            return datetime.strptime(time_str, '%I:%M %p').strftime('%H:%M:%S')
        except Exception:
            return '00:00:00'

    @st.cache_data(ttl=30)
    def get_monthly_entries(_self, teacher_id, year, month):
        """
        Get and cache monthly entries with enhanced data processing
        Returns processed DataFrame with consistent types
        """
        try:
            timesheet_df = _self.read_sheet_to_df(_self.timesheet_sheet_id, 'A:H')
            if timesheet_df.empty:
                return pd.DataFrame()
            
            # Convert date column to datetime
            timesheet_df['date'] = pd.to_datetime(timesheet_df['date'], format='%Y-%m-%d')
            timesheet_df['teacher_id'] = timesheet_df['teacher_id'].astype(str).str.strip()
            
            # Filter entries for the specified month and teacher
            mask = (
                (timesheet_df['teacher_id'] == str(teacher_id).strip()) &
                (timesheet_df['date'].dt.year == year) &
                (timesheet_df['date'].dt.month == month)
            )
            monthly_entries = timesheet_df[mask].copy()
            
            # Ensure numeric types for calculations
            monthly_entries['actual_hours'] = pd.to_numeric(monthly_entries['actual_hours'], errors='coerce')
            monthly_entries['adjusted_hours'] = pd.to_numeric(monthly_entries['adjusted_hours'], errors='coerce')
            
            return monthly_entries
            
        except Exception as e:
            st.error(f"Error getting monthly entries: {str(e)}")
            return pd.DataFrame()

    def calculate_program_totals(self, entries):
        """
        Calculate total hours by program with proper handling of partial hours
        Returns dictionary of program totals sorted by hours
        """
        try:
            if entries.empty:
                return {}
            
            # Ensure adjusted_hours is numeric
            entries['adjusted_hours'] = pd.to_numeric(entries['adjusted_hours'], errors='coerce')
            
            # Group by program and sum adjusted hours
            program_totals = entries.groupby('program')['adjusted_hours'].sum().round(2)
            
            # Convert to dictionary and sort by total hours
            totals_dict = dict(sorted(
                program_totals.items(),
                key=lambda x: (-x[1], x[0])  # Sort by hours (desc) then program name (asc)
            ))
            
            return totals_dict
            
        except Exception as e:
            st.error(f"Error calculating program totals: {str(e)}")
            return {}

    def process_entries_for_display(self, entries):
        """
        Process entries for display with consistent formatting
        Returns processed DataFrame ready for display
        """
        try:
            if entries.empty:
                return pd.DataFrame()
                
            display_df = entries.copy()
            
            # Format dates and times
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
            display_df['clock_in'] = display_df['clock_in'].apply(self.format_clock_time)
            display_df['clock_out'] = display_df['clock_out'].apply(self.format_clock_time)
            
            # Create sort datetime
            display_df['sort_datetime'] = pd.to_datetime(
                display_df['date'] + ' ' + display_df['clock_in'].apply(
                    lambda x: self.format_time_for_sorting(x)
                ),
                format='%Y-%m-%d %H:%M:%S',
                errors='coerce'
            )
            
            # Sort entries
            display_df = display_df.sort_values('sort_datetime', ascending=False)
            
            # Select and order columns for display
            columns_to_display = ['date', 'program', 'clock_in', 'clock_out', 'adjusted_hours']
            display_df = display_df[columns_to_display]
            
            # Format numeric columns
            display_df['adjusted_hours'] = display_df['adjusted_hours'].round(2)
            
            return display_df
            
        except Exception as e:
            st.error(f"Error processing entries for display: {str(e)}")
            return pd.DataFrame()

    def format_program_totals_for_display(self, program_totals):
        """
        Format program totals for display with consistent styling
        Returns HTML string for program totals section
        """
        try:
            if not program_totals:
                return ""

            # Calculate total hours across all programs
            total_hours = sum(program_totals.values())
                
            # Build the HTML string with proper structure
            html = '<div class="program-summary">\n'
            html += '    <h3>Hours by Program</h3>\n'
            html += '    <div class="program-list">\n'
            
            # Add each program's data
            for program, hours in program_totals.items():
                html += f"""        <div class="program-total">
                <span class="program-name">{program}</span>
                <span class="program-hours">{hours:.2f} hrs</span>
            </div>\n"""
            
            # Add total hours section
            html += f"""        <div class="program-total" style="border-top: 2px solid #e9ecef; margin-top: 10px; padding-top: 10px;">
                <span class="program-name" style="font-weight: 600;">Total Hours</span>
                <span class="program-hours" style="background-color: #2c3e50; color: white;">{total_hours:.2f} hrs</span>
            </div>\n"""
            
            # Close the containers properly
            html += '    </div>\n'  # Close program-list
            html += '</div>\n'      # Close program-summary
            
            return html
            
        except Exception as e:
            st.error(f"Error formatting program totals: {str(e)}")
            return ""
        

# Part 4
    def main_page(self):
            """Main page of the application with clock in/out functionality"""
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
            
            programs = ["Select Program", "Rawdat", "Rawdat + Admin Work", "Sigaar", "Mukhayyam", "Kibaar", "Camp"]
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

            # Create three columns for buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🕐 Clock In", use_container_width=True):
                    if self.handle_clock_in(teacher_id, program):
                        st.success(f"Clocked in successfully at {self.get_london_time().strftime('%I:%M %p')}")
            
            with col2:
                if st.button("🕐 Clock Out", use_container_width=True):
                    if self.handle_clock_out(teacher_id, program):
                        st.success(f"Clocked in successfully at {self.get_london_time().strftime('%I:%M %p')}")
            
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
        """Show timesheet history page with enhanced program totals and export options"""
        try:
            # Back button
            if st.button("← Back", key="back_button"):
                st.session_state.current_page = 'main'
                st.rerun()
                
            st.markdown("""
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
                    <span style="font-size: 24px;">📅</span>
                    <span class="big-font">Timesheet History</span>
                </div>
            """, unsafe_allow_html=True)
            
            # Get and display teacher information
            teacher = self.get_teacher_info(teacher_id)
            if not teacher:
                st.error("Teacher information not found")
                return
                
            st.markdown(f"""
                <div class="main-header">
                    <span style="font-size: 40px;">👤</span>
                    <div>
                        <div class="big-font">{teacher_id} - {teacher['name']}</div>
                        <div class="text-muted">Last 2 Months History</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Calculate months to display
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
            
            # Create tabs for each month
            tabs = st.tabs([f"{calendar.month_name[m[1]]} {m[0]}" for m in months])
            
            # Process each month's data
            for idx, (year, month) in enumerate(months):
                with tabs[idx]:
                    # Get monthly entries
                    entries = self.get_monthly_entries(teacher_id, year, month)
                    
                    if not entries.empty:
                        # Process entries for display
                        display_df = self.process_entries_for_display(entries)
                        
                        # Calculate program totals
                        program_totals = self.calculate_program_totals(entries)
                        
                        # Create export button and handle PDF generation
                        col1, col2 = st.columns([4, 1])
                        with col2:
                            # Modify this section in the show_history_page method
                            if st.button(f"📄 Export PDF", key=f"export_{year}_{month}", use_container_width=True):
                                with st.spinner("Generating PDF report..."):
                                    try:
                                        pdf_content = self.generate_pdf_report(
                                            teacher_id,
                                            entries,
                                            year,
                                            month,
                                            teacher
                                        )
                                        
                                        if pdf_content:
                                            # Convert PDF content to base64
                                            b64_pdf = base64.b64encode(pdf_content).decode('utf-8')
                                            file_name = f"timesheet_{teacher_id}_{year}_{month}.pdf"
                                            
                                            # Update the button to a download link with integrated styling
                                            st.success("PDF report generated successfully!")
                                            st.markdown(
                                                f"""
                                                <a href="data:application/pdf;base64,{b64_pdf}" 
                                                download="{file_name}"
                                                style="text-decoration:none;">
                                                    <div style="
                                                        background-color: #2c3e50;
                                                        color: white;
                                                        padding: 10px 15px;
                                                        border-radius: 5px;
                                                        text-align: center;
                                                        font-weight: 500;
                                                        display: flex;
                                                        align-items: center;
                                                        justify-content: center;
                                                        gap: 8px;
                                                        margin: 10px 0;
                                                        cursor: pointer;
                                                        transition: all 0.3s ease;">
                                                        <span>📥</span> Download PDF Report
                                                    </div>
                                                </a>
                                                """,
                                                unsafe_allow_html=True
                                            )
                                        else:
                                            st.error("Failed to generate PDF report")
                                    except Exception as e:
                                        st.error(f"Error during PDF export: {str(e)}")

                        
                        # Display entries table
                        st.markdown("### Timesheet Entries")
                        height = min(len(display_df) * 35 + 40, 400)  # Cap maximum height
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            height=height
                        )

                        # Display total hours under the table
                        total_hours = display_df['adjusted_hours'].sum()
                        st.markdown(
                            f"""
                            <div class="total-hours">
                                Total Hours: {total_hours:.2f}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
                        # Display program totals
                        st.markdown(
                            self.format_program_totals_for_display(program_totals),
                            unsafe_allow_html=True
                        )
                        
                    else:
                        st.info(f"No entries found for {calendar.month_name[month]} {year}")
        
        except Exception as e:
            st.error(f"An error occurred while loading the history page: {str(e)}")

    def run(self):
        """Main application entry point"""
        if st.session_state.current_page == 'main':
            self.main_page()
        elif st.session_state.current_page == 'history':
            self.show_history_page(st.session_state.get('history_teacher_id', ''))

# Part 5

    def generate_pdf_report(self, teacher_id, entries, year, month, teacher_info):
            """
            Generate PDF timesheet report with enhanced formatting and error handling
            Returns PDF content as bytes
            """
            try:
                # Create buffer for PDF
                buffer = BytesIO()
                
                # Initialize PDF document
                doc = SimpleDocTemplate(
                    buffer,
                    pagesize=A4,
                    rightMargin=30,
                    leftMargin=30,
                    topMargin=30,
                    bottomMargin=30
                )
                
                # Initialize styles
                styles = getSampleStyleSheet()
                
                # Custom styles
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=20,
                    spaceAfter=30,
                    alignment=1  # Center alignment
                )
                
                subtitle_style = ParagraphStyle(
                    'CustomSubTitle',
                    parent=styles['Heading2'],
                    fontSize=16,
                    spaceAfter=20,
                    textColor=colors.grey
                )
                
                header_style = ParagraphStyle(
                    'CustomHeader',
                    parent=styles['Heading3'],
                    fontSize=14,
                    spaceBefore=20,
                    spaceAfter=10,
                    textColor=colors.HexColor('#2c3e50')
                )
                
                normal_style = ParagraphStyle(
                    'CustomNormal',
                    parent=styles['Normal'],
                    fontSize=10,
                    spaceBefore=6,
                    spaceAfter=6
                )
                
                # Initialize elements list
                elements = []
                
                # Add title
                elements.append(Paragraph(
                    "AL JAMEAH AL SAYFIYAH TRUST",
                    title_style
                ))
                
                # Add timesheet subtitle
                elements.append(Paragraph(
                    f"Timesheet Report - {calendar.month_name[month]} {year}",
                    subtitle_style
                ))
                
                # Add teacher information
                elements.append(Paragraph(
                    f"Teacher: {teacher_info['name']}",
                    normal_style
                ))
                elements.append(Paragraph(
                    f"ITS ID: {teacher_id}",
                    normal_style
                ))
                
                # Add generation timestamp
                elements.append(Paragraph(
                    f"Report Generated: {datetime.now().strftime('%Y-%m-%d at %I:%M:%S %p')}",
                    normal_style
                ))
                

                # Add spacer
                elements.append(Spacer(1, 20))
                
                if not entries.empty:
                    # Sort entries by date
                    entries_sorted = entries.sort_values('date')
                    
                    # Prepare timesheet data
                    timesheet_data = [['Date', 'Program', 'Clock In', 'Clock Out', 'Hours']]
                    
                    # Add entries to timesheet data
                    for _, row in entries_sorted.iterrows():
                        timesheet_data.append([
                            row['date'].strftime('%Y-%m-%d'),
                            row['program'],
                            self.format_clock_time(row['clock_in']),
                            self.format_clock_time(row['clock_out']),
                            f"{float(row['adjusted_hours']):.2f}"
                        ])

                    # Add total row
                    total_hours = entries_sorted['adjusted_hours'].sum()
                    timesheet_data.append(['', '', '', 'Total Hours:', f"{total_hours:.2f}"])
                    
                    # Create and style the timesheet table
                    table_style = TableStyle([
                        # Header styling
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        
                        # Data row styling
                        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -2), 1, colors.black),
                        
                        # Total row styling
                        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8f9fa')),
                        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                        ('ALIGN', (-2, -1), (-1, -1), 'RIGHT'),
                        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#2c3e50')),
                        
                        # Specific column alignments
                        ('ALIGN', (0, 0), (0, -2), 'LEFT'),  # Date column
                        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),  # Hours column
                        
                        # Alternating row colors (excluding total row)
                        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')])
                    ])
                    
                    # Create the table with specific column widths
                    col_widths = [90, 120, 80, 80, 60]  # Adjusted column widths
                    timesheet_table = Table(timesheet_data, colWidths=col_widths, repeatRows=1)
                    timesheet_table.setStyle(table_style)
                    elements.append(timesheet_table)
                    
                    # Add spacer
                    elements.append(Spacer(1, 30))
                    
                    # Add program totals section
                    elements.append(Paragraph("Program Summary", header_style))
                    
                    # Calculate program totals
                    program_totals = self.calculate_program_totals(entries)
                    
                    # Create program totals table
                    totals_data = [['Program', 'Total Hours']]
                    for program, hours in program_totals.items():
                        totals_data.append([program, f"{hours:.2f}"])
                    
                    # Add total row to program totals
                    total_program_hours = sum(program_totals.values())
                    totals_data.append(['Total', f"{total_program_hours:.2f}"])
                    
                    # Style for program totals table
                    totals_style = TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('GRID', (0, 0), (-1, -2), 1, colors.black),
                        ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),
                        # Total row styling
                        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8f9fa')),
                        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#2c3e50')),
                    ])
                    
                    totals_table = Table(totals_data, colWidths=[300, 100])
                    totals_table.setStyle(totals_style)
                    elements.append(totals_table)
                    
                else:
                    elements.append(Paragraph(
                        f"No entries found for {calendar.month_name[month]} {year}",
                        normal_style
                    ))
                
                # Build PDF
                doc.build(elements)
                
                # Get PDF content
                pdf_content = buffer.getvalue()
                buffer.close()
                
                return pdf_content
                
            except Exception as e:
                st.error(f"Error generating PDF report: {str(e)}")
                return None
    def get_london_time(self):
        """Get current time in London (GMT/BST) with proper DST handling"""
        london_tz = pytz.timezone('Europe/London')
        return datetime.now(pytz.utc).astimezone(london_tz)

if __name__ == "__main__":
    app = TimesheetApp()
    app.run()