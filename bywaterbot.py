import json
import os
import pprint
import random
import re
import requests
import rt
import urllib.request
from bot_functions import (
    get_name_to_id_mapping,
    get_karma_pep_talks,
    get_quote,
    get_putdowns,
)
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

print("ByWaterBot is starting up!")

# Initializes your app with your bot token and socket mode handler
slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
app = App(token=slack_bot_token)
pp = pprint.PrettyPrinter(indent=2)

# Give a quote on startup
quotes_csv_url = os.environ.get("QUOTES_CSV_URL")
quote = get_quote(url=quotes_csv_url)
app.client.chat_postMessage(
    channel="#general",
    text=quote,
)

# Get all Slack users and make a dictionary of name ( e.g. display name ) to user id
name_to_id = get_name_to_id_mapping(app=app)

# Load karma pep talks from csv
karma_csv_url = os.environ.get("KARMA_CSV_URL")
karma1, karma2, karma3, karma4 = get_karma_pep_talks(url=karma_csv_url)

putdowns = get_putdowns()

# Handle Karma
@app.message(re.compile("(\S*)(\s?\+\+\s?)(.*)?"))
def karma_regex(say, context):
    user = context["matches"][0]

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
@app.message(re.compile("(\S*)(\s?\-\-\s?)(.*)?"))
def karma_regex(say, context):
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
    say(f"Hey there <@{message['user']}>!")


@app.message("Quote Please")
def say_quote(message, say):
    quotes_csv_url = os.environ.get("QUOTES_CSV_URL")
    quote = get_quote(url=quotes_csv_url)
    app.client.chat_postMessage(
        channel="#general",
        text=quote,
    )
    say(quote)


@app.message("Refresh Karma")
def refresh_karma(message, say):
    say(f"Sure thing!!")
    karma1, karma2, karma3, karma4 = get_karma_pep_talks(url=karma_csv_url)
    say(f"Done!")


# Koha bugzilla links, recognizes "bug 1234" and "bz 1234"
@app.message(re.compile("(bug|bz)\s*([0-9]+)"))
def bug_regex(say, context):
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
@app.message(re.compile("(branches)\s*(\d+)\s*(\w*)"))
def bug_regex(say, context):
    bug = context["matches"][1]
    shortname = context["matches"][2] or "bywater"
    print(f"BUG: {bug}, SHORTNAME: {shortname}")

    say(text=f"Looking for bug {bug} on {shortname} branches...")

    url = f"http://find-branches-by-bugs.bwsdocker1.bywatersolutions.com/{bug}/{shortname}"
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


@app.event("message")
def handle_message_events(body, logger):
    logger.info(body)


# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
