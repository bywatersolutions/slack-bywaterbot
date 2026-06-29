"""
Listener matchers shared across the handler modules.

Bolt runs only the FIRST @app.message listener that matches an incoming
message, so a handler that only conditionally acts ( DM-only, or one that
should skip messages posted by other bots ) has to express that as a listener
matcher, not an early return in its body. An early return still counts the
message as handled, which shadows every handler registered after it. These
matchers let such handlers decline to match instead, so the message falls
through to the handler that should actually run.

Convention: every human-command @app.message handler uses is_not_bot_message
( or is_direct_message for DM-only commands ) so bot posts can only ever reach
the handlers meant for them ( the #tickets new-ticket notifier, registered
first, and the #devops-alerts watcher, registered last ).
"""


def is_direct_message(message):
    """Match only messages sent in a DM with the bot."""
    return message.get("channel_type") == "im"


def is_not_bot_message(message):
    """Skip messages posted by bots/integrations ( e.g. Zoho Flow, GitHub )."""
    return not (message.get("bot_id") or message.get("subtype") == "bot_message")
