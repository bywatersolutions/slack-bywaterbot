"""
Configuration Module for ByWater Slack Bot

Handles loading of bywaterbot_data, environment variables, and Twilio client initialization.
"""

import os
import pprint
from datetime import datetime
from twilio.rest import Client
from bot_functions import load_bywaterbot_data

pp = pprint.PrettyPrinter(indent=2)

DEFAULT_DEVOPS_ASSIGNEE = "Kyle"

# Global data store
bywaterbot_data = {}

# Twilio client
twilio_client = None
twilio_phone = None


def load_config():
    """Load bywaterbot_data and initialize environment variables and clients."""
    global bywaterbot_data, twilio_client, twilio_phone

    print("Loading configuration...")

    # Initial load of bywaterbot_data
    bywaterbot_data = load_bywaterbot_data()
    pp.pprint(bywaterbot_data)

    # Set environment variables from bywaterbot_data if they are not already set
    if "BYWATER_BOT_GITHUB_TOKEN" not in os.environ:
        os.environ["BYWATER_BOT_GITHUB_TOKEN"] = bywaterbot_data.get(
            "BYWATER_BOT_GITHUB_TOKEN", ""
        )
    if "CREDENTIALS_JSON" not in os.environ:
        os.environ["CREDENTIALS_JSON"] = bywaterbot_data.get("CREDENTIALS_JSON", "")
    if "KARMA_CSV_URL" not in os.environ:
        os.environ["KARMA_CSV_URL"] = bywaterbot_data.get("KARMA_CSV_URL", "")
    if "QUOTES_CSV_URL" not in os.environ:
        os.environ["QUOTES_CSV_URL"] = bywaterbot_data.get("QUOTES_CSV_URL", "")
    if "SLACK_APP_TOKEN" not in os.environ:
        os.environ["SLACK_APP_TOKEN"] = bywaterbot_data.get("SLACK_APP_TOKEN", "")
    if "SLACK_BOT_TOKEN" not in os.environ:
        os.environ["SLACK_BOT_TOKEN"] = bywaterbot_data.get("SLACK_BOT_TOKEN", "")
    if "TWILIO_ACCOUNT_SID" not in os.environ:
        os.environ["TWILIO_ACCOUNT_SID"] = bywaterbot_data.get("TWILIO_ACCOUNT_SID", "")
    if "TWILIO_AUTH_TOKEN" not in os.environ:
        os.environ["TWILIO_AUTH_TOKEN"] = bywaterbot_data.get("TWILIO_AUTH_TOKEN", "")
    if "TWILIO_PHONE" not in os.environ:
        os.environ["TWILIO_PHONE"] = bywaterbot_data.get("TWILIO_PHONE", "")
    if "TOKEN_JSON" not in os.environ:
        os.environ["TOKEN_JSON"] = bywaterbot_data.get("TOKEN_JSON", "")

    # Write google credentials to file if stored in environment variable
    if "CREDENTIALS_JSON" in os.environ:
        with open("credentials.json", "w") as f:
            f.write(os.environ["CREDENTIALS_JSON"])

    # Only write token.json from env var if it doesn't exist (don't overwrite cached credentials)
    if "TOKEN_JSON" in os.environ and not os.path.exists("token.json"):
        with open("token.json", "w") as f:
            f.write(os.environ["TOKEN_JSON"])

    # Set up twilio client
    try:
        account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        twilio_phone = os.environ["TWILIO_PHONE"]
        if account_sid and auth_token:
            twilio_client = Client(account_sid, auth_token)
            print("Twilio client initialized")
    except Exception as e:
        print(f"Error initializing Twilio client: {e}")


def refresh_data():
    """Refresh the bywaterbot_data by reloading it from the source."""
    global bywaterbot_data
    try:
        new_data = load_bywaterbot_data()
        if new_data:
            bywaterbot_data = new_data
            print(f"Successfully refreshed bywaterbot_data at {datetime.now()}")
            return True
    except Exception as e:
        print(f"Error refreshing bywaterbot_data at {datetime.now()}: {e}")
    return False
