import os
import re
import pprint
import requests
import json
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

pp = pprint.PrettyPrinter(indent=2)

@app.message("hello")
def message_hello(message, say):
    # say() sends a message to the channel where the event was triggered
    say(f"Hey there <@{message['user']}>!")

# Koha bugzilla links, recognizes "bug 1234" and "bz 1234"
@app.message(re.compile("(bug|bz)\s*([0-9]+)"))
def bug_regex(say, context):
    # regular expression matches are inside of context.matches
    #pp.pprint(context)
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
                },
                {
                    "type": "mrkdwn",
                    "text": f"<{bugzilla}|View bug {bug} in Bugzilla>"
                }
            ]
        }
    ]
    say(
        blocks=blocks,
        text=f"Koha community <{bugzilla}|bug {bug}>: _{summary}_ [*{status}*]"
    )

# Koha bugzilla links, recognizes "bug 1234" and "bz 1234"
@app.message(re.compile("(ticket|rt)\s*([0-9]+)"))
def bug_regex(say, context):
    ticket_id = context['matches'][1]

    rt_url = f"https://ticket.bywatersolutions.com/Ticket/Display.html?id={ticket_id}"

#   blocks = [{
#     "type": "section",
#     "text": {"type": "mrkdwn", "text": f"<{rt_url}|RT Ticket {ticket_id}"},
#   }]
#   say(
#       blocks=blocks,
#       text=f"Ticket {ticket_id}: https://ticket.bywatersolutions.com/Ticket/Display.html?id={ticket_id}"
#   )

    say(
        text=f"<{rt_url}|RT Ticket {ticket_id}>"
    )

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
