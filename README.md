# slack-bywaterbot  

ByWaterBot is a Slack bot written in Python using Bolt for Slack

## Description

An in-depth paragraph about your project and overview of use.
This bot was written specifically to fill the needs of ByWater Solutions staff.
It is a replacement for the older slack-bwsbot project

## Getting Started

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

ex. Dominique Pizzie  
ex. [@DomPizzie](https://twitter.com/dompizzie)

## License

This project is licensed under the GPL v3 License - see the LICENSE.md file for details

## Acknowledgments

Inspiration, code snippets, etc.
* [awesome-readme](https://github.com/matiassingers/awesome-readme)
* [PurpleBooth](https://gist.github.com/PurpleBooth/109311bb0361f32d87a2)
* [dbader](https://github.com/dbader/readme-template)
* [zenorocha](https://gist.github.com/zenorocha/4526327)
* [fvcproductions](https://gist.github.com/fvcproductions/1bfc2d4aecb01a834b46)
