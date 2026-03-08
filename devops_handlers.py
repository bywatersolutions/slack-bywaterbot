"""
DevOps Handlers Module

Contains message handlers for:
- Monitoring #devops for fire emojis
- Alerting users on Fire Duty
"""

import config
from calendar_functions import get_weekday_duty, get_user
from bot_functions import get_devops_fire_duty_asignee, get_channel_id_by_name


def register_devops_handlers(app):

    # We need to get the channel ID on startup or when needed
    # Since app is passed in, we can get it here, but it might be better to get it lazily
    # For now, let's look it up when registering
    try:
        devops_channel_id = get_channel_id_by_name(app=app, channel_name="devops")
        print(f"DEVOPS CHANNEL ID: {devops_channel_id}")
    except Exception as e:
        print(f"Error getting devops channel ID: {e}")
        devops_channel_id = None

    def alert_user(event, department, channel_id, message_ts, body, logger):
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
                # Get the message text from the reaction
                try:
                    message_ts = event.get("item", {}).get("ts")
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
                        assignee = config.DEFAULT_DEVOPS_ASSIGNEE
                    else:  # User cannot be contacted
                        body_text = f"There is a fire in #devops: {text}"

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

                message_ts = event.get("item", {}).get("ts")

                event_dev = get_weekday_duty("dev")

                dev_user = None
                if event_dev:
                    dev_user = get_user(event_dev)
                    alert_user(event_dev, "dev", channel_id, message_ts, body, logger)

                event_sys = get_weekday_duty("systems")
                if event_sys:
                    sys_user = get_user(event_sys)
                    if dev_user != sys_user:
                        alert_user(
                            event_sys, "systems", channel_id, message_ts, body, logger
                        )

                app.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Please tag this ticket with devops_fire.",
                    thread_ts=message_ts,
                )

    @app.event("reaction_added")
    def handle_reaction_events(body, logger):
        """Entry point for reaction events."""
        handle_devops_fires(body, logger)
