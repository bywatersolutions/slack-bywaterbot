"""
ByWater Slack Bot

Main application module for the ByWater Slack bot. Sets up the Slack Bolt app, loads configuration,
and registers message handlers from other modules.
"""

import os
import threading
import time
import schedule
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Import configuration and handlers
from config import load_config, refresh_data
from bot_functions import get_quote
from version import __version__

from calendar_functions import get_google_creds
from devops_handlers import register_devops_handlers
from devops_alerts_handlers import register_devops_alerts_handlers
from general_handlers import register_general_handlers
from karma_handlers import register_karma_handlers
from support_handlers import register_support_handlers, register_ticket_notifier
from partner_handlers import register_partner_handlers
from contact_handlers import register_contact_handlers


def run_scheduler():
    """Run the scheduler in a background thread."""
    # Initial refresh to ensure we have fresh data on startup
    refresh_data()

    # Schedule hourly refreshes
    schedule.every().hour.do(refresh_data)

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


def register_handlers(app):
    """Register every handler, in the order Bolt has to see them.

    Bolt runs only the first @app.message listener that matches a message, so
    order matters. The #tickets new-ticket notifier registers first: its
    specific "New Ticket" pattern must win over the broader help/lookup handlers,
    which also match the Zoho Flow post. The #devops-alerts watcher uses a
    catch-all @app.event("message") that matches every message, so it registers
    last or it shadows the partner and contact commands below it.
    """
    register_ticket_notifier(app)
    register_general_handlers(app)
    register_karma_handlers(app)
    register_support_handlers(app)
    register_devops_handlers(app)
    register_partner_handlers(app)
    register_contact_handlers(app)
    register_devops_alerts_handlers(app)


if __name__ == "__main__":
    print(f"ByWaterBot {__version__} is starting up!")

    # 1. Load Configuration
    load_config()

    # 2.Initialize App
    slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app = App(token=slack_bot_token)

    # 3. Start Scheduler
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # 4. Initialize Single-Run Tasks (Quotes, Credentials)
    # Give a quote on startup logic (commented out in original, kept for reference)
    # quotes_csv_url = os.environ.get("QUOTES_CSV_URL")
    # quote = get_quote(url=quotes_csv_url)

    # Initialize Google Calendar credentials
    print("Initializing Google Calendar credentials...")
    try:
        get_google_creds()
        print("Google Calendar credentials initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize Google Calendar credentials: {e}")

    # 5. Register Handlers ( order matters — see register_handlers )
    register_handlers(app)

    # 6. Start the App
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
