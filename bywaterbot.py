"""
ByWater Slack Bot

Main application module for the ByWater Slack bot. Sets up the Slack Bolt app, loads configuration,
and defines message handlers for karma, bug tracking, and other utilities.
"""

import json
import os
import pprint
import random
import re
import requests
import rt
import schedule
import threading
import time
import urllib.request
from datetime import datetime
from twilio.rest import Client
from bot_functions import (
    get_name_to_id_mapping,
    get_karma_pep_talks,
    get_quote,
    get_putdowns,
    get_channel_id_by_name,
    get_devops_fire_duty_asignee,
    get_data_from_url,
)
from calendar_functions import (
    get_weekend_duty,
    get_user,
)
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

DEFAULT_DEVOPS_ASSIGNEE = "Kyle"

pp = pprint.PrettyPrinter(indent=2)

print("ByWaterBot is starting up!")

# Write google credentials to file if stored in environment variable
if "CREDENTIALS_JSON" in os.environ:
    f = open("credentials.json", "w")
    f.write(os.environ["CREDENTIALS_JSON"])
    f.close()
if "TOKEN_JSON" in os.environ:
    f = open("token.json", "w")
    f.write(os.environ["TOKEN_JSON"])
    f.close()

# Initializes your app with your bot token and socket mode handler
slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
app = App(token=slack_bot_token)

# Set up twilio client
account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
twilio_phone = os.environ["TWILIO_PHONE"]
twilio_client = Client(account_sid, auth_token)


def load_bywaterbot_data():
    """Load bywaterbot_data from URL, environment variable, or local file."""
    data = None
    source = ""

    # Try to load from URL first
    if os.environ.get("BYWATER_BOT_DATA_URL") and os.environ.get(
        "BYWATER_BOT_GITHUB_TOKEN"
    ):
        data = get_data_from_url(
            os.environ.get("BYWATER_BOT_DATA_URL"),
            os.environ["BYWATER_BOT_GITHUB_TOKEN"],
        )
        if data:
            source = "URL"

    # Fall back to environment variable
    if not data and os.environ.get("BYWATER_BOT_DATA"):
        try:
            data = json.loads(os.environ.get("BYWATER_BOT_DATA"))
            source = "environment variable"
        except json.JSONDecodeError as e:
            print(f"Error parsing BYWATER_BOT_DATA: {e}")

    # Fall back to local file
    if not data and os.path.exists("data.json"):
        try:
            with open("data.json") as f:
                data = json.load(f)
                source = "local file"
        except Exception as e:
            print(f"Error loading data.json: {e}")

    if data:
        print(f"Successfully loaded bywaterbot_data from {source}")
        return data
    else:
        raise Exception("Failed to load bywaterbot_data from any source")


def refresh_bywaterbot_data():
    """Refresh the bywaterbot_data by reloading it from the source."""
    global bywaterbot_data
    try:
        new_data = load_bywaterbot_data()
        bywaterbot_data = new_data
        print(f"Successfully refreshed bywaterbot_data at {datetime.now()}")
        return True
    except Exception as e:
        print(f"Error refreshing bywaterbot_data at {datetime.now()}: {e}")
        return False


# Initial load of bywaterbot_data
bywaterbot_data = load_bywaterbot_data()
pp.pprint(bywaterbot_data)

# Schedule hourly refresh
def run_scheduler():
    """Run the scheduler in a background thread."""
    # Initial refresh to ensure we have fresh data on startup
    refresh_bywaterbot_data()

    # Schedule hourly refreshes
    schedule.every().hour.do(refresh_bywaterbot_data)

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


# Start the scheduler in a background thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# Give a quote on startup
quotes_csv_url = os.environ.get("QUOTES_CSV_URL")
quote = get_quote(url=quotes_csv_url)
# app.client.chat_postMessage(
#    channel="#general",
#    text=quote,
# )

devops_channel_id = get_channel_id_by_name(app=app, channel_name="devops")
print(f"DEVOPS CHANNEL ID: {devops_channel_id}")

# Get all Slack users and make a dictionary of name ( e.g. display name ) to user id
name_to_id, name_to_info = get_name_to_id_mapping(app=app)

