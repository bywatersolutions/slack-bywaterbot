# slack-bywaterbot  

ByWaterBot is a Slack bot written in Python using Bolt for Slack

## Description

An in-depth paragraph about your project and overview of use.
This bot was written specifically to fill the needs of ByWater Solutions staff.
It is a replacement for the older slack-bwsbot project

## Getting Started

### Commands and features

DM the bot `help` (any casing) and it replies with this same reference. Unless
noted, commands work in any channel the bot is in or in a direct message.

#### Koha & support lookups

* `bug <id>` / `bz <id>` — Look up a Koha community bug; replies with its summary, status, and a link. _e.g._ `bug 38120`
* `ticket <id>` / `zd <id>` — Look up a Zoho Desk support ticket by its ZD number; replies with its status, assignee, partner, and a link. _e.g._ `ticket 215390`
* `branches <bug_id> [shortname]` — List which Koha branches contain a bug. Shortname defaults to `bywater`. _e.g._ `branches 38120 bywater`

#### Partners

* `innreach partners` — List the INN-Reach partner shortnames.
* `rapido partners` — List the Rapido partner shortnames.

#### Texting teammates (SMS via Twilio)

* `TEXT <name> <message>` — Send a teammate an SMS. Use their name as it appears in the contact list. _e.g._ `TEXT Kyle running 5 min late`
* `test weekend duty` — _(#tickets only)_ Dry run: reports who's on weekend duty and whether a number is on file. No text is sent.
* `test weekend duty sms` — _(#tickets only)_ Send a real test SMS to the current on-duty person.

#### Karma & kudos

* `name++` / `@name++` — Give someone kudos; posts an encouragement to `#kudos`. _e.g._ `@kyle++`
* `(name1 name2 ...)++` — Give a whole group kudos at once.
* `name--` — Take a shot at someone; the bot gently pushes back.

#### Fun & utility

* `hello` — The bot says hi.
* `wow` — Owen Wilson says "wow".
* `Quote Please` — Posts a random quote to `#general`.
* `list slack names` — List the names and Slack IDs the bot knows.
* `version` — Replies with the bot's current version. _(DM only)_

#### Your contact info (DM only)

Self-service editing of your own entry in `data.json`. You can only edit your
own info — the bot matches you by your stored Slack id — and changes are
committed back to the private data repo, so they survive the hourly refresh.

* `claim <name>` — Link your Slack account to your weekend/fire-duty calendar name so the bot can find you. _e.g._ `claim Laura O`
* `set my sms <number>` — Set the mobile number the bot texts for your duty alerts. _e.g._ `set my sms +12025550123`
* `my info` — Show the name and ( masked ) number on file for you.

#### Admin (DM only)

* `Refresh Data` — Reload contact/duty data from its source.
* `Refresh Karma` — Reload the karma pep-talk messages.
* `help` — Show this capability reference (any casing).

#### Automatic behaviors (no command needed)

* **New weekend tickets** — when a new ticket posts in `#tickets`, the bot texts whoever's on weekend duty.
* **DevOps fires** — react :fire: to a message in `#devops` and the bot texts the on-call dev/systems person.
* **#devops-alerts** — see [DevOps alert acknowledgements](#devops-alert-acknowledgements) below.

### DevOps alert acknowledgements

The bot watches `#devops-alerts` for failure posts ( the danger-colored messages
our GitHub Actions and the custom rebaser send ). When it sees one, it DMs the
on-call person an Acknowledge button and keeps re-sending that DM every
`DEVOPS_ALERT_NAG_MINUTES` minutes until the button is clicked. Successes posted
to the channel are ignored. The bot must be invited to `#devops-alerts`.

### Dependencies

* Python 3 and dependencies

### Installing

```bash
pip install --no-cache-dir -r requirements.txt
```

### Environment variables

This project uses a number of environment variables to function:

* SLACK_BOT_TOKEN - Slack bot token
* SLACK_APP_TOKEN - Slack app token
* BYWATER_BOT_DATA_URL - GitHub URL of the private `data.json` ( contact/duty map + secrets ) the bot loads and refreshes hourly
* BYWATER_BOT_GITHUB_TOKEN - Token used to read `data.json`. Needs **contents: write** on that repo for the self-service `claim` / `set my sms` commands to commit updates back
* QUOTES_CSV_URL - URL to a CSV of quotes
* KARMA_CSV_URL - URL to a CSV of karma comment possibilities
* CREDENTIALS_JSON - Download crendentials.json from Google, put contents in this variable
* TOKEN_JSON - Run `python calendar_functions.py` on the server, input given URL in lynx, copy contents of token.json into this variable
* TWILIO_ACCOUNT_SID - SID for the Twilio account to be used ( provided by Twilio )
* TWILIO_AUTH_TOKEN - Authentication token for the Twilio account ot be used ( provided by Twilio )
* TWILIO_PHONE - Outgoing Twilio phone number ( e.g. +11234567890 )
* DEVOPS_ALERT_DM_USER - Who to nag about #devops-alerts failures ( defaults to the devops fire-duty default, "Kyle" )
* DEVOPS_ALERT_NAG_MINUTES - Minutes between un-acknowledged DM reminders ( defaults to 15 )

The `ticket`/`zd` lookup talks to the Zoho Desk REST API using an OAuth2
refresh token ( server-to-server ). Create a Self Client in the
[Zoho API Console](https://api-console.zoho.com/), generate a grant code with
the scope `Desk.tickets.READ,Desk.search.READ` ( both are required — the search
endpoint used for ZD-number lookups needs `Desk.search.READ` ), then exchange it
for a refresh token once and set the variables below.

The exchange is scripted — run `python zoho_functions.py` and paste the grant
code when prompted; it prints the `ZOHO_REFRESH_TOKEN` to set.

* ZOHO_DESK_ORG_ID - Zoho Desk organization id ( ByWater is `868351381`; from `GET /api/v1/organizations` )
* ZOHO_CLIENT_ID - OAuth client id from the Self Client
* ZOHO_CLIENT_SECRET - OAuth client secret from the Self Client
* ZOHO_REFRESH_TOKEN - Long-lived refresh token from the one-time code exchange
* ZOHO_ACCOUNTS_URL - Accounts base URL ( optional, defaults to `https://accounts.zoho.com`; change for non-US data centers )
* ZOHO_DESK_URL - Desk API base URL ( optional, defaults to `https://desk.zoho.com` )

Check out https://slack.dev/bolt-python/tutorial/getting-started to see
how to set up the Slack tokens.

### Slack Bot settings

#### Event Subscriptions

* message.channels
* message.groups
* message.im
* message.mpim

#### Permissions

##### Bot Token Scopes

* channels:history
* chat:write
* im:write
* groups:history
* im:history
* mpim:history
* users:read

##### Google Scopes
* calendar, read-only

### Executing program

```bash
python3 bywaterbot.py
```

## Versioning

This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The running version lives in `version.py` (`__version__`); bump it on release and
add a matching entry to [CHANGELOG.md](CHANGELOG.md), which is kept in the
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/) format. DM the bot
`version` to see what's running, and tag releases `vX.Y.Z` to match.

## Authors

Contributors names and contact info

[@kylemhall](https://github.com/kylemhall)

## License

This project is licensed under the GPL v3 License - see the LICENSE.md file for details

## Acknowledgments

Inspiration, code snippets, etc.
* [awesome-readme](https://github.com/matiassingers/awesome-readme)
