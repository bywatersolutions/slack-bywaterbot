"""
Bot Functions Module

Provides utility functions for the ByWater Slack bot, including channel lookup,
user mapping, data retrieval, and message handling.
"""

import json
import os
import random
import re
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

SHEETS_API_URL = "https://sheets.googleapis.com/v4/spreadsheets"


def load_bywaterbot_data():
    """Load bywaterbot_data from the Google Sheet, environment variable, or local file."""
    data = None
    source = ""

    # Try to load from the Google Sheet first
    if os.environ.get("BYWATER_BOT_SHEET_ID") and os.environ.get(
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    ):
        print("Loading bywaterbot_data from Google Sheet")
        data = get_data_from_sheet(os.environ["BYWATER_BOT_SHEET_ID"])
        if data:
            print("Successfully loaded bywaterbot_data from Google Sheet")
            source = "Google Sheet"

    # Fall back to environment variable
    if not data and os.environ.get("BYWATER_BOT_DATA"):
        try:
            print("Loading bywaterbot_data from environment variable")
            data = json.loads(os.environ.get("BYWATER_BOT_DATA"))
            source = "environment variable"
        except json.JSONDecodeError as e:
            print(f"Error parsing BYWATER_BOT_DATA: {e}")

    # Fall back to local file
    if not data and os.path.exists("data.json"):
        try:
            with open("data.json") as f:
                print("Loading bywaterbot_data from local file")
                data = json.load(f)
                source = "local file"
        except Exception as e:
            print(f"Error loading data.json: {e}")

    if data:
        print(f"Successfully loaded bywaterbot_data from {source}")
        return data
    else:
        print("Failed to load bywaterbot_data from any source")
        raise Exception("Failed to load bywaterbot_data from any source")


def _sheet_session():
    """Return a requests session authorized as the bot's Google service account."""
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return AuthorizedSession(creds)


def _sheet_users(rows):
    """Turn the 'users' tab ( name, sms, slack_id ) into the bywaterbot_data users map.

    Row 1 is the header. Also returns each name's sheet row number so a write
    can put every entry back on the row it came from.
    """
    users = {}
    row_numbers = {}
    for row_number, row in enumerate(rows[1:], start=2):
        name, sms, slack_id = (list(row) + ["", "", ""])[:3]
        name = name.strip()
        if not name:
            continue

        info = {}
        if sms.strip():
            info["sms"] = sms.strip()
        if slack_id.strip():
            info["slack_id"] = slack_id.strip()
        users[name] = info
        row_numbers[name] = row_number
    return users, row_numbers


def get_data_from_sheet(sheet_id):
    """Fetch bywaterbot_data from the tabs of the Google Sheet.

    Args:
        sheet_id: The spreadsheet id from the sheet's URL.

    Returns:
        The bywaterbot_data dict if successful, otherwise None.
    """
    try:
        response = _sheet_session().get(
            f"{SHEETS_API_URL}/{sheet_id}/values:batchGet",
            params={
                "ranges": [
                    "users",
                    "partners",
                    "settings",
                    "karma",
                    "quotes",
                    "putdowns",
                ]
            },
            timeout=10,
        )
        response.raise_for_status()
        (
            users_tab,
            partners_tab,
            settings_tab,
            karma_tab,
            quotes_tab,
            putdowns_tab,
        ) = response.json()["valueRanges"]

        users, _ = _sheet_users(users_tab.get("values", []))

        # One row per partner: product ( innreach / rapido ), partner
        partners = {}
        for row in partners_tab.get("values", [])[1:]:
            product, partner = (list(row) + ["", ""])[:2]
            if product.strip() and partner.strip():
                partners.setdefault(product.strip().lower(), []).append(partner.strip())

        # One row per setting: key, value, notes
        settings = {}
        for row in settings_tab.get("values", [])[1:]:
            key, value = (list(row) + ["", ""])[:2]
            if key.strip() and value.strip():
                settings[key.strip()] = value.strip()

        # Four columns of haiku lines and an attribution; a kudos message picks
        # one from each. Cells keep their trailing newlines, which break the lines.
        karma = [[], [], [], []]
        for row in karma_tab.get("values", [])[1:]:
            for column, cell in enumerate(row[:4]):
                if cell.strip():
                    karma[column].append(cell)

        quotes = [
            row[0] for row in quotes_tab.get("values", [])[1:] if row and row[0].strip()
        ]
        putdowns = [
            row[0]
            for row in putdowns_tab.get("values", [])[1:]
            if row and row[0].strip()
        ]

        return {
            "users": users,
            "partners": partners,
            "settings": settings,
            "karma": karma,
            "quotes": quotes,
            "putdowns": putdowns,
        }
    except Exception as e:
        print(f"Error fetching data from Google Sheet {sheet_id}: {e}")
        return None


def read_bywaterbot_data_for_update():
    """Read the canonical bywaterbot_data plus a context for writing it back.

    Prefers the Google Sheet ( the live source ), falling back to the local
    data.json. From the sheet only the 'users' tab is read, since that's all
    the self-service commands change.

    Returns ( data, context ) where context is opaque and passed straight to
    write_bywaterbot_data(), or ( None, None ) on failure.
    """
    sheet_id = os.environ.get("BYWATER_BOT_SHEET_ID")

    if sheet_id and os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        try:
            resp = _sheet_session().get(
                f"{SHEETS_API_URL}/{sheet_id}/values/users", timeout=10
            )
            resp.raise_for_status()
            rows = resp.json().get("values", [])
            users, row_numbers = _sheet_users(rows)
            context = {
                "source": "sheet",
                "sheet_id": sheet_id,
                "row_numbers": row_numbers,
                # New names go after the last row that has anything in it
                "next_row": len(rows) + 1,
            }
            return {"users": users}, context
        except Exception as e:
            print(f"Error reading bywaterbot_data from Google Sheet for update: {e}")
            return None, None

    # Local fallback ( dev / when no sheet is configured )
    if os.path.exists("data.json"):
        try:
            with open("data.json") as f:
                data = json.load(f)
            return data, {"source": "local", "path": "data.json"}
        except Exception as e:
            print(f"Error reading local data.json for update: {e}")
            return None, None

    return None, None