# Load karma pep talks from csv
karma_csv_url = os.environ.get("KARMA_CSV_URL")
karma1, karma2, karma3, karma4 = get_karma_pep_talks(url=karma_csv_url)

putdowns = get_putdowns()


@app.message("help")
def message_help(message, say):
    """List bot capabilities (DM only)."""
    if message.get("channel_type") != "im":
        return

    text = (
        "Here are my capabilities:\n"
        "* `hello`: Say hello\n"
        "* `names`: List known names and Slack IDs\n"
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


# Refresh bywaterbot data manually
@app.message("Refresh Data")
def message_refresh(message, say):
    """Refresh bywaterbot data."""
    if message.get("channel_type") != "im":
        return

    if refresh_bywaterbot_data():
        say("Successfully refreshed bywaterbot data!")
    else:
        say("Failed to refresh bywaterbot data.")


# Handle group karma e.g. (@khall @kidclamp @tcohen)++
@app.message(re.compile("\((.+)\)\+\+"))
def group_karma_regex(say, context):
    """Handle group karma increments.

    This handler processes messages matching the pattern ``(user1 user2 ...)++`` and
    awards karma to each mentioned user.

    Args:
        say: Function to send a response back to Slack.
        context: Dictionary containing regex matches from the Slack event.
    """
    users = context["matches"][0]
    for user in users.split():
        give_karma(user, say, context)


# Handle individual karma
@app.message(re.compile("(\S*)(\s?\+\+\s?)(.*)?"))
def karma_regex(say, context):
    """Handle individual karma increments.

    This handler processes messages matching ``user++`` or ``user --`` patterns.

    Args:
        say: Function to send a response back to Slack.
        context: Dictionary containing regex matches from the Slack event.
    """
    user = context["matches"][0]
    give_karma(user, say, context)


def give_karma(user, say, context):
    """Award karma to a user or respond with a put‑down.

    Determines whether ``user`` refers to a Slack user ID or a plain string.
    If it is a user, posts a kudos message with random pep talk lines.
    Otherwise, sends a humorous put‑down.

    Args:
        user: The target user identifier or name.
        say: Function to send a response back to Slack.
        context: Additional context (unused here).
    """
    is_user = False

    if user.startswith("<@"):
        is_user = True
    elif (not user.startswith("<@")) and user.lower() in name_to_id:
        user = f"<@{name_to_id[user.lower()]}>"
        is_user = True

    if is_user:
        app.client.chat_postMessage(
            channel="#kudos",
            text=f"{user} {random.choice(karma1)} {random.choice(karma2)} {random.choice(karma3)} {random.choice(karma4)}",
        )
    else:
        say(text=f"Who doesn't love {user}, right?")


# Handle negative Karma
@app.message(re.compile("^(\w+)(\-\-)"))
def karma_regex(say, context):
    """Handle negative karma decrements.

    This handler processes messages matching the pattern ``user--`` and
    posts a humorous put‑down.

    Args:
        say: Function to send a response back to Slack.
        context: Dictionary containing regex matches from the Slack event.
    """
    user = context["matches"][0]
    user = context["matches"][0]

    is_user = False

    if user.startswith("<@"):
        is_user = True
    elif (not user.startswith("<@")) and user.lower() in name_to_id:
        user = f"<@{name_to_id[user.lower()]}>"
        is_user = True

    if is_user:
        say(text=f"If you can't say something nice, don't say anything at all.")
    else:
        say(text=f"{user}, {random.choice(putdowns)}")


@app.message("hello")
def message_hello(message, say):
    # say() sends a message to the channel where the event was triggered
    print(f"Hey there <@{message['user']}>!")
    say(f"Hey there <@{message['user']}>!")


@app.message("names")
def message_names(message, say):
    say("Here are the names I know along with that persons Slack ID :")
    for name, info in name_to_info.items():
        say(f"{name}: {info['id']}")


@app.message("^wow")
def message_hello(message, say):
    blocks = [
        {
            "type": "image",
            "image_url": "https://bywater.solutions/wow",
            "alt_text": "Just imagine Owen Wilson saying 'Wow'.",
        }
    ]
    say(blocks=blocks)


@app.message("Quote Please")
def say_quote(message, say):
    """Post a random quote to #general and echo it.

    Retrieves a quote via ``get_quote`` and posts it to the ``#general``
    channel, then echoes the same quote back to the user who requested it.

    Args:
        message: Slack event payload.
        say: Function to send a response back to Slack.
    """
    quotes_csv_url = os.environ.get("QUOTES_CSV_URL")
    quote = get_quote(url=quotes_csv_url)
    app.client.chat_postMessage(
        channel="#general",
        text=quote,
    )
    say(quote)


@app.message("Refresh Karma")
def refresh_karma(message, say):
    """Refresh the cached karma pep talks.

    Re‑loads the karma CSV files and acknowledges completion.

    Args:
        message: Slack event payload.
        say: Function to send a response back to Slack.
    """
    say(f"Sure thing!!")
    karma1, karma2, karma3, karma4 = get_karma_pep_talks(url=karma_csv_url)
    say(f"Done!")


# Koha bugzilla links, recognizes "bug 1234" and "bz 1234"
@app.message(re.compile("(bug|bz)\s*([0-9]+)"))
def bug_regex(say, context):
    """Lookup a Koha bug and post its details.

    Handles messages like ``bug 1234`` or ``bz 1234``. Retrieves bug summary and
    status from the Koha Bugzilla API and formats a Slack message with a button
    linking to the bug.

    Args:
        say: Function to send a response back to Slack.
        context: Dictionary containing regex matches, where ``matches[1]`` is the
            bug number.
    """
    # regular expression matches are inside of context.matches
    # pp.pprint(context)
    bug = context["matches"][1]
    url = requests.get(f"https://bugs.koha-community.org/bugzilla3/rest/bug/{bug}")
    text = url.text
    data = json.loads(text)

    summary = data["bugs"][0]["summary"]
    status = data["bugs"][0]["status"]
    bugzilla = f"https://bugs.koha-community.org/bugzilla3/show_bug.cgi?id={bug}"

    print(f"BUG: {bug}")
    print(f"SUMMARY: {summary}")
    print(f"STATUS: {status}")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Bug {bug}: {summary}"},
        },
        {
            "type": "section",
            "fields": [{"type": "mrkdwn", "text": f"*Status*\n{status}"}],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"View bug {bug}"},
                    "style": "primary",
                    "value": f"View bug {bug}",
                    "url": f"{bugzilla}",
                }
            ],
        },
    ]
    say(
        blocks=blocks,
        text=f"Koha community <{bugzilla}|bug {bug}>: _{summary}_ [*{status}*]",
    )


