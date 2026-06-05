"""
DevOps Alerts Handlers Module

Watches the #devops-alerts channel for failure posts ( the danger-colored
messages our GitHub Actions and the custom rebaser send ) and makes sure they
can't be ignored: it opens a DM to the on-call person with an Acknowledge button
and keeps re-sending that DM on a timer until the button is clicked.

Successes posted to #devops-alerts are left alone; only failures start a nag.
"""

import os
import threading
import time

import config
from bot_functions import get_channel_id_by_name, get_name_to_id_mapping

# How long to wait between nags, and the action_id the Acknowledge button fires.
NAG_INTERVAL_SECONDS = int(os.environ.get("DEVOPS_ALERT_NAG_MINUTES", "15")) * 60
ACK_ACTION_ID = "ack_devops_alert"

# Open, unacknowledged incidents keyed by a generated id. Guarded by _lock since
# the message handler, the button handler and the nag thread all touch it.
_incidents = {}
_lock = threading.Lock()
_counter = 0


def _is_failure_alert(event):
    """True if the message looks like one of our failure posts.

    We treat a danger-colored attachment, or any 'fail' text, as a failure. Our
    success posts are plain text without either, so they don't trigger a nag.
    """
    blob = (event.get("text") or "").lower()
    danger = False
    for att in event.get("attachments", []) or []:
        color = (att.get("color") or "").lower()
        # Slack may keep 'danger' or resolve it to its red hex.
        if color in ("danger", "#a30200", "#d50200", "#cc0000"):
            danger = True
        blob += " " + (att.get("title") or "").lower()
        blob += " " + (att.get("text") or "").lower()
        blob += " " + (att.get("fallback") or "").lower()
        for field in att.get("fields", []) or []:
            blob += " " + str(field.get("value") or "").lower()
    return danger or "fail" in blob


def _alert_summary(event):
    """Readable summary of the alert, used in the DM and as a dedupe signature."""
    parts = []
    if event.get("text"):
        parts.append(event["text"])
    for att in event.get("attachments", []) or []:
        if att.get("title"):
            parts.append(att["title"])
        if att.get("text"):
            parts.append(att["text"])
    return "\n".join(parts).strip() or "A DevOps job failed."


def _send_dm(app, incident_id, repeat=False):
    """Send ( or re-send ) the Acknowledge DM for an incident."""
    with _lock:
        inc = _incidents.get(incident_id)
        if not inc or inc["acknowledged"]:
            return
        user_id = inc["user_id"]
        summary = inc["text"]
        permalink = inc.get("permalink")
        count = inc["nag_count"]

    if repeat:
        header = f":rotating_light: Still unacknowledged ( reminder #{count} ) — DevOps failure"
    else:
        header = ":rotating_light: DevOps failure needs your acknowledgement"

    body = summary
    if permalink:
        body += f"\n<{permalink}|View in #devops-alerts>"

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{header}*\n{body}"}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "Acknowledge"},
                    "action_id": ACK_ACTION_ID,
                    "value": incident_id,
                }
            ],
        },
    ]

    try:
        # Posting to a user id delivers to that user's DM with the bot.
        app.client.chat_postMessage(
            channel=user_id, text=f"{header}: {summary}", blocks=blocks
        )
    except Exception as e:
        print(f"Error sending devops-alert DM: {e}")

    with _lock:
        inc = _incidents.get(incident_id)
        if inc:
            inc["nag_count"] += 1
            inc["next_nag"] = time.time() + NAG_INTERVAL_SECONDS


def _nag_loop(app):
    """Background thread: re-send the DM for any incident whose nag is due."""
    while True:
        now = time.time()
        due = []
        with _lock:
            for incident_id, inc in _incidents.items():
                if not inc["acknowledged"] and inc["next_nag"] <= now:
                    due.append(incident_id)
        for incident_id in due:
            _send_dm(app, incident_id, repeat=True)
        time.sleep(30)


