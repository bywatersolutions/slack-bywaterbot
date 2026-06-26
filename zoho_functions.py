"""
Zoho Desk Functions Module

Looks up support tickets in Zoho Desk ( help.bywatersolutions.com ) via the REST
API. Authenticates with an OAuth2 refresh token ( server-to-server ), caching the
short-lived access token between calls so we don't mint a new one every lookup.
"""

import os
import time
import requests

# Cache the access token so we don't request a new one on every lookup
_access_token = None
_access_token_expiry = 0


def _zoho_config():
    """Return the Zoho OAuth/Desk settings from the environment.

    Returns a dict, or None if the required credentials aren't all present.
    """
    client_id = os.environ.get("ZOHO_CLIENT_ID")
    client_secret = os.environ.get("ZOHO_CLIENT_SECRET")
    refresh_token = os.environ.get("ZOHO_REFRESH_TOKEN")
    org_id = os.environ.get("ZOHO_DESK_ORG_ID")
    if not (client_id and client_secret and refresh_token and org_id):
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "org_id": org_id,
        # Default to the US data center; override for EU/IN/AU/etc.
        "accounts_url": os.environ.get(
            "ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com"
        ),
        "desk_url": os.environ.get("ZOHO_DESK_URL", "https://desk.zoho.com"),
    }


def zoho_configured():
    """Return True if all the Zoho Desk credentials are set in the environment."""
    return _zoho_config() is not None


def get_zoho_access_token():
    """Return a valid Zoho Desk access token, refreshing it when needed.

    Uses the OAuth2 refresh-token grant. Returns None if Zoho isn't configured
    or the token request fails.
    """
    global _access_token, _access_token_expiry

    # Reuse the cached token until ~1 minute before it expires
    if _access_token and time.time() < _access_token_expiry - 60:
        return _access_token

    config = _zoho_config()
    if not config:
        print("Zoho Desk is not configured (missing env vars)")
        return None

    try:
        resp = requests.post(
            f"{config['accounts_url']}/oauth/v2/token",
            params={
                "refresh_token": config["refresh_token"],
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            print(f"Zoho token response had no access_token: {data}")
            return None

        _access_token = token
        _access_token_expiry = time.time() + data.get("expires_in", 3600)
        return _access_token
    except Exception as e:
        print(f"Error getting Zoho access token: {e}")
        return None


def get_zoho_ticket(ticket_number):
    """Fetch a single ticket from Zoho Desk by its ZD number.

    Args:
        ticket_number: The ticket's serial number, e.g. "215390".

    Returns:
        The ticket dict if found, otherwise None ( not found or on error ).
    """
    config = _zoho_config()
    token = get_zoho_access_token()
    if not config or not token:
        return None

    try:
        resp = requests.get(
            f"{config['desk_url']}/api/v1/tickets/search",
            headers={
                "Authorization": f"Zoho-oauthtoken {token}",
                "orgId": config["org_id"],
            },
            params={"ticketNumber": ticket_number, "limit": 1},
            timeout=10,
        )
        # The search endpoint returns 204 No Content when nothing matches
        if resp.status_code == 204:
            return None
        resp.raise_for_status()
        results = resp.json().get("data", [])
        return results[0] if results else None
    except Exception as e:
        print(f"Error fetching Zoho ticket {ticket_number}: {e}")
        return None


def bootstrap_refresh_token():
    """Interactively exchange a Self Client grant code for a refresh token.

    Reads ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET from the environment when set,
    otherwise prompts for them, asks for a grant code generated in the Zoho API
    Console ( https://api-console.zoho.com/ , Self Client > Generate Code, scope
    'Desk.tickets.READ,Desk.search.READ' ), and prints the resulting refresh
    token to drop into ZOHO_REFRESH_TOKEN. Run it with: python zoho_functions.py
    """
    accounts_url = os.environ.get("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com")
    client_id = os.environ.get("ZOHO_CLIENT_ID") or input("Zoho Client ID: ").strip()
    client_secret = (
        os.environ.get("ZOHO_CLIENT_SECRET") or input("Zoho Client Secret: ").strip()
    )

    print(
        "\nGenerate a grant code at https://api-console.zoho.com/ "
        "( Self Client > Generate Code ) with scope "
        "'Desk.tickets.READ,Desk.search.READ'.\n"
        "It expires within minutes, so paste it as soon as you create it.\n"
    )
    code = input("Grant code: ").strip()

    try:
        resp = requests.post(
            f"{accounts_url}/oauth/v2/token",
            params={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
            timeout=10,
        )
        data = resp.json()
    except Exception as e:
        print(f"\nToken request failed: {e}")
        return

    refresh_token = data.get("refresh_token")
    if not refresh_token:
        print(f"\nNo refresh_token in response: {data}")
        print(
            "( A refresh token is only returned on the first exchange of a grant "
            "code. Generate a fresh code and try again. )"
        )
        return

    print("\nSuccess! Set these in the bot's environment:\n")
    print(f"ZOHO_CLIENT_ID={client_id}")
    print(f"ZOHO_CLIENT_SECRET={client_secret}")
    print(f"ZOHO_REFRESH_TOKEN={refresh_token}")
    print("ZOHO_DESK_ORG_ID=<your org id, e.g. 868351381>")
    print(f"\n( scope granted: {data.get('scope')} )")


if __name__ == "__main__":
    bootstrap_refresh_token()