# RT links, recognizes "ticket 1234" and "rt 1234"
@app.message(re.compile("(ticket|rt)\s*([0-9]+)"))
def bug_regex(say, context):
    """Lookup an RT ticket and post its details.

    Handles messages like ``ticket 1234`` or ``rt 1234``. Retrieves ticket
    information via the RT API and formats a Slack message with a button linking
    to the ticket.

    Args:
        say: Function to send a response back to Slack.
        context: Dictionary containing regex matches, where ``matches[1]`` is the
            ticket ID.
    """
    ticket_id = context["matches"][1]

    rt_user = os.environ.get("RT_USERNAME")
    rt_pass = os.environ.get("RT_PASSWORD")

    tracker = rt.Rt("https://ticket.bywatersolutions.com/REST/1.0/", rt_user, rt_pass)
    tracker.login()

    tickets = tracker.search(Queue=rt.ALL_QUEUES, raw_query=f"id='{ticket_id}'")

    ticket = tracker.get_ticket(ticket_id=ticket_id)

    subject = tickets[0]["Subject"]
    owner = tickets[0]["Owner"]
    queue = tickets[0]["Queue"]

    requestors1 = ""
    requestors2 = ""
    i = 0
    requestors = tickets[0]["Requestors"]
    for r in requestors:
        if (i % 2) == 0:
            requestors1 = requestors1 + f"{r}\n"
        else:
            requestors2 = requestors2 + f"{r}\n"
        i += 1

    if len(requestors2):
        requestors2 = ".\n" + requestors2
    else:
        requestors2 = " "

    rt_url = f"https://ticket.bywatersolutions.com/Ticket/Display.html?id={ticket_id}"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Ticket {ticket_id}: {subject}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Owner*\n{owner}"},
                {"type": "mrkdwn", "text": f"*Queue*\n{queue}"},
                {"type": "mrkdwn", "text": f"*Requestors*\n{requestors1}"},
                {"type": "mrkdwn", "text": f"{requestors2}"},
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"View ticket {ticket_id}"},
                    "style": "primary",
                    "value": f"View ticket {ticket_id}",
                    "url": f"{rt_url}",
                }
            ],
        },
    ]
    say(
        blocks=blocks,
        text=f"<{rt_url}|Ticket {ticket_id}>: _{subject}_",
    )


