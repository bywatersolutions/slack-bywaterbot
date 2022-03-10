# slack-bywaterbot  

ByWaterBot is a Slack bot written in Python using Bolt for Slack

## Description

An in-depth paragraph about your project and overview of use.
This bot was written specifically to fill the needs of ByWater Solutions staff.
It is a replacement for the older slack-bwsbot project

## Getting Started

### Keywords and phrases

This bot has a number of words and phrases it listens for

* "hello" - Bot will say hi to you!
* "bug 1234", "bz 1234" - Bot will provide a link and info to the Koha Bugzilla for that number
* "ticket 1234", "rt 1234" - Bot will provide a link to the given ticket number
* "branches 1234", "branches 1234 _shortname_" - Bot will tell you bug branches are on the bug for the given shortname ( defaults to "bywater" )
* "Quote Please" - Bot will give you a quote from our quotes file
* "Refresh Karma" - Bot will download the latest version of the pep talk data

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
* QUOTES_CSV_URL - URL to a CSV of quotes
* KARMA_CSV_URL - URL to a CSV of karma comment possibilities

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
* groups:history
* im:history
* mpim:history
* users:read

### Executing program

```bash
python3 bywaterbot.py
```

## Authors

Contributors names and contact info

[@kylemhall](https://github.com/kylemhall)

## License

This project is licensed under the GPL v3 License - see the LICENSE.md file for details

## Acknowledgments

Inspiration, code snippets, etc.
* [awesome-readme](https://github.com/matiassingers/awesome-readme)
