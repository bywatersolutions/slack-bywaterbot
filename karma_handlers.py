"""
Karma Handlers Module

Contains message handlers for:
- Individual karma (user++ / user--)
- Group karma ((user1 user2)++)
- Refreshing karma messages
"""

import re
import random
import os
from twilio.rest import Client
import config
from bot_functions import get_name_to_id_mapping, get_karma_pep_talks, get_putdowns

# Load karma pep talks from csv
karma_csv_url = os.environ.get("KARMA_CSV_URL")
karma1, karma2, karma3, karma4 = [], [], [], []
if karma_csv_url:
    try:
        karma1, karma2, karma3, karma4 = get_karma_pep_talks(url=karma_csv_url)
    except Exception as e:
        print(f"Error loading karma talks: {e}")

putdowns = get_putdowns()

def register_karma_handlers(app):

    def give_karma(user, say, context):
        """Award karma to a user or respond with a put‑down."""
        
        # We need name_to_id mapping for finding user IDs from names
        name_to_id, _ = get_name_to_id_mapping(app)
        
        is_user = False
        if user.startswith("<@"):
            is_user = True
        elif (not user.startswith("<@")) and user.lower() in name_to_id:
            user = f"<@{name_to_id[user.lower()]}>"
            is_user = True

        if is_user:
            try:
                print("Giving karma to", user)
                k1 = random.choice(karma1) if karma1 else "You rock!"
                k2 = random.choice(karma2) if karma2 else ""
                k3 = random.choice(karma3) if karma3 else ""
                k4 = random.choice(karma4) if karma4 else ""
                
                message = f"{user} {k1} {k2} {k3} {k4}"
                print("Posting message:", message)
                app.client.chat_postMessage(
                    channel="#kudos",
                    text=message,
                )
            except Exception as e:
                print(f"Error giving karma: {e}")
                say(f"Great job {user}!")
        else:
            say(text=f"Who doesn't love {user}, right?")

    # Handle group karma e.g. (@khall @kidclamp @tcohen)++
    @app.message(re.compile(r"\((.+)\)\+\+"))
    def handle_group_karma(say, context):
        """Handle group karma increments."""
        users = context["matches"][0]
        for user in users.split():
            give_karma(user, say, context)

    # Handle individual karma
    # Regex designed to capture `user++` or `user ++` but NOT things like `C++` ideally, 
    # though the original regex was quite broad: (\S*)(\s?\+\+\s?)(.*)?
    @app.message(re.compile(r"(\S*)(\s?\+\+\s?)(.*)?"))
    def handle_individual_karma(say, context):
        """Handle individual karma increments."""
        user = context["matches"][0]
        give_karma(user, say, context)

    # Handle negative Karma
    @app.message(re.compile(r"^(\w+)(\-\-)"))
    def handle_negative_karma(say, context):
        """Handle negative karma decrements."""
        user = context["matches"][0]
        name_to_id, _ = get_name_to_id_mapping(app)
        
        is_user = False
        if user.startswith("<@"):
            is_user = True
        elif (not user.startswith("<@")) and user.lower() in name_to_id:
            user = f"<@{name_to_id[user.lower()]}>"
            is_user = True

        if is_user:
            say(text=f"If you can't say something nice, don't say anything at all.")
        else:
            p = random.choice(putdowns) if putdowns else "is not great."
            say(text=f"{user}, {p}")

    @app.message("Refresh Karma")
    def refresh_karma(message, say):
        """Refresh the cached karma pep talks."""
        if message.get("channel_type") != "im":
            return
        
        global karma1, karma2, karma3, karma4
        say(f"Sure thing!!")
        try:
            url = os.environ.get("KARMA_CSV_URL")
            if url:
                karma1, karma2, karma3, karma4 = get_karma_pep_talks(url=url)
                say(f"Done!")
            else:
                say("No KARMA_CSV_URL configured.")
        except Exception as e:
            say(f"Error refreshing karma: {e}")
