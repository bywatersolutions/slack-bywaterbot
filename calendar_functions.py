import datetime
import os.path
import re

from datetime import timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

def main():
    event = get_weekend_duty()
    print("EVENT:", event)
    user = get_user(event)
    print("USER: ", user)

def get_weekend_duty():
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)

        page_token = None
        weekend_help_desk_calendar_id = None
        while True:
          calendar_list = service.calendarList().list(pageToken=page_token).execute()
          for calendar_list_entry in calendar_list['items']:
            if calendar_list_entry['summary'] == "Weekend Help Desk":
                weekend_help_desk_calendar_id = calendar_list_entry['id']
          page_token = calendar_list.get('nextPageToken')
          if not page_token:
            break


        # Call the Calendar API
        d = datetime.datetime.utcnow() - timedelta(days=7)
        last_week = d.isoformat() + 'Z'  # 'Z' indicates UTC time
        print('Getting the upcoming 10 events')
        events_result = service.events().list(calendarId=weekend_help_desk_calendar_id, timeMin=last_week,
                                              maxResults=100, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
            return

        # Prints the start and name of the next 10 events
        current_event = None
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            if start <= today <= end:
                print(f"Found event where start {start} <= today {today} <= end {end}");
                current_event = event
                print("FOUND EVENT: ", start, end, event['summary'])
                return(event)

    except HttpError as error:
        print('An error occurred: %s' % error)

def get_user(event):
    if event:
        summary = event['summary']

        result = re.search(r"(.+) help desk", summary)
        print("USER: ", result.group(1))

        return result.group(1)


if __name__ == '__main__':
    main()
