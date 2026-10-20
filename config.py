"""
Configuration Module for ByWater Slack Bot

Handles loading of bywaterbot_data, environment variables, and Twilio client initialization.
"""

import os
from datetime import datetime
from twilio.rest import Client
from bot_functions import load_bywaterbot_data

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
    print(
        "Loaded bywaterbot_data: "
        + ", ".join(f"{len(value)} {key}" for key, value in bywaterbot_data.items())
    )

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
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        twilio_phone = os.environ.get("TWILIO_PHONE")
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