def write_bywaterbot_data(data, context, change_description):
    """Persist bywaterbot_data back to its source. Returns True on success.

    For the Google Sheet this writes each user back to the row it was read
    from and appends new names, so rows never move and any extra columns
    people keep next to them stay lined up. The sheet's version history is
    the record of changes, so change_description is only logged.
    """
    if context["source"] == "sheet":
        next_row = context["next_row"]
        updates = []
        for name, info in data["users"].items():
            row_number = context["row_numbers"].get(name)
            if row_number is None:
                row_number = next_row
                next_row += 1
            updates.append(
                {
                    "range": f"users!A{row_number}:C{row_number}",
                    "values": [[name, info.get("sms", ""), info.get("slack_id", "")]],
                }
            )

        try:
            resp = _sheet_session().post(
                f"{SHEETS_API_URL}/{context['sheet_id']}/values:batchUpdate",
                # RAW keeps +1... phone numbers as text instead of parsing them
                json={"valueInputOption": "RAW", "data": updates},
                timeout=10,
            )
            resp.raise_for_status()
            print(f"Wrote bywaterbot_data to Google Sheet: {change_description}")
            return True
        except Exception as e:
            print(f"Error writing bywaterbot_data to Google Sheet: {e}")
            return False

    serialized = json.dumps(data, indent=4) + "\n"
    try:
        with open(context["path"], "w") as f:
            f.write(serialized)
        return True
    except Exception as e:
        print(f"Error writing local data.json: {e}")
        return False


def get_devops_fire_duty_asignee(app, channel_id):
    """Retrieve the on‑call DevOps assignee from a channel topic.

    The channel topic is expected to contain a phrase like ``is NAME`` where
    ``NAME`` is the assignee's name. The function extracts and returns that name.

    Args:
        app: Slack ``App`` instance used to call the Slack API.
        channel_id: The ID of the Slack channel to inspect.

    Returns:
        The extracted name as a string, or ``None`` if not found.
    """
    """
    Get the channel topic and extract name using regex "is NAME"
    """
    try:
        # Get channel info
        channel_info = app.client.conversations_info(channel=channel_id)
        topic = channel_info.get("channel", {}).get("topic", {}).get("value", "")
        print(f"Topic: {topic}")

        # Extract name using regex
        name_match = re.search(r"is\s+(\w+\s*\w*)\n", topic)
        if name_match:
            name = name_match.group(1)
            print(f"Found name in topic: {name}")
            return name
    except Exception as e:
        print(f"Error processing channel topic: {e}")


def get_channel_id_by_name(app, channel_name):
    """Return the Slack channel ID for a given channel name.

    Args:
        app: Slack ``App`` instance.
        channel_name: Human‑readable name of the channel (without the ``#``).

    Returns:
        The channel ID string if found, otherwise ``None``.
    """
    """
    Get channel ID by channel name
    """
    try:
        # Get all channels
        result = app.client.conversations_list()
        channels = result.get("channels", [])

        # Find the channel by name
        for channel in channels:
            if channel.get("name", "") == channel_name:
                return channel.get("id")
        return None
    except Exception as e:
        print(f"Error getting channel ID: {e}")
        return None


def get_name_to_id_mapping(app):
    """Build a mapping from user display names to Slack user IDs.

    The mapping includes ``display_name``, ``name`` and ``real_name`` keys,
    all lower‑cased for case‑insensitive lookup.

    Args:
        app: Slack ``App`` instance.

    Returns:
        Dictionary mapping lower‑cased names to user IDs.
    """
    name_to_id = {}
    name_to_info = {}
    resp = app.client.users_list()
    users = resp["members"]
    for u in users:
        name_to_id[u["profile"]["display_name"].lower()] = u["id"]
        if "name" in u and not u["name"].lower() in name_to_id:
            name_to_id[u["name"].lower()] = u["id"]
        if "real_name" in u and not u["real_name"].lower() in name_to_id:
            name_to_id[u["real_name"].lower()] = u["id"]

        if "real_name" in u and ("is_bot" not in u or not u["is_bot"]):
            name_to_info[u["real_name"]] = u
    return name_to_id, name_to_info


def get_quote(quotes):
    """Return a random quote from the list of quotes.

    The function also normalises certain prefixes for nicer output.

    Args:
        quotes: The quotes from the sheet's 'quotes' tab.

    Returns:
        A single quote string.
    """
    quote = random.choice(quotes)

    if quote.startswith("PQ: "):
        quote = quote.replace("PQ: ", "Partner Quote: ", 1)
    elif quote.startswith("HAHA: "):
        quote = quote.replace("HAHA: ", "", 1)
    elif quote.startswith("MOVE: "):
        quote = quote.replace("MOVE: ", "Get up and move! ", 1)
    elif quote.startswith("FACT: "):
        quote = quote.replace("FACT: ", "Fun Fact! ", 1)
    elif quote.startswith("Koha sys pref: "):
        quote = quote.replace(
            "Koha sys pref: ",
            "Koha SysPref Quiz! Do you know what this setting does?",
            1,
        )

    return quote
