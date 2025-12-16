"""
Bot Functions Module

Provides utility functions for the ByWater Slack bot, including channel lookup,
user mapping, data retrieval, and message handling.
"""

import csv
import json
import random
import re
import urllib.request
import requests


def get_data_from_url(url, token):
    """Fetch JSON data from a URL.

    Attempts to retrieve data from the given URL and parse it as JSON.
    Useful for loading dynamic configuration from a remote source.

    Args:
        url: The URL to fetch data from.

    Returns:
        The parsed JSON data (dict or list) if successful, otherwise None.
    """
    try:
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.raw",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data from URL {url}: {e}")
        return None


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
    resp = app.client.users_list()
    users = resp["members"]
    for u in users:
        name_to_id[u["profile"]["display_name"].lower()] = u["id"]
        if "name" in u and not u["name"].lower() in name_to_id:
            name_to_id[u["name"].lower()] = u["id"]
        if "real_name" in u and not u["real_name"].lower() in name_to_id:
            name_to_id[u["real_name"].lower()] = u["id"]
    return name_to_id


def get_karma_pep_talks(url):
    """Download and parse the karma pep talks CSV.

    Args:
        url: URL to the CSV file.

    Returns:
        Four lists containing the different talk lines.
    """
    urllib.request.urlretrieve(url, "karma.csv")

    karma1, karma2, karma3, karma4 = [], [], [], []

    with open("karma.csv") as csvfile:
        reader = csv.reader(csvfile, delimiter=",", quotechar='"')

        for row in reader:
            if len(row[0]):
                karma1.append(row[0])
            if len(row[1]):
                karma2.append(row[1])
            if len(row[2]):
                karma3.append(row[2])
            if len(row[3]):
                karma4.append(row[3])

    return karma1, karma2, karma3, karma4


def get_quote(url):
    """Download a CSV of quotes and return a random entry.

    The function also normalises certain prefixes for nicer output.

    Args:
        url: URL to the quotes CSV.

    Returns:
        A single quote string.
    """
    urllib.request.urlretrieve(url, "quotes.csv")

    quotes = []

    with open("quotes.csv") as csvfile:
        reader = csv.reader(csvfile, delimiter=",", quotechar='"')
        for row in reader:
            if len(row[0]):
                quotes.append(row[0])

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


def get_putdowns():
    """Return a static list of humorous put‑downs used by the bot.

    Returns:
        List of strings.
    """
    putdowns = [
        "you’re a gray sprinkle on a rainbow cupcake.",
        "you are more disappointing than an unsalted pretzel.",
        "I’ll never forget the first time we met. But I’ll keep trying.",
        "It’s impossible to underestimate you.",
        "I thought of you today. It reminded me to take out the trash.",
        "you are like a cloud. When you disappear, it’s a beautiful day.",
        "you have miles to go before you reach mediocre.",
        "I was today years old when I realized I didn’t like you.",
        "the jerk store called. They’re running out of you.",
        "life is full of disappointments, and I just added you to the list.",
        "I treasure the time I don’t spend with you.",
    ]
    return putdowns
