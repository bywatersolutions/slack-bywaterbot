"""
General Handlers Module

Contains message handlers for:
- Help command
- Hello command
- List names command
- Wow command
- Quote requests
"""

import os
from config import bywaterbot_data, refresh_data
from bot_functions import get_name_to_id_mapping, get_quote

def register_general_handlers(app):
    
    @app.message("help")
    def message_help(message, say):
        """List bot capabilities (DM only)."""
        if message.get("channel_type") != "im":
            return

        text = (
            "Here are my capabilities:\n"
            "* `hello`: Say hello\n"
            "* `list slack names`: List known names and Slack IDs\n"
            "* `Quote Please`: Get a random quote\n"
            "* `Refresh Karma`: Refresh karma messages\n"
            "* `Refresh Data`: Refresh ByWaterBot data from source\n"
            "* `bug 1234` or `bz 1234`: Look up Koha bug\n"
            "* `branches <bug_id> [shortname]`: Find branches for a bug\n"
            "* `test sms <user>`: Send test SMS\n"
            "* `TEXT <user> <message>`: Send SMS\n"
            "* `(user1 user2)++`: Group karma\n"
            "* `user++` or `user--`: Individual karma"
        )
        say(text)

    @app.message("hello")
    def message_hello(message, say):
        # say() sends a message to the channel where the event was triggered
        print(f"Hey there <@{message['user']}>!")
        say(f"Hey there <@{message['user']}>!")

    @app.message("^list slack names")
    def message_names(message, say):
        name_to_id, name_to_info = get_name_to_id_mapping(app)
        say("Here are the names I know along with that persons Slack ID :")
        for name, info in name_to_info.items():
            say(f"{name}: {info['id']}")

    @app.message("^wow")
    def message_wow(message, say):
        blocks = [
            {
                "type": "image",
                "image_url": "https://bywater.solutions/wow",
                "alt_text": "Just imagine Owen Wilson saying 'Wow'.",
            }
        ]
        say(blocks=blocks)

    @app.message("Quote Please")
    def handle_quote(message, say):
        """Post a random quote to #general and echo it."""
        quotes_csv_url = os.environ.get("QUOTES_CSV_URL")
        if quotes_csv_url:
            quote = get_quote(url=quotes_csv_url)
            try:
                app.client.chat_postMessage(
                    channel="#general",
                    text=quote,
                )
                say(quote)
            except Exception as e:
                say(f"Error posting quote: {e}")
        else:
            say("No QUOTES_CSV_URL configured.")

    # Refresh bywaterbot data manually
    @app.message("Refresh Data")
    def handle_refresh(message, say):
        """Refresh bywaterbot data."""
        if message.get("channel_type") != "im":
            return

        if refresh_data():
            say("Successfully refreshed bywaterbot data!")
        else:
            say("Failed to refresh bywaterbot data.")
