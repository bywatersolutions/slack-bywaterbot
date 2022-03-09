import random
import csv
import os
import re
import pprint
import requests
import json
import urllib.request
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Initializes your app with your bot token and socket mode handler
slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
app = App(token=slack_bot_token)
pp = pprint.PrettyPrinter(indent=2)

# Load quotes
quotes_csv_url = os.environ.get("QUOTES_CSV_URL")
urllib.request.urlretrieve(quotes_csv_url, 'quotes.csv')
quotes = []
with open('quotes.csv') as csvfile: 
    reader = csv.reader(csvfile, delimiter=',', quotechar='"') 
    for row in reader:
        if len(row[0]):
            quotes.append(row[0])
quote = random.choice(quotes)
if quote.startswith("PQ: "):
    quote = quote.replace("PQ: ", "Partner Quote: ", 1);
elif quote.startswith("HAHA: "):
    quote = quote.replace("HAHA: ", "", 1);
elif quote.startswith("MOVE: "):
    quote = quote.replace("MOVE: ", "Get up and move! ", 1);
elif quote.startswith("FACT: "):
    quote = quote.replace("FACT: ", "Fun Fact! ", 1);
elif quote.startswith("Koha sys pref: "):
    quote = quote.replace("Koha sys pref: ", "Koha SysPref Quiz! Do you know what this setting does?", 1);
app.client.chat_postMessage(
    channel="#general",
    text=quote,
)

# Get all Slack users and make a dictionary of name ( e.g. display name ) to user id
name_to_id = {}
resp = app.client.users_list()
users = resp['members']
for u in users:
    name_to_id[u["profile"]["display_name"].lower()] = u["id"]
    if "name" in u and not u["name"].lower() in name_to_id:
        name_to_id[u["name"].lower()] = u["id"]
    if "real_name" in u and not u["real_name"].lower() in name_to_id:
        name_to_id[u["real_name"].lower()] = u["id"]

# Load karma pep talks from csv
karma_csv_url = os.environ.get("KARMA_CSV_URL")
urllib.request.urlretrieve(karma_csv_url, 'karma.csv')
karma1, karma2, karma3, karma4 = [], [], [], []
with open('karma.csv') as csvfile: 
    reader = csv.reader(csvfile, delimiter=',', quotechar='"') 
    for row in reader:
        if len(row[0]):
            karma1.append(row[0])
        if len(row[1]):
            karma2.append(row[1])
        if len(row[2]):
            karma3.append(row[2])
        if len(row[3]):
            karma4.append(row[3])

# Handle Karma
@app.message(re.compile("(\S*)(\s?\+\+\s?)(.*)?"))
def karma_regex(say, context):
    user = context['matches'][0];

    is_user = False

    if ( user.startswith("<@" ) ):
        is_user = True
    elif ( not user.startswith("<@") ) and user.lower() in name_to_id:
        user = f"<@{name_to_id[user.lower()]}>"
        is_user = True

    if is_user:
        say(
            text=f"{user} {random.choice(karma1)} {random.choice(karma2)} {random.choice(karma3)} {random.choice(karma4)}"
        )
    else:
        say(
            text=f"Who doesn't love {user}, right?"
        )

@app.message("hello")
def message_hello(message, say):
    # say() sends a message to the channel where the event was triggered
    say(f"Hey there <@{message['user']}>!")

# Koha bugzilla links, recognizes "bug 1234" and "bz 1234"
@app.message(re.compile("(bug|bz)\s*([0-9]+)"))
def bug_regex(say, context):
    # regular expression matches are inside of context.matches
    # pp.pprint(context)
    bug = context['matches'][1]
    url = requests.get(f"https://bugs.koha-community.org/bugzilla3/rest/bug/{bug}")
    text = url.text
    data = json.loads(text)

    summary = data['bugs'][0]['summary']
    status = data['bugs'][0]['status']
    bugzilla = f"https://bugs.koha-community.org/bugzilla3/show_bug.cgi?id={bug}"

    print(f"BUG: {bug}")
    print(f"SUMMARY: {summary}")
    print(f"STATUS: {status}")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Bug {bug}: {summary}"
              }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Status*\n{status}"
                }
            ]
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": f"View bug {bug}"

                    },
                    "style": "primary",
                    "value": f"View bug {bug}",
                    "url":  f"{bugzilla}"
                }
            ]
        }
    ]
    say(
        blocks=blocks,
        text=f"Koha community <{bugzilla}|bug {bug}>: _{summary}_ [*{status}*]"
    )

# ByWater "Koha branches that contain this bug" tool
@app.message(re.compile("(branches)\s*(\d+)\s*(\w*)"))
def bug_regex(say, context):
    bug = context['matches'][1]
    shortname = context['matches'][2] or "bywater"
    print(f"BUG: {bug}, SHORTNAME: {shortname}")

    say( text=f"Looking for bug {bug} on {shortname} branches..." )

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
        say( text=text )
    else:
        say( text=f"I could not find bug {bug} in any branches for {shortname}!" )

# Koha bugzilla links, recognizes "bug 1234" and "bz 1234"
@app.message(re.compile("(ticket|rt)\s*([0-9]+)"))
def bug_regex(say, context):
    ticket_id = context['matches'][1]

    rt_url = f"https://ticket.bywatersolutions.com/Ticket/Display.html?id={ticket_id}"

    say(
        text=f"<{rt_url}|RT Ticket {ticket_id}>"
    )

@app.event("message")
def handle_message_events(body, logger):
    logger.info(body)

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
