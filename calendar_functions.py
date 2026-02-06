"""
Calendar Functions Module

Provides functionality to interact with the Google Calendar API.
Used to identify the user currently assigned to weekend help desk duty.
"""

import datetime
import os.path
import re

from datetime import timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def main():
    """Execute the main flow to find and print the weekend duty user.

    Calls ``get_weekend_duty`` to retrieve the current event and ``get_user``
    to extract the assignee's name, printing both to standard output.
    """
    event = get_weekend_duty()
    print("EVENT:", event)
    user = get_user(event)
    print("USER: ", user)

def get_weekday_duty(department):

    if department == "dev":
        calendar_name = "Fire Duty - Developers"
    elif department == "systems":
        calendar_name = "Fire Duty - Systems"

    """Retrieve the current weekday duty event from Google Calendar.

    Authenticates with the Google Calendar API (handling OAuth token flow),
    finds the correct calendar based on the department parameter ( "dev" or "systems"),
    and searches for the event overlapping the current date and time.

    Returns:
        dict: A dictionary representation of the Google Calendar event if found,
        otherwise None.
    """

    try:
        creds = get_google_creds()
        service = build("calendar", "v3", credentials=creds)

        # Find the Fire Duty calendar by name
        page_token = None
        fire_duty_calendar_id = None
        while True:
            calendar_list = service.calendarList().list(pageToken=page_token).execute()
            for calendar_list_entry in calendar_list["items"]:
                if calendar_list_entry["summary"] == calendar_name:
                    fire_duty_calendar_id = calendar_list_entry["id"]
                    break
            page_token = calendar_list.get("nextPageToken")
            if fire_duty_calendar_id or not page_token:
                break

        if not fire_duty_calendar_id:
            print(f"Calendar '{calendar_name}' not found.")
            return None

        # Get events for the current hour only
        now = datetime.datetime.utcnow()
        start_of_hour = now.replace(minute=0, second=0, microsecond=0)
        start_of_next_hour = start_of_hour + timedelta(hours=1)
        
        time_min = start_of_hour.isoformat() + "Z"
        time_max = start_of_next_hour.isoformat() + "Z"
        
        print(f"Getting events for {calendar_name} from {start_of_hour} to {start_of_next_hour} UTC")
        events_result = (
            service.events()
            .list(
                calendarId=fire_duty_calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            print("No events found for today.")
            return None

        # Find the event that overlaps with the current time
        now_str = now.strftime("%Y-%m-%dT%H:%M:%S")
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            
            # For all-day events, compare dates; for timed events, compare timestamps
            if "T" in start:  # Timed event
                if start <= now_str <= end:
                    print(f"Found current event: {event['summary']} ({start} to {end})")
                    return event
            else:  # All-day event
                today = now.strftime("%Y-%m-%d")
                if start <= today < end:
                    print(f"Found current event: {event['summary']} ({start} to {end})")
                    return event

        print("No event found for current time.")
        return None

    except Exception as error:
        print(f"An error occurred: {error}")
        return None


def get_weekend_duty():
    """Retrieve the current weekend help desk event from Google Calendar.

    Authenticates with the Google Calendar API (handling OAuth token flow),
    finds the "Weekend Help Desk" calendar, and searches for the event
    corresponding to the current date.

    Returns:
        dict: A dictionary representation of the Google Calendar event if found,
        otherwise None.
    """

    try:
        creds = get_google_creds()
        service = build("calendar", "v3", credentials=creds)

        page_token = None
        weekend_help_desk_calendar_id = None
        while True:
            calendar_list = service.calendarList().list(pageToken=page_token).execute()
            for calendar_list_entry in calendar_list["items"]:
                if calendar_list_entry["summary"] == "Weekend Help Desk":
                    weekend_help_desk_calendar_id = calendar_list_entry["id"]
            page_token = calendar_list.get("nextPageToken")
            if not page_token:
                break

        # Call the Calendar API
        d = datetime.datetime.utcnow() - timedelta(days=7)
        last_week = d.isoformat() + "Z"  # 'Z' indicates UTC time
        print("Getting the upcoming 10 events")
        events_result = (
            service.events()
            .list(
                calendarId=weekend_help_desk_calendar_id,
                timeMin=last_week,
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            print("No upcoming events found.")
            return

        # Prints the start and name of the next 10 events
        current_event = None
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            if start <= today < end:
                print(f"Found event where start {start} <= today {today} < end {end}")
                current_event = event
                print("FOUND EVENT: ", start, end, event["summary"])
                return event

    except HttpError as error:
        print("An error occurred: %s" % error)


def get_user(event):
    """Extract the user name from a calendar event summary.

    Parses the event summary string (typically "Name - Weekend Help Desk")
    to isolate the assignee's name using regex.

    Args:
        event (dict): The Google Calendar event object containing a 'summary' key.

    Returns:
        str: The extracted user name.
    """
    if event:
        summary = event["summary"]

        result = re.search("(.+) - Weekend Help Desk.*", summary, re.IGNORECASE)
        print("USER: ", result.group(1))

        return result.group(1)

# Global credential cache to prevent race conditions
_cached_creds = None

def get_google_creds():
    global _cached_creds
    
    # Return cached credentials if available and valid
    if _cached_creds and _cached_creds.valid:
        return _cached_creds
    
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.

    creds = None

    if os.path.exists("token.json"):
        try:
            print("Loading credentials from token.json")
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        except Exception as e:
            print(f"Error loading token.json: {e}. Will re-authenticate.")
            # Remove corrupted file
            try:
                os.remove("token.json")
            except:
                pass
            creds = None
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        print("No valid credentials found")
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing credentials")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials: {e}. Will re-authenticate.")
                creds = None
        
        if not creds:
            print("Creating new credentials")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        try:
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        except Exception as e:
            print(f"Warning: Could not save token.json: {e}")
    
    # Cache the credentials
    _cached_creds = creds
    return creds


if __name__ == "__main__":
    main()