# ByWater "Koha branches that contain this bug" tool
@app.message(re.compile("(branches)\s*(\d+)\s*(\S*)"))
def bug_regex(say, context):
    """Find Koha branches containing a bug.

    Responds to ``branches <bug_id> [shortname]`` by querying a helper service
    that returns a list of branches where the bug is present.

    Args:
        say: Function to send a response back to Slack.
        context: Dictionary containing regex matches; ``matches[1]`` is the bug
            ID and ``matches[2]`` is an optional shortname.
    """
    bug = context["matches"][1]
    shortname = context["matches"][2] or "bywater"
    print(f"BUG: {bug}, SHORTNAME: {shortname}")

    say(
        text=f"Looking for bug {bug} ( https://bugs.koha-community.org/bugzilla3/show_bug.cgi?id={bug} ) on {shortname} branches..."
    )

    url = f"https://find-branches-by-bugs.tools.bywatersolutions.com/{bug}/{shortname}"
    print(f"URL: {url}")
    res = requests.get(url)
    text = res.text
    data = json.loads(text)
    pp.pprint(data)

    if len(data):
        text = f"I found bug {bug} in the following branches:\n"
        for d in data:
            text += f"* {d}\n"
        say(text=text)
    else:
        say(text=f"I could not find bug {bug} in any branches for {shortname}!")


# ByWater Weekend Updater, sends sms to person on weekend duty
@app.message(re.compile("Ticket Created:\s+\*\[(.+)\]\*\s+(\d+)\s+-\s+(.*)"))
def bug_regex(say, context):
    """Notify weekend duty on ticket creation.

    Triggered by messages matching ``Ticket Created: *[queue]* <id> - <desc>``.
    Looks up the on‑call user for the weekend and sends an SMS via Twilio.

    Args:
        say: Function to send a response back to Slack.
        context: Dictionary containing regex matches for queue, ticket ID, and
            description.
    """
    queue = context["matches"][1]
    ticket = context["matches"][1]
    description = context["matches"][2]

    print(f"TICKET: {ticket}, QUEUE: {queue}, DESC: {description}")

    event = get_weekend_duty()
    if event:
        print(event)
        ## FIXME: We need to pass in bywaterbot_data["users"] and just have get_user look to see if the calendard
        ## event containers the name of that user. Solves the problem of needing a specifc format for the calendar
        ## event ( e.g. "Someones Name help desk" )
        user = get_user(event)
        print("FOUND USER: ", user)
        transports = bywaterbot_data["users"][user]
        if transports["sms"]:
            sms = transports["sms"]
            say(text=f"I've alerted {user} via sms!")

            body = f"New {queue} ticket {ticket}: {description} https://ticket.bywatersolutions.com/Ticket/Display.html?id={ticket}"
            message = twilio_client.messages.create(
                body=body, from_=twilio_phone, to=sms
            )
            print(message.sid)

        if len(transports) == 0:
            say(text=f"{user} has not opted to receive alerts from me!")


@app.message(re.compile("test sms (.*)"))
def test_sms(say, context):
    """Send a test SMS to the specified user."""
    user = context["matches"][0]

    if user not in bywaterbot_data["users"]:
        say(text=f"I couldn't find a user named {user} in my records!")
        return

    transports = bywaterbot_data["users"][user]
    if "sms" in transports and transports["sms"]:
        sms = transports["sms"]
        say(text=f"I've alerted {user} via sms!")

        body = f"This is a test SMS from the ByWater Slack bot."
        message = twilio_client.messages.create(body=body, from_=twilio_phone, to=sms)
        print(message.sid)
    else:
        say(text=f"{user} does not have an SMS number configured!")


