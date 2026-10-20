"""
Partner Handlers Module

Commands:
- innreach partners: List INN-Reach partner libraries
- rapido partners: List Rapido partner libraries
"""

import re

import config
from message_matchers import is_not_bot_message


def register_partner_handlers(app):

    @app.message(
        re.compile(r"(innreach|rapido)\s+partners", re.IGNORECASE),
        matchers=[is_not_bot_message],
    )
    def handle_partners(say, context):
        """List partners for INN-Reach or Rapido."""
        product = context["matches"][0].lower()
        # TODO: Replace the sheet's 'partners' tab with Zoho CRM API once access is granted
        partners = config.bywaterbot_data.get("partners", {}).get(product, [])
        label = "INN-Reach" if product == "innreach" else "Rapido"

        lines = [f"*{label} Partners ({len(partners)}):*"]
        for p in sorted(partners):
            lines.append(f"* {p}")

        say(text="\n".join(lines))
