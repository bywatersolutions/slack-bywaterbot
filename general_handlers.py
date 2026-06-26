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
import re
import config
from bot_functions import get_name_to_id_mapping, get_quote


def register_general_handlers(app):
    # Detailed capabilities, sent when you DM me "help" (any casing)
    @app.message(re.compile(r"\bhelp\b", re.IGNORECASE))
    def message_help(message, say):
        """Describe every capability and how to use it (DM only)."""
        if message.get("channel_type") != "im":
            return

        text = (
            ":robot_face: *ByWaterBot help*\n"
            "Here's everything I can do and how to ask. Unless noted, commands work "
            "in any channel I'm in or in a DM with me.\n"
            "\n"
            "*Koha & support lookups*\n"
            "• `bug <id>` or `bz <id>` — Look up a Koha community bug; I reply with "
            "its summary, status, and a link.   _e.g._ `bug 38120`\n"
            "• `branches <bug_id> [shortname]` — List which Koha branches contain a "
            "bug. Shortname defaults to `bywater`.   _e.g._ `branches 38120 bywater`\n"
            "\n"
            "*Partners*\n"
            "• `innreach partners` — List the INN-Reach partner shortnames.\n"
            "• `rapido partners` — List the Rapido partner shortnames.\n"
            "\n"
            "*Texting teammates (SMS via Twilio)*\n"
            "• `TEXT <name> <message>` — Send a teammate an SMS. Use their name as it "
            "appears in my contact list.   _e.g._ `TEXT Kyle running 5 min late`\n"
            "• `test weekend duty` — _(#tickets only)_ Dry run: I tell you who's on "
            "weekend duty and whether I have their number. No text is sent.\n"
            "• `test weekend duty sms` — _(#tickets only)_ Send a real test SMS to the "
            "current on-duty person.\n"
            "\n"
            "*Karma & kudos*\n"
            "• `name++` or `@name++` — Give someone kudos; I post an encouragement to "
            "#kudos.   _e.g._ `@kyle++`\n"
            "• `(name1 name2 ...)++` — Give a whole group kudos at once.\n"
            "• `name--` — Take a shot at someone; I'll gently push back.\n"
            "\n"
            "*Fun & utility*\n"
            "• `hello` — I'll say hi.\n"
            '• `wow` — Owen Wilson says "wow".\n'
            "• `Quote Please` — I post a random quote to #general.\n"
            "• `list slack names` — List the names and Slack IDs I know.\n"
            "\n"
            "*Admin (DM me only)*\n"
            "• `Refresh Data` — Reload my contact/duty data from its source.\n"
            "• `Refresh Karma` — Reload my karma pep-talk messages.\n"
            "• `help` — Show this message (any casing works).\n"
            "\n"
            "*Things I do automatically* (no command needed)\n"
            "• *New weekend tickets* — when a new ticket posts in #tickets, I text "
            "whoever's on weekend duty.\n"
            "• *DevOps fires* — react :fire: to a message in #devops and I'll text the "
            "on-call dev/systems person.\n"
            "• *#devops-alerts* — when a failure posts, I DM the on-call person an "
            "Acknowledge button and keep reminding them until they click it."
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

        if config.refresh_data():
            say("Successfully refreshed bywaterbot data!")
        else:
            say("Failed to refresh bywaterbot data.")
