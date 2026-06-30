# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-06-30

First versioned release of ByWaterBot. This starts version tracking; the
features below already existed, and message-handler dispatch was hardened so
commands no longer shadow one another (most visibly, the weekend-duty SMS alert
now actually fires on new tickets).

### Added

- Version tracking and this changelog; DM the bot `version` to see what's
  running.
- Koha and support lookups: `bug`/`bz <id>` (Koha Bugzilla), `ticket`/`zd <id>`
  (Zoho Desk), and `branches <bug> [shortname]`.
- Weekend-duty SMS alerts: the bot texts whoever is on weekend duty when a new
  ticket posts in `#tickets`, with `test weekend duty` and
  `test weekend duty sms` to exercise the path on demand from `#tickets`.
- Self-service contact info over DM: `claim <name>`, `set my sms <number>`, and
  `my info`, written back to the data source so they survive the hourly refresh.
- `TEXT <name> <message>` to relay a Slack message to a teammate as an SMS.
- Karma: `name++`, group `(name1 name2 ...)++`, and `name--`.
- Partner shortname lists: `innreach partners` and `rapido partners`.
- DevOps on-call paging: react :fire: in `#devops` to text the on-call person,
  and a `#devops-alerts` watcher that DMs an Acknowledge button and keeps
  nagging until it is clicked.
- A detailed `help` reference, plus `hello`, `wow`, `Quote Please`, and
  `list slack names`.

### Fixed

- The weekend-duty SMS notifier never fired: Bolt runs only the first
  `@app.message` listener that matches, and every Zoho Flow "New Ticket" post
  contains a `help.bywatersolutions.com` link, so the `help` command matched
  first and shadowed it. The notifier now registers first, and human-command
  handlers use listener matchers so bot posts only reach the handlers meant for
  them.
- The `#devops-alerts` watcher (a catch-all `@app.event("message")`) shadowed
  the partner and contact commands, which never ran; it now registers last.
- `get_weekend_duty()` raised `NameError` on any Calendar API error because
  `HttpError` was caught but never imported.

[Unreleased]: https://github.com/bywatersolutions/slack-bywaterbot/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/bywatersolutions/slack-bywaterbot/releases/tag/v1.0.0