def register_devops_alerts_handlers(app):

    try:
        alerts_channel_id = get_channel_id_by_name(
            app=app, channel_name="devops-alerts"
        )
        print(f"DEVOPS-ALERTS CHANNEL ID: {alerts_channel_id}")
    except Exception as e:
        print(f"Error getting devops-alerts channel ID: {e}")
        alerts_channel_id = None

    # Who gets nagged. Defaults to the same person as devops fire duty.
    dm_user_name = os.environ.get(
        "DEVOPS_ALERT_DM_USER", config.DEFAULT_DEVOPS_ASSIGNEE
    )

    # Our own user id, so we never react to messages we posted ourselves.
    try:
        bot_user_id = app.client.auth_test().get("user_id")
    except Exception as e:
        print(f"Error getting bot user id: {e}")
        bot_user_id = None

    def resolve_dm_user_id():
        try:
            name_to_id, _ = get_name_to_id_mapping(app)
            return name_to_id.get(dm_user_name.lower())
        except Exception as e:
            print(f"Error resolving DM user '{dm_user_name}': {e}")
            return None

    @app.event("message")
    def handle_alerts_message(body, logger):
        event = body.get("event", {})

        # Only act on #devops-alerts. If we couldn't resolve that channel at
        # startup, do nothing rather than nag on messages from every channel.
        if not alerts_channel_id or event.get("channel") != alerts_channel_id:
            return

        # Never nag ourselves into a loop.
        if bot_user_id and event.get("user") == bot_user_id:
            return

        # Edits, deletes and join/leave noise aren't alerts.
        if event.get("subtype") in (
            "message_changed",
            "message_deleted",
            "channel_join",
            "channel_leave",
        ):
            return

        if not _is_failure_alert(event):
            return

        summary = _alert_summary(event)
        signature = summary[:120]

        # If we're already nagging about an identical failure, don't start a second
        # one. This collapses the duplicate danger posts a rebase conflict can send.
        with _lock:
            for inc in _incidents.values():
                if not inc["acknowledged"] and inc["signature"] == signature:
                    print("Duplicate devops-alert failure; not starting a second nag.")
                    return

        user_id = resolve_dm_user_id()
        if not user_id:
            print(f"Can't DM '{dm_user_name}' — user id not found.")
            return

        permalink = None
        try:
            ts = event.get("ts")
            if ts:
                permalink = app.client.chat_getPermalink(
                    channel=event.get("channel"), message_ts=ts
                ).get("permalink")
        except Exception as e:
            print(f"Error getting permalink: {e}")

        global _counter
        with _lock:
            _counter += 1
            incident_id = f"alert-{_counter}"
            _incidents[incident_id] = {
                "user_id": user_id,
                "text": summary,
                "permalink": permalink,
                "signature": signature,
                "acknowledged": False,
                "nag_count": 0,
                "next_nag": time.time(),
            }
        print(f"Opened devops-alert incident {incident_id}; nagging {dm_user_name}.")
        _send_dm(app, incident_id)

    @app.action(ACK_ACTION_ID)
    def handle_ack(ack, body, logger):
        ack()

        actions = body.get("actions", [])
        incident_id = actions[0].get("value") if actions else None
        who = body.get("user", {}).get("id")

        with _lock:
            inc = _incidents.get(incident_id)
            if inc:
                inc["acknowledged"] = True

        # Replace the button with a confirmation so the DM reads cleanly.
        try:
            container = body.get("container", {})
            channel = container.get("channel_id")
            message_ts = container.get("message_ts")
            if channel and message_ts:
                app.client.chat_update(
                    channel=channel,
                    ts=message_ts,
                    text="Acknowledged. Thanks!",
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": ":white_check_mark: *Acknowledged.* I'll stop nagging.",
                            },
                        }
                    ],
                )
        except Exception as e:
            print(f"Error updating ack message: {e}")

        print(f"Incident {incident_id} acknowledged by {who}.")

    # Start the re-nag thread once handlers are registered.
    nag_thread = threading.Thread(target=_nag_loop, args=(app,), daemon=True)
    nag_thread.start()
