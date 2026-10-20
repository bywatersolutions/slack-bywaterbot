"""
DevOps Handlers Module

Contains message handlers for:
- Monitoring #devops for fire emojis
- Alerting users on Fire Duty
- Keeping #devops fires-only ( top-level posts without a fire reaction are removed )
"""

import os
import threading

from slack_sdk import WebClient

import config
from calendar_functions import get_weekday_duty, get_user
from bot_functions import get_devops_fire_duty_asignee, get_channel_id_by_name
from message_matchers import is_not_bot_message

def register_devops_handlers(app):

    # We need to get the channel ID on startup or when needed
    # Since app is passed in, we can get it here, but it might be better to get it lazily
    # For now, let's look it up when registering
    try:
        devops_channel_id = get_channel_id_by_name(
            app=app, channel_name=config.get_setting("DEVOPS_CHANNEL", "devops")
        )
        print(f"DEVOPS CHANNEL ID: {devops_channel_id}")
    except Exception as e:
        print(f"Error getting devops channel ID: {e}")
        devops_channel_id = None

    def alert_user(event, department, channel_id, message_ts, body, logger, permalink=None):
        user = get_user(event)
        print("FOUND USER: ", user)

        # Check if user exists in our data
        if user not in config.bywaterbot_data["users"]:
            print(f"User {user} not found in bywaterbot_data")
            # Optional: post to thread that user wasn't found?
            try:
                app.client.chat_postMessage(
                    channel=channel_id,
                    text=f"I found {user} on the calendar but don't have their contact info!",
                    thread_ts=message_ts,
                )
            except Exception as e:
                print(f"Error posting to Slack: {e}")

            return user

        transports = config.bywaterbot_data["users"][user]
        if "sms" in transports and transports["sms"]:
            sms = transports["sms"]
            try:
                app.client.chat_postMessage(
                    channel=channel_id,
                    text=f"I've alerted {user} via sms!",
                    thread_ts=message_ts,
                )
            except Exception as e:
                print(f"Error posting to Slack: {e}")

            if config.twilio_client:
                # Construct a generic fire message since we don't have ticket details here
                sms_body = f"Fire! Fire! There is a fire in #{department} that needs your attention."
                if permalink:
                    sms_body += f" {permalink}"
                try:
                    message = config.twilio_client.messages.create(
                        body=sms_body, from_=config.twilio_phone, to=sms
                    )
                    print(message.sid)
                except Exception as e:
                    print(f"Error sending SMS: {e}")

        if len(transports) == 0:
            try:
                app.client.chat_postMessage(
                    channel=channel_id,
                    text=f"{user} has not opted to receive alerts from me!",
                    thread_ts=message_ts,
                )
            except Exception as e:
                print(f"Error posting to Slack: {e}")

    def handle_devops_fires(body, logger):
        """Monitor #devops channel for fire emoji events."""
        event = body.get("event")

        # For reactions, get the channel ID from the item field
        if event.get("type") == "reaction_added":
            channel_id = event.get("item").get("channel")
        else:
            channel_id = event.get("channel")

        print("CHANNEL ID: ", channel_id)

        # Only process events in #devops channel
        if devops_channel_id and channel_id != devops_channel_id:
            return

        assignee = ""
        text = ""

        # Check if this is a reaction event
        if event.get("type") == "reaction_added":
            reaction = event.get("reaction")
            print("REACTION: ", reaction)
            if reaction == "fire":
                message_ts = event.get("item", {}).get("ts")

                permalink = None
                if message_ts:
                    try:
                        permalink_response = app.client.chat_getPermalink(
                            channel=channel_id, message_ts=message_ts
                        )
                        permalink = permalink_response.get("permalink")
                        print(f"Permalink: {permalink}")
                    except Exception as e:
                        print(f"Error getting permalink: {e}")

                # Get the message text from the reaction
                try:
                    if message_ts:
                        response = app.client.conversations_history(
                            channel=channel_id,
                            inclusive=True,
                            latest=message_ts,
                            limit=1,
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

                    if assignee not in config.bywaterbot_data["users"]:
                        body_text = (
                            f"There is a fire in #devops assigned to {assignee}: {text}"
                        )
                        assignee = config.get_setting(
                            "DEFAULT_DEVOPS_ASSIGNEE", config.DEFAULT_DEVOPS_ASSIGNEE
                        )
                    else:  # User cannot be contacted
                        body_text = f"There is a fire in #devops: {text}"

                    if permalink:
                        body_text += f" {permalink}"

                    if assignee in config.bywaterbot_data["users"]:
                        transports = config.bywaterbot_data["users"][assignee]
                        print(f"TRANSPORTS: {transports}")
                        if transports.get("sms"):
                            sms = transports["sms"]
                            print(f"BODY: {body_text}")
                            try:
                                if config.twilio_client:
                                    message = config.twilio_client.messages.create(
                                        body=body_text,
                                        from_=config.twilio_phone,
                                        to=sms,
                                    )
                                    print(
                                        f"TWILIO SMS SENT TO {assignee}: {message.sid}"
                                    )
                            except Exception as e:
                                print(f"Error sending SMS: {e}")

                event_dev = get_weekday_duty("dev")

                dev_user = None
                if event_dev:
                    dev_user = get_user(event_dev)
                    alert_user(
                        event_dev, "dev", channel_id, message_ts, body, logger,
                        permalink=permalink,
                    )

                event_sys = get_weekday_duty("systems")
                if event_sys:
                    sys_user = get_user(event_sys)
                    if dev_user != sys_user:
                        alert_user(
                            event_sys, "systems", channel_id, message_ts, body, logger,
                            permalink=permalink,
                        )

    @app.event("reaction_added")
    def handle_reaction_events(body, logger):
        """Entry point for reaction events."""
        handle_devops_fires(body, logger)

    def in_devops_top_level(message):
        """Listener matcher: only match new top-level posts in #devops.

        Thread replies ( including "also send to channel" ones ), edits and
        join/leave messages don't match, so they fall through to the other
        handlers. If we couldn't resolve #devops at startup, match nothing
        rather than enforce on every channel.
        """
        if devops_channel_id is None or message.get("channel") != devops_channel_id:
            return False
        if message.get("subtype") not in (None, "file_share"):
            return False
        thread_ts = message.get("thread_ts")
        return thread_ts is None or thread_ts == message.get("ts")

    def remove_if_not_fire(channel_id, message_ts, user, text, warning_ts):
        """Delete a #devops post that never got a fire reaction and DM its author."""
        try:
            response = app.client.reactions_get(channel=channel_id, timestamp=message_ts)
        except Exception as e:
            # Most likely the author already deleted it
            print(f"Error getting reactions for #devops message {message_ts}: {e}")
            response = None

        # Our warning is stale either way, and while it's in the thread, deleting the post
        # leaves a "This message was deleted" stub in the channel, so remove it first
        if warning_ts:
            try:
                app.client.chat_delete(channel=channel_id, ts=warning_ts)
            except Exception as e:
                print(f"Error deleting #devops fires-only warning {warning_ts}: {e}")

        if response is None:
            return

        reactions = response.get("message", {}).get("reactions", [])
        if any(reaction.get("name") == "fire" for reaction in reactions):
            return

        # Bot tokens can only delete the bot's own messages, so this needs an admin's user token
        admin_user_token = os.environ.get("SLACK_ADMIN_USER_TOKEN")
        if not admin_user_token:
            print(f"SLACK_ADMIN_USER_TOKEN is not set; can't remove #devops message {message_ts}")
            return

        try:
            WebClient(token=admin_user_token).chat_delete(channel=channel_id, ts=message_ts)
        except Exception as e:
            print(f"Error deleting #devops message {message_ts}: {e}")
            return

        dm_text = (
            f":fire: <#{channel_id}> is now for fires only, so I removed your message there. "
            "Only posts with a :fire: reaction stay in the channel, and all discussion should "
            "happen as replies in the thread of a fire post. "
            "If this was a fire, repost it and react to it with :fire:."
        )
        if text:
            quoted_text = "\n".join(f"> {line}" for line in text.splitlines())
            dm_text += f"\n\nHere's what you wrote:\n{quoted_text}"

        try:
            # Posting to a user id delivers to that user's DM with the bot.
            app.client.chat_postMessage(channel=user, text=dm_text)
        except Exception as e:
            print(f"Error sending #devops removal DM: {e}")

    @app.event("message", matchers=[is_not_bot_message, in_devops_top_level])
    def enforce_fires_only(message):
        """Warn the author of a new #devops post, then remove it unless it gets a fire."""
        channel_id = message.get("channel")
        message_ts = message.get("ts")
        user = message.get("user")
        text = message.get("text", "")

        # How long a new top-level #devops post has to get a fire reaction before it's removed
        fire_grace_minutes = int(config.get_setting("DEVOPS_FIRE_GRACE_MINUTES", "1"))

        warning_ts = None
        try:
            response = app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=message_ts,
                text=(
                    f":fire: <#{channel_id}> is for fires only. React to your message "
                    f"with :fire: within {fire_grace_minutes} "
                    f"minute{'' if fire_grace_minutes == 1 else 's'} or I'll remove it. "
                    "Discussion belongs in the thread of a fire post."
                ),
            )
            warning_ts = response.get("ts")
        except Exception as e:
            print(f"Error sending #devops fires-only warning: {e}")

        timer = threading.Timer(
            fire_grace_minutes * 60,
            remove_if_not_fire,
            args=(channel_id, message_ts, user, text, warning_ts),
        )
        timer.daemon = True
        timer.start()
