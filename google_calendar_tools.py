import os.path
import datetime as dt
from typing import List

from langchain_core.tools import tool
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from dateutil.parser import parse as date_parse
from tzlocal import get_localzone

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service():
    """Initializes and returns a Google Calendar service object."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    service = build("calendar", "v3", credentials=creds)
    return service

@tool
def check_availability(start_time: str, end_time: str) -> str:
    """
    Checks for free time slots in a Google Calendar between a given start and end time.
    This tool handles timezones automatically.
    """
    try:
        service = get_calendar_service()
        start_dt = date_parse(start_time)
        end_dt = date_parse(end_time)
        local_tz = get_localzone()

        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=local_tz)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=local_tz)

        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()
        
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_iso,
                timeMax=end_iso,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        busy_slots = events_result.get("items", [])

        if not busy_slots:
            return f"The entire period from {start_dt.strftime('%I:%M %p')} to {end_dt.strftime('%I:%M %p')} is free. Suggest 1-hour slots."
        
        available_slots = []
        current_time = start_dt

        for event in busy_slots:
            event_start = date_parse(event["start"].get("dateTime"))
            if current_time < event_start:
                while current_time + dt.timedelta(hours=1) <= event_start:
                    slot_end = current_time + dt.timedelta(hours=1)
                    available_slots.append(f"{current_time.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')}")
                    current_time += dt.timedelta(hours=1)
            current_time = max(current_time, date_parse(event["end"].get("dateTime")))

        while current_time + dt.timedelta(hours=1) <= end_dt:
            slot_end = current_time + dt.timedelta(hours=1)
            available_slots.append(f"{current_time.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')}")
            current_time += dt.timedelta(hours=1)

        if not available_slots:
            return "No 1-hour slots are available in the requested timeframe."

        return f"Here are the available 1-hour slots: {', '.join(available_slots)}. Please suggest these to the user."

    except Exception as e:
        print(f"ERROR in check_availability: {e}") 
        return "An error occurred while checking the calendar. Please try again or specify a different time."

@tool
def book_appointment(start_time: str, end_time: str, summary: str, description: str = "") -> str:
    """Books an appointment on the user's primary Google Calendar."""
    try:
        service = get_calendar_service()
        start_dt = date_parse(start_time)
        end_dt = date_parse(end_time)
        local_tz = get_localzone()
        
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=local_tz)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=local_tz)

        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": str(local_tz)},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": str(local_tz)},
        }
        created_event = service.events().insert(calendarId="primary", body=event).execute()
        return f"Success! The appointment '{summary}' has been booked for {start_dt.strftime('%A, %B %d at %I:%M %p')}. The event link is: {created_event.get('htmlLink')}"
    except Exception as e:
        print(f"ERROR in book_appointment: {e}")
        return "An error occurred while booking the appointment. Please check the details and try again."