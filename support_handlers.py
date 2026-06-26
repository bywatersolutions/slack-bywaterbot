"""
Support Handlers Module

Contains message handlers for:
- Koha Bugzilla lookup (bug/bz <id>)
- RT Ticket lookup (ticket/rt <id>)
- Bug branch lookup (branches <id>)
- Ticket creation notifications (detects "*New Ticket:*" from Zoho Flow)
- SMS relay (TEXT <user> <message>)
"""

import pprint
import requests
import json
import re

import config
from calendar_functions import get_weekend_duty, get_user

pp = pprint.PrettyPrinter(indent=2)


def register_support_handlers(app):

    # Koha bugzilla links, recognizes "bug 1234" and "bz 1234"
    @app.message(re.compile(r"(bug|bz)\s*([0-9]+)"))
    def handle_koha_bug(say, context):
        """Lookup a Koha bug and post its details."""
        bug = context["matches"][1]
        try:
            url = requests.get(
                f"https://bugs.koha-community.org/bugzilla3/rest/bug/{bug}"
            )
            text = url.text
            data = json.loads(text)

            summary = data["bugs"][0]["summary"]
            status = data["bugs"][0]["status"]
            bugzilla = (
                f"https://bugs.koha-community.org/bugzilla3/show_bug.cgi?id={bug}"
            )

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
        except Exception as e:
            print(f"Error fetching bug {bug}: {e}")
            say(
                f"I couldn't find details for bug {bug}. It might not exist or the API is down."
            )

    # RT links, recognizes "ticket 1234" and "rt 1234"
    @app.message(re.compile(r"(ticket|rt)\s*([0-9]+)"))
    def handle_rt_ticket(say, context):
        """Lookup an RT ticket and post its details."""
        ticket_id = context["matches"][1]

        rt_user = os.environ.get("RT_USERNAME")
        rt_pass = os.environ.get("RT_PASSWORD")

        if not rt_user or not rt_pass:
            say("RT credentials are not configured!")
            return

        try:
            tracker = rt.Rt(
                "https://ticket.bywatersolutions.com/REST/1.0/", rt_user, rt_pass
            )
            tracker.login()

            tickets = tracker.search(Queue=rt.ALL_QUEUES, raw_query=f"id='{ticket_id}'")

            if not tickets:
                say(f"Ticket {ticket_id} not found.")
                return

            # ticket = tracker.get_ticket(ticket_id=ticket_id) # Seemingly unused or redundant with search

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
                    "text": {
                        "type": "plain_text",
                        "text": f"Ticket {ticket_id}: {subject}",
                    },
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
                            "text": {
                                "type": "plain_text",
                                "text": f"View ticket {ticket_id}",
                            },
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
        except Exception as e:
            print(f"Error fetching ticket {ticket_id}: {e}")
            say(f"Error fetching ticket {ticket_id}.")

    # ByWater "Koha branches that contain this bug" tool
    @app.message(re.compile(r"(branches)\s*(\d+)\s*(\S*)"))
    def handle_branches(say, context):
        """Find Koha branches containing a bug."""
        bug = context["matches"][1]
        shortname = context["matches"][2] or "bywater"
        print(f"BUG: {bug}, SHORTNAME: {shortname}")

        say(
            text=f"Looking for bug {bug} ( https://bugs.koha-community.org/bugzilla3/show_bug.cgi?id={bug} ) on {shortname} branches..."
        )

        try:
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
        except Exception as e:
            print(f"Error finding branches for bug {bug}: {e}")
            say(f"Error finding branches for bug {bug}.")

    # ByWater Weekend Updater, sends sms to person on weekend duty.
    # Matches the "New Ticket" notifications Zoho Flow posts to #tickets, e.g.:
    #   *New Ticket:* ZD #215390 - Libby Authentication
    #   *Product:* Koha
    #   *Partner:* Waterford Township Public Library
    @app.message(re.compile(r"\*New Ticket:\*\s+ZD\s+#(\d+)\s+-\s+(.+)"))
    def handle_ticket_created(say, context, message):
        """Notify weekend duty on ticket creation."""
        ticket = context["matches"][0]
        subject = context["matches"][1].strip()

        # Product, Partner and the case URL live on their own lines in the message
        text = message.get("text", "")

        product_match = re.search(r"\*Product:\*\s*(.+)", text)
        product = product_match.group(1).strip() if product_match else ""

        partner_match = re.search(r"\*Partner:\*\s*(.+)", text)
        partner = partner_match.group(1).strip() if partner_match else ""

        # The Zoho Desk case link, e.g. <https://help.bywatersolutions.com/.../dv/123>
        url_match = re.search(r"<(https?://help\.bywatersolutions\.com/[^>]+)>", text)
        ticket_url = url_match.group(1) if url_match else ""

        print(
            f"TICKET: {ticket}, PRODUCT: {product}, PARTNER: {partner}, SUBJECT: {subject}"
        )

        event = get_weekend_duty()
        if event:
            print(event)
            user = get_user(event)
            print("FOUND USER: ", user)

            if user in config.bywaterbot_data["users"]:
                transports = config.bywaterbot_data["users"][user]
                if transports.get("sms"):
                    sms = transports["sms"]
                    say(text=f"I've alerted {user} via sms!")

                    # Product/Partner can be blank on some tickets, so build the
                    # message a piece at a time and only include what we have
                    descriptor = f"{product} ticket" if product else "ticket"
                    body = f"New {descriptor} ZD #{ticket}"
                    if partner:
                        body += f" for {partner}"
                    body += f": {subject}"
                    if ticket_url:
                        body += f" {ticket_url}"
                    try:
                        if config.twilio_client:
                            message = config.twilio_client.messages.create(
                                body=body, from_=config.twilio_phone, to=sms
                            )
                            print(message.sid)
                    except Exception as e:
                        print(f"Error sending SMS: {e}")
                        say(f"Failed to send SMS to {user}.")
                else:
                    say(text=f"{user} does not have an SMS number configured!")
            else:
                say(text=f"{user} not found in my records for alerts.")
        else:
            print("No weekend duty event found.")

    # Text someone from slack
    @app.message(re.compile("TEXT (.*)"))
    def handle_text_command(say, context):
        """Relay a Slack message to a user via SMS."""
        message_text = context["matches"][0]
        sender = context["user_id"]

        try:
            # Call the users.info method using the WebClient
            response = app.client.users_info(user=sender)
            origin_user = response.data["user"]["real_name"]
        except Exception as e:
            print(f"Error details: {e}")
            origin_user = "Unknown User"

        destination_user_found = False
        for user in config.bywaterbot_data["users"]:
            if message_text.startswith(user):
                message_body = message_text.replace(user, "", 1).strip()
                transports = config.bywaterbot_data["users"][user]
                if transports.get("sms"):
                    sms = transports["sms"]

                    body = f"You have a message from {origin_user} via Slack: {message_body}"
                    try:
                        if config.twilio_client:
                            message = config.twilio_client.messages.create(
                                body=body, from_=config.twilio_phone, to=sms
                            )
                            print(message.sid)
                            destination_user_found = True
                            say("Message sent!")
                    except Exception as e:
                        print(f"Twilio error: {e}")
                        say("Failed to send SMS via Twilio.")
                else:
                    say(f"{user} has no SMS number configured.")
                    destination_user_found = True  # User found but no SMS
                break

        if not destination_user_found:
            say("I was unable to find someone matching that user.")
