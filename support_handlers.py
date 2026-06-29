"""
Support Handlers Module

Contains message handlers for:
- Koha Bugzilla lookup (bug/bz <id>)
- Zoho Desk ticket lookup (ticket/zd <id>)
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
from bot_functions import get_channel_id_by_name
from zoho_functions import zoho_configured, get_zoho_ticket
from message_matchers import is_not_bot_message

pp = pprint.PrettyPrinter(indent=2)


def resolve_weekend_duty_user():
    """Return (event, user, sms) for whoever is on weekend duty now.

    user is None if there's no current event or the summary can't be parsed;
    sms is None if the user isn't in bywaterbot_data or has no number on file.
    """
    event = get_weekend_duty()
    if not event:
        return None, None, None
    user = get_user(event)
    sms = None
    if user and user in config.bywaterbot_data.get("users", {}):
        sms = config.bywaterbot_data["users"][user].get("sms")
    return event, user, sms


def _mask_sms(sms):
    """Show only the last 4 digits of a phone number for display."""
    return "***-***-" + sms[-4:] if sms else ""


def register_ticket_notifier(app):
    """Register the #tickets new-ticket SMS notifier.

    This has to be registered before every other message handler. Bolt runs
    only the first @app.message listener that matches an incoming message, and
    the Zoho Flow "New Ticket" post also matches broader handlers: the help
    command's 'help' trigger matches the word 'help' inside the
    help.bywatersolutions.com case link, and the ticket-lookup handler matches
    the "ZD #NNNN" in the post. If any of those win first, this notifier never
    runs and nobody on weekend duty gets texted. Registering it first lets the
    specific "New Ticket" pattern win.
    """

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


def register_support_handlers(app):

    # Resolve the #tickets channel id once so the weekend-duty test command can
    # restrict itself to that channel (fail closed if we can't find it)
    try:
        tickets_channel_id = get_channel_id_by_name(app=app, channel_name="tickets")
        print(f"TICKETS CHANNEL ID: {tickets_channel_id}")
    except Exception as e:
        print(f"Error getting tickets channel ID: {e}")
        tickets_channel_id = None

    def in_tickets_channel(message):
        """Listener matcher: only match messages posted in #tickets."""
        return tickets_channel_id is not None and (
            message.get("channel") == tickets_channel_id
        )

    # Koha bugzilla links, recognizes "bug 1234" and "bz 1234"
    @app.message(re.compile(r"(bug|bz)\s*([0-9]+)"), matchers=[is_not_bot_message])
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

    # Zoho Desk links, recognizes "ticket 1234", "zd 1234" and "zd #1234".
    # is_not_bot_message keeps this off the Zoho Flow "New Ticket" announcement
    # ( which contains "ZD #NNNN" ) so it neither does a second lookup nor shadows
    # the new-ticket notifier.
    @app.message(
        re.compile(r"(ticket|zd)\s*#?\s*([0-9]+)", re.IGNORECASE),
        matchers=[is_not_bot_message],
    )
    def handle_zoho_ticket(say, context, message):
        """Look up a Zoho Desk ticket by its ZD number and post its details."""
        ticket_number = context["matches"][1]

        if not zoho_configured():
            say("Zoho Desk credentials are not configured!")
            return

        try:
            ticket = get_zoho_ticket(ticket_number)
            if not ticket:
                say(f"Ticket ZD #{ticket_number} not found.")
                return

            subject = ticket.get("subject") or "(no subject)"
            status = ticket.get("status") or "Unknown"
            priority = ticket.get("priority") or "—"

            assignee = ticket.get("assignee") or {}
            assignee_name = (
                " ".join(
                    filter(None, [assignee.get("firstName"), assignee.get("lastName")])
                )
                or "Unassigned"
            )

            contact = ticket.get("contact") or {}
            contact_name = (
                " ".join(
                    filter(None, [contact.get("firstName"), contact.get("lastName")])
                )
                or "—"
            )
            account = (contact.get("account") or {}).get("accountName") or "—"

            web_url = ticket.get("webUrl") or "https://help.bywatersolutions.com"

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Ticket ZD #{ticket_number}: {subject}"[:150],
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Status*\n{status}"},
                        {"type": "mrkdwn", "text": f"*Priority*\n{priority}"},
                        {"type": "mrkdwn", "text": f"*Assignee*\n{assignee_name}"},
                        {"type": "mrkdwn", "text": f"*Partner*\n{account}"},
                        {"type": "mrkdwn", "text": f"*Requestor*\n{contact_name}"},
                    ],
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": f"View ticket {ticket_number}",
                            },
                            "style": "primary",
                            "value": f"View ticket {ticket_number}",
                            "url": web_url,
                        }
                    ],
                },
            ]
            say(
                blocks=blocks,
                text=f"<{web_url}|Ticket ZD #{ticket_number}>: _{subject}_ [*{status}*]",
            )
        except Exception as e:
            print(f"Error fetching Zoho ticket {ticket_number}: {e}")
            say(f"Error fetching ticket ZD #{ticket_number}.")

    # ByWater "Koha branches that contain this bug" tool
    @app.message(
        re.compile(r"(branches)\s*(\d+)\s*(\S*)"), matchers=[is_not_bot_message]
    )
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

    # Weekend duty self-test, #tickets only:
    #   "test weekend duty"      -> dry run, report who'd be alerted, no SMS
    #   "test weekend duty sms"  -> send a real test SMS to the on-duty person
    @app.message(
        re.compile(r"test weekend duty(\s+sms)?", re.IGNORECASE),
        matchers=[in_tickets_channel],
    )
    def handle_weekend_duty_test(say, context, message):
        """Exercise the weekend-duty alert path on demand from #tickets."""
        send_sms = bool(context["matches"][0])  # group 1 = " sms" when present
        event, user, sms = resolve_weekend_duty_user()

        if not event:
            say(
                text="🧪 Weekend duty test: no current weekend duty event on the calendar."
            )
            return

        summary = event.get("summary", "")
        if not user:
            say(
                text=f"🧪 Weekend duty test: found event '{summary}' but couldn't parse who's on duty."
            )
            return

        if not sms:
            say(
                text=f"🧪 Weekend duty test: *{user}* is on duty (event: '{summary}'), but I have no SMS number for them."
            )
            return

        masked = _mask_sms(sms)
        if not send_sms:
            say(
                text=(
                    f"🧪 Weekend duty test (dry run): *{user}* is on duty (event: '{summary}'). "
                    f"✅ SMS on file: {masked}. I would alert them. No SMS sent."
                )
            )
            return

        body = "TEST: weekend-duty alert check from #tickets, please ignore."
        sent = False
        if config.twilio_client:
            try:
                msg = config.twilio_client.messages.create(
                    body=body, from_=config.twilio_phone, to=sms
                )
                print(msg.sid)
                sent = True
            except Exception as e:
                print(f"Error sending test SMS: {e}")
        if sent:
            say(text=f"🧪 Weekend duty test: sent a test SMS to *{user}* ({masked}).")
        else:
            say(
                text=f"🧪 Weekend duty test: *{user}* is on duty ({masked}) but the SMS didn't send (Twilio not configured or errored)."
            )

    # Text someone from slack
    @app.message(re.compile("TEXT (.*)"), matchers=[is_not_bot_message])
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