# Text someone from slack
@app.message(re.compile("TEXT (.*)"))
def bug_regex(say, context):
    """Relay a Slack message to a user via SMS.

    Handles ``TEXT <user> <message>`` commands, looks up the target user in the
    configuration, and forwards the message using Twilio.

    Args:
        say: Function to send a response back to Slack.
        context: Dictionary containing the raw message text.
    """
    pp.pprint(context)
    message = context["matches"][0]

    print(f"MESSAGE: {message}")

    sender = context["user_id"]
    try:
        # Call the users.info method using the WebClient
        response = app.client.users_info(user=sender)
    except SlackApiError as e:
        print("Error fetching conversations: {}".format(e))
    origin_user = response.data["user"]["real_name"]

    destination_user_found = False
    for user in bywaterbot_data["users"]:
        print(f"LOOKING AT USER {user}")
        if message.startswith(user):
            message = message.replace(user, "", 1)
            transports = bywaterbot_data["users"][user]
            sms = transports["sms"]

            print(f"FOUND MATCHING USER {user}")

            body = f"You have a message from {origin_user} via Slack: {message}"
            print(body)
            message = twilio_client.messages.create(
                body=body, from_=twilio_phone, to=sms
            )
            print(message.sid)
            destination_user_found = True
            break

    if destination_user_found == True:
        say("Message sent!")
    else:
        say("I was unable to find someone matching that user.")


def handle_devops_fires(body, logger):
    """Monitor #devops channel for fire emoji events.

    When a fire emoji is added, extracts the on‑call assignee from the channel
    topic and sends an alert via SMS.

    Args:
        body: Event payload from Slack.
        logger: Logger instance for debugging.
    """
    """
    Monitor #devops channel for messages containing fire emoji or reactions with fire emoji.
    When found, check the channel topic for a name using regex "is NAME".
    """
    event = body.get("event")

    # For reactions, get the channel ID from the item field
    if event.get("type") == "reaction_added":
        channel_id = event.get("item").get("channel")
    else:
        channel_id = event.get("channel")

    print("CHANNEL ID: ", channel_id)

    # Only process events in #devops channel
    if channel_id != devops_channel_id:
        return

    assignee = ""
    text = ""

    # Check if this is a reaction event
    if event.get("type") == "reaction_added":
        reaction = event.get("reaction")
        print("REACTION: ", reaction)
        if reaction == "fire":
            # Get the message text from the reaction
            try:
                message_ts = event.get("item", {}).get("ts")
                if message_ts:
                    response = app.client.conversations_history(
                        channel=channel_id, inclusive=True, latest=message_ts, limit=1
                    )
                    messages = response.get("messages")
                    if messages:
                        text = messages[0].get("text")
                        print(f"Found message text: {text}")
            except Exception as e:
                print(f"Error getting message text: {e}")
                text = ""  # Default empty text if we can't get it

            assignee = get_devops_fire_duty_asignee(app, channel_id)

    if assignee:
        print(f"{assignee} is on duty for devops")

        if assignee not in bywaterbot_data["users"]:
            body = f"There is a fire in #devops assigned to {assignee}: {text}"
            assignee = DEFAULT_DEVOPS_ASSIGNEE
        else:  # User cannot be contacted
            body = f"There is a fire in #devops: {text}"

        transports = bywaterbot_data["users"][assignee]
        print(f"TRANSPORTS: {transports}")
        sms = transports["sms"]

        print(f"BODY: {body}")
        message = twilio_client.messages.create(body=body, from_=twilio_phone, to=sms)
        print(f"TWILIO SMS SENT TO {assignee}: {message.sid}")


@app.event("reaction_added")
def handle_reaction_events(body, logger):
    """Entry point for reaction events.

    Delegates to ``handle_devops_fires`` to process fire‑emoji reactions.

    Args:
        body: Event payload from Slack.
        logger: Logger instance.
    """
    handle_devops_fires(body, logger)


# @app.event("message")
# def handle_message_events(body, logger):
#    print("MESSAGE EVENT")
#    print(body)

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
