"""
Contact Handlers Module

Lets staff manage their own entry in bywaterbot_data ( data.json ) from a DM:
- claim <name>          link your Slack account to your duty-calendar name
- set my sms <number>   set the mobile number used for your duty alerts
- my info               show the name and ( masked ) number on file for you

Updates are self-service only ( you can edit just your own entry, matched by
your Slack user id ) and are committed back to the canonical source via
bot_functions.write_bywaterbot_data so they survive the hourly refresh.
"""

import re

import config
from bot_functions import read_bywaterbot_data_for_update, write_bywaterbot_data
from message_matchers import is_direct_message

CLAIM_RE = re.compile(r"^\s*claim\s+(.+)", re.IGNORECASE)
SET_SMS_RE = re.compile(
    r"^\s*(?:set|update)\s+my\s+(?:sms|number|phone|cell)(?:\s+(?:to|is|=))?\s+(.+)",
    re.IGNORECASE,
)
MY_INFO_RE = re.compile(r"^\s*(?:my\s+(?:contact\s+)?info|whoami)\s*$", re.IGNORECASE)


def normalize_phone(raw):
    """Return a phone number in E.164 form ( e.g. +12025550123 ), or None.

    Accepts common typed formats ( spaces, dashes, parens ) and assumes a US
    number when given 10 digits or 11 digits starting with 1.
    """
    raw = raw.strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)

    if has_plus:
        return "+" + digits if 7 <= len(digits) <= 15 else None
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    if 7 <= len(digits) <= 15:
        return "+" + digits
    return None


def _mask_phone(sms):
    """Show only the last 4 digits of a phone number for display."""
    return "***-***-" + sms[-4:] if sms else ""


def _find_user_by_slack_id(users, slack_id):
    """Return the user-key whose entry is claimed by slack_id, or None."""
    for name, info in users.items():
        if isinstance(info, dict) and info.get("slack_id") == slack_id:
            return name
    return None


def register_contact_handlers(app):

    # Link your Slack account to your duty-calendar name, e.g. "claim Laura O"
    @app.message(CLAIM_RE, matchers=[is_direct_message])
    def claim_name(message, say, context):
        """Claim ( or create ) the contact entry for the requester's name ( DM-only )."""
        slack_id = message.get("user")
        requested = context["matches"][0].strip()
        if not requested:
            say("Tell me which name to claim, e.g. `claim Laura O`.")
            return

        data, ctx = read_bywaterbot_data_for_update()
        if data is None:
            say("I couldn't read the contact list right now — try again in a moment.")
            return

        users = data.setdefault("users", {})

        # Match an existing key case-insensitively so we don't create duplicates
        target = None
        for name in users:
            if name.lower() == requested.lower():
                target = name
                break
        if target is None:
            target = requested
            users[target] = {}
        elif not isinstance(users[target], dict):
            users[target] = {}

        owner_id = users[target].get("slack_id")
        if owner_id and owner_id != slack_id:
            say(
                f"*{target}* is already claimed by someone else. "
                "If that's a mistake, ask an admin to fix it."
            )
            return

        # One name per person: drop my id from any other entry I'd claimed
        for name, info in users.items():
            if name != target and isinstance(info, dict):
                if info.get("slack_id") == slack_id:
                    info.pop("slack_id", None)

        users[target]["slack_id"] = slack_id

        if write_bywaterbot_data(
            data, ctx, f"Claim contact entry {target} via ByWaterBot"
        ):
            config.bywaterbot_data = data
            msg = f"You're now linked to *{target}*."
            if not users[target].get("sms"):
                msg += " Set your number with `set my sms <number>`."
            say(msg)
        else:
            say("I couldn't save that just now — please try again.")

    # Set the mobile number used for your duty alerts, e.g. "set my sms +1..."
    @app.message(SET_SMS_RE, matchers=[is_direct_message])
    def set_my_sms(message, say, context):
        """Update the requester's own SMS number ( DM-only )."""
        slack_id = message.get("user")
        raw = context["matches"][0]
        number = normalize_phone(raw)
        if not number:
            say(
                f"`{raw.strip()}` doesn't look like a phone number. "
                "Try `set my sms +12025550123`."
            )
            return

        data, ctx = read_bywaterbot_data_for_update()
        if data is None:
            say("I couldn't read the contact list right now — try again in a moment.")
            return

        users = data.setdefault("users", {})
        name = _find_user_by_slack_id(users, slack_id)
        if not name:
            say(
                "You haven't claimed your name yet. DM me `claim <YourName>` first "
                "( use the name on the weekend/fire-duty calendar )."
            )
            return

        users[name]["sms"] = number
        if write_bywaterbot_data(data, ctx, f"Update SMS for {name} via ByWaterBot"):
            config.bywaterbot_data = data
            say(f"Done! I'll use {_mask_phone(number)} for *{name}*.")
        else:
            say("I couldn't save that just now — please try again.")

    # Show the name and masked number on file for the requester
    @app.message(MY_INFO_RE, matchers=[is_direct_message])
    def my_info(message, say):
        """Show the requester their own contact entry ( DM-only )."""
        slack_id = message.get("user")
        users = config.bywaterbot_data.get("users", {})
        name = _find_user_by_slack_id(users, slack_id)
        if not name:
            say(
                "You haven't claimed a name yet. DM me `claim <YourName>` "
                "( the name on the weekend/fire-duty calendar )."
            )
            return

        sms = users[name].get("sms")
        say(f"*{name}* — SMS: {_mask_phone(sms) if sms else 'not set'}")
