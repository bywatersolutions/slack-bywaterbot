"""
Partner Handlers Module

Commands:
- innreach partners: List INN-Reach partner libraries
- rapido partners: List Rapido partner libraries
"""

import re

from message_matchers import is_not_bot_message

# TODO: Replace hardcoded lists with Zoho CRM API once access is granted
PARTNERS = {
    "innreach": [
        "amadorlibrary",
        "bhpl",
        "cdoc",
        "clic",
        "cocollege",
        "eldoradolibrary",
        "northville",
    ],
    "rapido": [
        "akronlibrary",
        "cuyahoga",
        "mrcpl",
        "westlake",
    ],
}


def register_partner_handlers(app):

    @app.message(
        re.compile(r"(innreach|rapido)\s+partners", re.IGNORECASE),
        matchers=[is_not_bot_message],
    )
    def handle_partners(say, context):
        """List partners for INN-Reach or Rapido."""
        product = context["matches"][0].lower()
        partners = PARTNERS[product]
        label = "INN-Reach" if product == "innreach" else "Rapido"

        lines = [f"*{label} Partners ({len(partners)}):*"]
        for p in sorted(partners):
            lines.append(f"* {p}")

        say(text="\n".join(lines))
