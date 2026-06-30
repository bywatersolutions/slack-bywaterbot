"""Unit tests for the ByWater Slack Bot."""

import json
import os
import re
from unittest.mock import MagicMock, patch, mock_open

import pytest

# ---------------------------------------------------------------------------
# bot_functions tests
# ---------------------------------------------------------------------------

from bot_functions import (
    get_putdowns,
    get_quote,
    get_data_from_url,
    get_devops_fire_duty_asignee,
    get_channel_id_by_name,
    get_name_to_id_mapping,
    get_karma_pep_talks,
    load_bywaterbot_data,
)


class TestGetPutdowns:
    def test_returns_list(self):
        result = get_putdowns()
        assert isinstance(result, list)

    def test_non_empty(self):
        assert len(get_putdowns()) > 0

    def test_all_strings(self):
        for p in get_putdowns():
            assert isinstance(p, str)


class TestGetQuote:
    @patch("bot_functions.urllib.request.urlretrieve")
    def test_prefix_replacement_pq(self, mock_retrieve):
        csv_content = "PQ: Some partner quote\n"
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch(
                "bot_functions.random.choice", return_value="PQ: Some partner quote"
            ):
                result = get_quote("http://example.com/quotes.csv")
        assert result.startswith("Partner Quote: ")
        assert "PQ: " not in result

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_prefix_replacement_haha(self, mock_retrieve):
        csv_content = "HAHA: Funny thing\n"
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch("bot_functions.random.choice", return_value="HAHA: Funny thing"):
                result = get_quote("http://example.com/quotes.csv")
        assert result == "Funny thing"

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_prefix_replacement_move(self, mock_retrieve):
        csv_content = "MOVE: Take a walk\n"
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch("bot_functions.random.choice", return_value="MOVE: Take a walk"):
                result = get_quote("http://example.com/quotes.csv")
        assert result == "Get up and move! Take a walk"

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_prefix_replacement_fact(self, mock_retrieve):
        csv_content = "FACT: The sky is blue\n"
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch(
                "bot_functions.random.choice", return_value="FACT: The sky is blue"
            ):
                result = get_quote("http://example.com/quotes.csv")
        assert result == "Fun Fact! The sky is blue"

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_prefix_replacement_koha(self, mock_retrieve):
        csv_content = "Koha sys pref: SomePref\n"
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch(
                "bot_functions.random.choice", return_value="Koha sys pref: SomePref"
            ):
                result = get_quote("http://example.com/quotes.csv")
        assert "Koha SysPref Quiz!" in result

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_no_prefix(self, mock_retrieve):
        csv_content = "Just a normal quote\n"
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch(
                "bot_functions.random.choice", return_value="Just a normal quote"
            ):
                result = get_quote("http://example.com/quotes.csv")
        assert result == "Just a normal quote"


class TestGetDataFromUrl:
    @patch("bot_functions.requests.get")
    def test_fetches_json(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "value"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = get_data_from_url("https://example.com/data.json", "token123")
        assert result == {"key": "value"}
        mock_get.assert_called_once()

    @patch("bot_functions.requests.get")
    def test_github_blob_url_converted(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": True}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        get_data_from_url(
            "https://github.com/owner/repo/blob/main/path/to/file.json",
            "token123",
        )
        called_url = mock_get.call_args[0][0]
        assert "api.github.com" in called_url
        assert "contents/path/to/file.json" in called_url
        assert "ref=main" in called_url

    @patch("bot_functions.requests.get")
    def test_returns_none_on_error(self, mock_get):
        mock_get.side_effect = Exception("Network error")
        result = get_data_from_url("https://example.com/data.json", "token123")
        assert result is None


class TestGetDevopsFireDutyAssignee:
    def test_extracts_name_from_topic(self):
        app = MagicMock()
        app.client.conversations_info.return_value = {
            "channel": {"topic": {"value": "Fire duty is Kyle Hall\nSome other info"}}
        }
        result = get_devops_fire_duty_asignee(app, "C123")
        assert result == "Kyle Hall"

    def test_extracts_single_name(self):
        app = MagicMock()
        app.client.conversations_info.return_value = {
            "channel": {"topic": {"value": "Current duty is Kyle\nMore info"}}
        }
        result = get_devops_fire_duty_asignee(app, "C123")
        assert result == "Kyle"

    def test_returns_none_when_no_match(self):
        app = MagicMock()
        app.client.conversations_info.return_value = {
            "channel": {"topic": {"value": "No name here"}}
        }
        result = get_devops_fire_duty_asignee(app, "C123")
        assert result is None

    def test_returns_none_on_api_error(self):
        app = MagicMock()
        app.client.conversations_info.side_effect = Exception("API error")
        result = get_devops_fire_duty_asignee(app, "C123")
        assert result is None


class TestGetChannelIdByName:
    def test_finds_channel(self):
        app = MagicMock()
        app.client.conversations_list.return_value = {
            "channels": [
                {"name": "general", "id": "C001"},
                {"name": "devops", "id": "C002"},
            ]
        }
        assert get_channel_id_by_name(app, "devops") == "C002"

    def test_returns_none_when_not_found(self):
        app = MagicMock()
        app.client.conversations_list.return_value = {
            "channels": [{"name": "general", "id": "C001"}]
        }
        assert get_channel_id_by_name(app, "nonexistent") is None

    def test_returns_none_on_error(self):
        app = MagicMock()
        app.client.conversations_list.side_effect = Exception("API error")
        assert get_channel_id_by_name(app, "devops") is None


class TestGetNameToIdMapping:
    def test_maps_display_name(self):
        app = MagicMock()
        app.client.users_list.return_value = {
            "members": [
                {
                    "id": "U001",
                    "name": "kyleh",
                    "real_name": "Kyle Hall",
                    "profile": {"display_name": "Kyle"},
                }
            ]
        }
        name_to_id, name_to_info = get_name_to_id_mapping(app)
        assert name_to_id["kyle"] == "U001"
        assert name_to_id["kyleh"] == "U001"
        assert name_to_id["kyle hall"] == "U001"

    def test_case_insensitive(self):
        app = MagicMock()
        app.client.users_list.return_value = {
            "members": [
                {
                    "id": "U001",
                    "name": "JohnDoe",
                    "real_name": "John Doe",
                    "profile": {"display_name": "John"},
                }
            ]
        }
        name_to_id, _ = get_name_to_id_mapping(app)
        assert "john" in name_to_id
        assert "johndoe" in name_to_id

    def test_excludes_bots_from_info(self):
        app = MagicMock()
        app.client.users_list.return_value = {
            "members": [
                {
                    "id": "U001",
                    "name": "mybot",
                    "real_name": "My Bot",
                    "is_bot": True,
                    "profile": {"display_name": "bot"},
                },
                {
                    "id": "U002",
                    "name": "kyleh",
                    "real_name": "Kyle",
                    "is_bot": False,
                    "profile": {"display_name": "Kyle"},
                },
            ]
        }
        _, name_to_info = get_name_to_id_mapping(app)
        assert "My Bot" not in name_to_info
        assert "Kyle" in name_to_info


class TestGetKarmaPepTalks:
    @patch("bot_functions.urllib.request.urlretrieve")
    def test_parses_csv(self, mock_retrieve):
        csv_content = '"a1","b1","c1","d1"\n"a2","b2","c2","d2"\n'
        with patch("builtins.open", mock_open(read_data=csv_content)):
            k1, k2, k3, k4 = get_karma_pep_talks("http://example.com/karma.csv")
        assert k1 == ["a1", "a2"]
        assert k2 == ["b1", "b2"]
        assert k3 == ["c1", "c2"]
        assert k4 == ["d1", "d2"]

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_skips_empty_cells(self, mock_retrieve):
        csv_content = '"a1","","c1",""\n"","b2","","d2"\n'
        with patch("builtins.open", mock_open(read_data=csv_content)):
            k1, k2, k3, k4 = get_karma_pep_talks("http://example.com/karma.csv")
        assert k1 == ["a1"]
        assert k2 == ["b2"]
        assert k3 == ["c1"]
        assert k4 == ["d2"]


class TestLoadBywaterbotData:
    @patch.dict(os.environ, {}, clear=True)
    @patch("bot_functions.os.path.exists", return_value=False)
    def test_raises_when_no_source(self, mock_exists):
        with pytest.raises(Exception, match="Failed to load"):
            load_bywaterbot_data()

    @patch.dict(
        os.environ,
        {"BYWATER_BOT_DATA": '{"key": "value"}'},
        clear=True,
    )
    @patch("bot_functions.os.path.exists", return_value=False)
    def test_loads_from_env_var(self, mock_exists):
        result = load_bywaterbot_data()
        assert result == {"key": "value"}

    @patch.dict(os.environ, {}, clear=True)
    @patch("bot_functions.os.path.exists", return_value=True)
    def test_loads_from_local_file(self, mock_exists):
        file_data = '{"from": "file"}'
        with patch("builtins.open", mock_open(read_data=file_data)):
            result = load_bywaterbot_data()
        assert result == {"from": "file"}


# ---------------------------------------------------------------------------
# calendar_functions tests
# ---------------------------------------------------------------------------

from calendar_functions import get_user


class TestGetUser:
    def test_weekend_help_desk_format(self):
        event = {"summary": "Kyle - Weekend Help Desk"}
        assert get_user(event) == "Kyle"

    def test_weekend_help_desk_full_name(self):
        event = {"summary": "Kyle Hall - Weekend Help Desk Duty"}
        assert get_user(event) == "Kyle Hall"

    def test_weekend_duty_format(self):
        event = {"summary": "Eric - Weekend Duty"}
        assert get_user(event) == "Eric"

    def test_weekend_duty_full_name(self):
        event = {"summary": "Andrew FH - Weekend Duty"}
        assert get_user(event) == "Andrew FH"

    def test_holiday_weekend_duty_format(self):
        event = {"summary": "Donna - Holiday Weekend Duty (4th of July)"}
        assert get_user(event) == "Donna"

    def test_fire_duty_format(self):
        event = {"summary": "Fire Duty: Kyle"}
        assert get_user(event) == "Kyle"

    def test_fire_duty_full_name(self):
        event = {"summary": "Fire Duty: Kyle Hall"}
        assert get_user(event) == "Kyle Hall"

    def test_returns_none_for_unparseable(self):
        event = {"summary": "Some random event"}
        assert get_user(event) is None

    def test_returns_none_for_none_event(self):
        assert get_user(None) is None


# ---------------------------------------------------------------------------
# config tests
# ---------------------------------------------------------------------------


class TestRefreshData:
    @patch("config.load_bywaterbot_data")
    def test_refresh_success(self, mock_load):
        import config

        mock_load.return_value = {"refreshed": True}
        result = config.refresh_data()
        assert result is True
        assert config.bywaterbot_data == {"refreshed": True}

    @patch("config.load_bywaterbot_data")
    def test_refresh_failure(self, mock_load):
        import config

        mock_load.side_effect = Exception("fail")
        result = config.refresh_data()
        assert result is False


# ---------------------------------------------------------------------------
# general_handlers tests
# ---------------------------------------------------------------------------


class TestGeneralHandlers:
    def _register(self):
        """Register handlers on a mock app and return the captured handlers."""
        from general_handlers import register_general_handlers

        app = MagicMock()
        handlers = {}

        def capture_message(pattern, *args, **kwargs):
            def decorator(fn):
                key = pattern if isinstance(pattern, str) else pattern.pattern
                fn._matchers = kwargs.get("matchers") or []
                handlers[key] = fn
                return fn

            return decorator

        app.message = capture_message
        register_general_handlers(app)
        return app, handlers

    def test_help_only_in_dm(self):
        app, handlers = self._register()
        # DM-only is enforced by a listener matcher, not the handler body, so it
        # doesn't shadow channel messages that merely contain the word "help"
        (is_dm,) = handlers[r"\bhelp\b"]._matchers
        assert is_dm({"channel_type": "channel"}) is False
        assert is_dm({"channel_type": "im"}) is True

    def test_help_responds_in_dm(self):
        app, handlers = self._register()
        say = MagicMock()
        handlers[r"\bhelp\b"]({"channel_type": "im"}, say)
        say.assert_called_once()
        text = say.call_args[0][0]
        assert "ByWaterBot help" in text
        # The detailed help describes the major capabilities and how to use them
        for snippet in ["bug <id>", "TEXT <name>", "name++", "test weekend duty"]:
            assert snippet in text

    def test_help_trigger_is_case_insensitive(self):
        # "help" in any casing triggers the help, but "helpful" does not
        pattern = re.compile(r"\bhelp\b", re.IGNORECASE)
        for variant in ["help", "Help", "HELP", "please help"]:
            assert pattern.search(variant)
        assert not pattern.search("helpful")

    def test_hello(self):
        app, handlers = self._register()
        say = MagicMock()
        handlers["hello"]({"user": "U123"}, say)
        say.assert_called_once()
        assert "<@U123>" in say.call_args[0][0]

    def test_version_reports_running_version(self):
        from version import __version__

        app, handlers = self._register()
        say = MagicMock()
        handlers[r"\bversion\b"]({"channel_type": "im"}, say)
        say.assert_called_once()
        assert __version__ in say.call_args[0][0]

    def test_version_is_dm_only(self):
        app, handlers = self._register()
        (is_dm,) = handlers[r"\bversion\b"]._matchers
        assert is_dm({"channel_type": "channel"}) is False
        assert is_dm({"channel_type": "im"}) is True

    def test_wow_sends_image_block(self):
        app, handlers = self._register()
        say = MagicMock()
        handlers["^wow"]({"user": "U123"}, say)
        say.assert_called_once()
        blocks = say.call_args[1]["blocks"]
        assert blocks[0]["type"] == "image"

    def test_refresh_only_in_dm(self):
        app, handlers = self._register()
        # DM-only via a listener matcher
        (is_dm,) = handlers["Refresh Data"]._matchers
        assert is_dm({"channel_type": "channel"}) is False
        assert is_dm({"channel_type": "im"}) is True

    @patch("config.refresh_data", return_value=True)
    def test_refresh_success(self, mock_refresh):
        app, handlers = self._register()
        say = MagicMock()
        handlers["Refresh Data"]({"channel_type": "im"}, say)
        say.assert_called_once()
        assert "success" in say.call_args[0][0].lower()


# ---------------------------------------------------------------------------
# karma_handlers tests
# ---------------------------------------------------------------------------


class TestKarmaHandlers:
    def _register(self):
        from karma_handlers import register_karma_handlers

        app = MagicMock()
        handlers = {}

        def capture_message(pattern, *args, **kwargs):
            def decorator(fn):
                key = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
                fn._matchers = kwargs.get("matchers") or []
                handlers[key] = fn
                return fn

            return decorator

        app.message = capture_message
        register_karma_handlers(app)
        return app, handlers

    def test_negative_karma_known_user(self):
        app, handlers = self._register()
        handler = handlers[r"^(\w+)(\-\-)"]
        say = MagicMock()

        app.client.users_list.return_value = {
            "members": [
                {
                    "id": "U001",
                    "name": "kyle",
                    "real_name": "Kyle",
                    "profile": {"display_name": "kyle"},
                }
            ]
        }

        context = {"matches": ("kyle", "--")}
        handler(say, context)
        say.assert_called_once()
        assert "nice" in say.call_args[1]["text"].lower()

    def test_negative_karma_unknown_user(self):
        app, handlers = self._register()
        handler = handlers[r"^(\w+)(\-\-)"]
        say = MagicMock()

        app.client.users_list.return_value = {
            "members": [
                {
                    "id": "U001",
                    "name": "kyle",
                    "real_name": "Kyle",
                    "profile": {"display_name": "kyle"},
                }
            ]
        }

        context = {"matches": ("mondays", "--")}
        handler(say, context)
        say.assert_called_once()
        assert "mondays" in say.call_args[1]["text"]


# ---------------------------------------------------------------------------
# devops_handlers tests
# ---------------------------------------------------------------------------


class TestDevopsHandlers:
    def _register(self):
        from devops_handlers import register_devops_handlers

        app = MagicMock()
        app.client.conversations_list.return_value = {
            "channels": [{"name": "devops", "id": "CDEVOPS"}]
        }
        handlers = {}

        def capture_event(event_name):
            def decorator(fn):
                handlers[event_name] = fn
                return fn

            return decorator

        app.event = capture_event
        register_devops_handlers(app)
        return app, handlers

    @patch("devops_handlers.get_weekday_duty", return_value=None)
    @patch("devops_handlers.get_devops_fire_duty_asignee", return_value=None)
    def test_fire_reaction_triggers_handler(self, mock_assignee, mock_duty):
        app, handlers = self._register()
        logger = MagicMock()

        app.client.conversations_history.return_value = {
            "messages": [{"text": "Server is down!"}]
        }

        body = {
            "event": {
                "type": "reaction_added",
                "reaction": "fire",
                "item": {"channel": "CDEVOPS", "ts": "123.456"},
            }
        }

        handlers["reaction_added"](body, logger)
        # A fire reaction in #devops runs the fire path: it fetches the
        # reacted-to message and looks up who's on devops fire duty.
        app.client.conversations_history.assert_called()
        mock_assignee.assert_called()

    @patch("devops_handlers.get_weekday_duty", return_value=None)
    @patch("devops_handlers.get_devops_fire_duty_asignee", return_value=None)
    def test_non_fire_reaction_ignored(self, mock_assignee, mock_duty):
        app, handlers = self._register()
        logger = MagicMock()

        body = {
            "event": {
                "type": "reaction_added",
                "reaction": "thumbsup",
                "item": {"channel": "CDEVOPS", "ts": "123.456"},
            }
        }

        handlers["reaction_added"](body, logger)
        app.client.chat_postMessage.assert_not_called()

    @patch("devops_handlers.get_weekday_duty", return_value=None)
    @patch("devops_handlers.get_devops_fire_duty_asignee", return_value=None)
    def test_wrong_channel_ignored(self, mock_assignee, mock_duty):
        app, handlers = self._register()
        logger = MagicMock()

        body = {
            "event": {
                "type": "reaction_added",
                "reaction": "fire",
                "item": {"channel": "COTHER", "ts": "123.456"},
            }
        }

        handlers["reaction_added"](body, logger)
        app.client.chat_postMessage.assert_not_called()

    @patch("devops_handlers.get_weekday_duty")
    @patch("devops_handlers.get_devops_fire_duty_asignee", return_value=None)
    @patch("devops_handlers.get_user", return_value="Kyle")
    def test_fire_alerts_duty_user(self, mock_get_user, mock_assignee, mock_duty):
        import config

        config.bywaterbot_data = {"users": {"Kyle": {"sms": "+15551234567"}}}
        config.twilio_client = MagicMock()
        config.twilio_phone = "+15559999999"

        mock_event = {"summary": "Fire Duty: Kyle"}
        mock_duty.return_value = mock_event

        app, handlers = self._register()
        logger = MagicMock()

        app.client.conversations_history.return_value = {
            "messages": [{"text": "Server down"}]
        }

        body = {
            "event": {
                "type": "reaction_added",
                "reaction": "fire",
                "item": {"channel": "CDEVOPS", "ts": "123.456"},
            }
        }

        handlers["reaction_added"](body, logger)
        # Should have posted alert message to slack
        assert app.client.chat_postMessage.call_count >= 1


# ---------------------------------------------------------------------------
# support_handlers tests
# ---------------------------------------------------------------------------


class TestSupportHandlers:
    def _register(self):
        from support_handlers import (
            register_support_handlers,
            register_ticket_notifier,
        )

        app = MagicMock()
        app.client.conversations_list.return_value = {
            "channels": [{"name": "tickets", "id": "CTICKETS"}]
        }
        handlers = {}

        def capture_message(pattern, *args, **kwargs):
            def decorator(fn):
                key = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
                fn._matchers = kwargs.get("matchers") or []
                handlers[key] = fn
                return fn

            return decorator

        app.message = capture_message
        register_ticket_notifier(app)
        register_support_handlers(app)
        return app, handlers

    @patch("support_handlers.requests.get")
    def test_handle_koha_bug(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {"bugs": [{"summary": "Fix login", "status": "NEW"}]}
        )
        mock_get.return_value = mock_response

        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("bug", "12345")}

        handler = handlers[r"(bug|bz)\s*([0-9]+)"]
        handler(say, context)

        say.assert_called_once()
        assert "12345" in str(say.call_args)

    @patch("support_handlers.requests.get")
    def test_handle_koha_bug_error(self, mock_get):
        mock_get.side_effect = Exception("Network error")

        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("bug", "99999")}

        handler = handlers[r"(bug|bz)\s*([0-9]+)"]
        handler(say, context)

        say.assert_called_once()
        assert "couldn't find" in say.call_args[0][0].lower()

    @patch("support_handlers.requests.get")
    def test_handle_branches_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = json.dumps(["v22.11.x", "v23.05.x"])
        mock_get.return_value = mock_response

        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("branches", "12345", "bywater")}

        handler = handlers[r"(branches)\s*(\d+)\s*(\S*)"]
        handler(say, context)

        # First call is "Looking for bug..." second is results
        assert say.call_count == 2

    @patch("support_handlers.requests.get")
    def test_handle_branches_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = json.dumps([])
        mock_get.return_value = mock_response

        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("branches", "12345", "bywater")}

        handler = handlers[r"(branches)\s*(\d+)\s*(\S*)"]
        handler(say, context)

        assert say.call_count == 2
        assert "could not find" in say.call_args[1]["text"].lower()

    def test_handle_text_command_user_not_found(self):
        import config

        config.bywaterbot_data = {"users": {"Kyle": {"sms": "+15551234567"}}}

        app, handlers = self._register()
        app.client.users_info.return_value = MagicMock(
            data={"user": {"real_name": "Tester"}}
        )

        say = MagicMock()
        context = {"matches": ("Nobody Hello there",), "user_id": "U001"}

        handler = handlers[r"TEXT (.*)"]
        handler(say, context)

        say.assert_called_once()
        assert "unable to find" in say.call_args[0][0].lower()

    def test_handle_text_command_user_found(self):
        import config

        config.bywaterbot_data = {"users": {"Kyle": {"sms": "+15551234567"}}}
        config.twilio_client = MagicMock()
        config.twilio_phone = "+15559999999"

        app, handlers = self._register()
        app.client.users_info.return_value = MagicMock(
            data={"user": {"real_name": "Tester"}}
        )

        say = MagicMock()
        context = {"matches": ("Kyle Hello there",), "user_id": "U001"}

        handler = handlers[r"TEXT (.*)"]
        handler(say, context)

        say.assert_called_once()
        assert "sent" in say.call_args[0][0].lower()
        config.twilio_client.messages.create.assert_called_once()

    def test_new_ticket_regex_matches_zoho_format(self):
        pattern = re.compile(r"\*New Ticket:\*\s+ZD\s+#(\d+)\s+-\s+(.+)")
        m = pattern.search("*New Ticket:* ZD #215390 - Libby Authentication")
        assert m is not None
        assert m.group(1) == "215390"
        assert m.group(2) == "Libby Authentication"

    @patch("support_handlers.get_user", return_value="Eric")
    @patch(
        "support_handlers.get_weekend_duty",
        return_value={"summary": "Eric - Weekend Duty"},
    )
    def test_handle_ticket_created_alerts_duty_user(self, mock_duty, mock_user):
        import config

        config.bywaterbot_data = {"users": {"Eric": {"sms": "+15551234567"}}}
        config.twilio_client = MagicMock()
        config.twilio_phone = "+15559999999"

        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("215390", "Libby Authentication")}
        message = {
            "text": (
                "*New Ticket:* ZD #215390 - Libby Authentication\n"
                "*Product:* Koha\n"
                "*Partner:* Waterford Township Public Library\n"
                "*Criticality:* Workflow blocker\n"
                "<https://help.bywatersolutions.com/support/bywatersolutions/"
                "ShowHomePage.do#Cases/dv/1025376000029707268>"
            )
        }

        handler = handlers[r"\*New Ticket:\*\s+ZD\s+#(\d+)\s+-\s+(.+)"]
        handler(say, context, message)

        say.assert_called_once()
        assert "Eric" in say.call_args[1]["text"]
        config.twilio_client.messages.create.assert_called_once()
        body = config.twilio_client.messages.create.call_args[1]["body"]
        assert "Koha ticket ZD #215390" in body
        assert "Waterford Township Public Library" in body
        assert "Libby Authentication" in body
        assert "help.bywatersolutions.com" in body

    _DUTY_TEST_PATTERN = r"test weekend duty(\s+sms)?"

    @patch("support_handlers.get_user", return_value="Eric")
    @patch(
        "support_handlers.get_weekend_duty",
        return_value={"summary": "Eric - Weekend Duty"},
    )
    def test_weekend_duty_test_dry_run(self, mock_duty, mock_user):
        import config

        config.bywaterbot_data = {"users": {"Eric": {"sms": "+17853046476"}}}
        config.twilio_client = MagicMock()
        config.twilio_phone = "+15559999999"

        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": (None,)}
        message = {"channel": "CTICKETS", "text": "test weekend duty"}

        handlers[self._DUTY_TEST_PATTERN](say, context, message)

        say.assert_called_once()
        text = say.call_args[1]["text"]
        assert "Eric" in text
        assert "6476" in text  # masked number, last 4 digits
        config.twilio_client.messages.create.assert_not_called()

    @patch("support_handlers.get_user", return_value="Eric")
    @patch(
        "support_handlers.get_weekend_duty",
        return_value={"summary": "Eric - Weekend Duty"},
    )
    def test_weekend_duty_test_sends_sms(self, mock_duty, mock_user):
        import config

        config.bywaterbot_data = {"users": {"Eric": {"sms": "+17853046476"}}}
        config.twilio_client = MagicMock()
        config.twilio_phone = "+15559999999"

        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": (" sms",)}
        message = {"channel": "CTICKETS", "text": "test weekend duty sms"}

        handlers[self._DUTY_TEST_PATTERN](say, context, message)

        config.twilio_client.messages.create.assert_called_once()
        assert config.twilio_client.messages.create.call_args[1]["to"] == "+17853046476"
        assert "Eric" in say.call_args[1]["text"]

    def test_weekend_duty_test_ignored_outside_tickets(self):
        app, handlers = self._register()
        # Restricted to #tickets by a listener matcher ( CTICKETS in this harness )
        (in_tickets,) = handlers[self._DUTY_TEST_PATTERN]._matchers
        assert in_tickets({"channel": "COTHER"}) is False
        assert in_tickets({"channel": "CTICKETS"}) is True

    @patch("support_handlers.get_user", return_value="Yannis")
    @patch(
        "support_handlers.get_weekend_duty",
        return_value={"summary": "Yannis - Weekend Duty"},
    )
    def test_weekend_duty_test_no_sms_on_file(self, mock_duty, mock_user):
        import config

        config.bywaterbot_data = {"users": {"Eric": {"sms": "+17853046476"}}}
        config.twilio_client = MagicMock()
        config.twilio_phone = "+15559999999"

        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": (" sms",)}
        message = {"channel": "CTICKETS", "text": "test weekend duty sms"}

        handlers[self._DUTY_TEST_PATTERN](say, context, message)

        say.assert_called_once()
        assert "no SMS number" in say.call_args[1]["text"]
        config.twilio_client.messages.create.assert_not_called()

    _ZOHO_TICKET_PATTERN = r"(ticket|zd)\s*#?\s*([0-9]+)"

    _SAMPLE_TICKET = {
        "ticketNumber": "215390",
        "subject": "Libby Authentication",
        "status": "New",
        "priority": "Medium (workflow blocker)",
        "assignee": {"firstName": "Eric", "lastName": "Swenson"},
        "contact": {
            "firstName": "Dana",
            "lastName": "Nicklas",
            "account": {"accountName": "Waterford Township Public Library"},
        },
        "webUrl": "https://help.bywatersolutions.com/agent/x#Cases/dv/123",
    }

    @patch("support_handlers.zoho_configured", return_value=True)
    @patch("support_handlers.get_zoho_ticket")
    def test_handle_zoho_ticket_found(self, mock_get_ticket, mock_configured):
        mock_get_ticket.return_value = self._SAMPLE_TICKET

        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("ticket", "215390")}
        message = {"text": "ticket 215390", "user": "U1"}

        handlers[self._ZOHO_TICKET_PATTERN](say, context, message)

        say.assert_called_once()
        kwargs = say.call_args[1]
        assert "215390" in kwargs["text"]
        rendered = str(kwargs["blocks"])
        assert "Libby Authentication" in rendered
        assert "Eric Swenson" in rendered
        assert "Waterford Township Public Library" in rendered

    @patch("support_handlers.zoho_configured", return_value=False)
    @patch("support_handlers.get_zoho_ticket")
    def test_handle_zoho_ticket_not_configured(self, mock_get_ticket, mock_configured):
        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("ticket", "215390")}
        message = {"text": "ticket 215390", "user": "U1"}

        handlers[self._ZOHO_TICKET_PATTERN](say, context, message)

        say.assert_called_once()
        assert "not configured" in say.call_args[0][0].lower()
        mock_get_ticket.assert_not_called()

    @patch("support_handlers.zoho_configured", return_value=True)
    @patch("support_handlers.get_zoho_ticket", return_value=None)
    def test_handle_zoho_ticket_not_found(self, mock_get_ticket, mock_configured):
        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("zd", "999999")}
        message = {"text": "zd #999999", "user": "U1"}

        handlers[self._ZOHO_TICKET_PATTERN](say, context, message)

        say.assert_called_once()
        assert "not found" in say.call_args[0][0].lower()

    def test_handle_zoho_ticket_ignores_bot_messages(self):
        # The Zoho Flow "New Ticket" announcement is a bot message; a listener
        # matcher keeps the lookup off it, so it neither does a second lookup nor
        # shadows the new-ticket notifier registered ahead of it
        app, handlers = self._register()
        (not_bot,) = handlers[self._ZOHO_TICKET_PATTERN]._matchers
        assert not_bot({"bot_id": "B08GUPHPLG0"}) is False
        assert not_bot({"subtype": "bot_message"}) is False
        assert not_bot({"text": "zd 215390", "user": "U1"}) is True


# ---------------------------------------------------------------------------
# zoho_functions tests
# ---------------------------------------------------------------------------

ZOHO_ENV = {
    "ZOHO_CLIENT_ID": "cid",
    "ZOHO_CLIENT_SECRET": "secret",
    "ZOHO_REFRESH_TOKEN": "rtok",
    "ZOHO_DESK_ORG_ID": "868351381",
}


class TestZohoFunctions:
    @patch.dict(os.environ, ZOHO_ENV, clear=True)
    def test_configured_true(self):
        import zoho_functions

        assert zoho_functions.zoho_configured() is True

    @patch.dict(os.environ, {}, clear=True)
    def test_configured_false(self):
        import zoho_functions

        assert zoho_functions.zoho_configured() is False

    @patch.dict(os.environ, ZOHO_ENV, clear=True)
    @patch("zoho_functions.requests.post")
    def test_access_token_caches(self, mock_post):
        import zoho_functions

        zoho_functions._access_token = None
        zoho_functions._access_token_expiry = 0
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = {
            "access_token": "tok123",
            "expires_in": 3600,
        }

        assert zoho_functions.get_zoho_access_token() == "tok123"
        # Second call serves from cache, no new token request
        assert zoho_functions.get_zoho_access_token() == "tok123"
        mock_post.assert_called_once()

    @patch.dict(os.environ, ZOHO_ENV, clear=True)
    @patch("zoho_functions.get_zoho_access_token", return_value="tok")
    @patch("zoho_functions.requests.get")
    def test_get_ticket_found(self, mock_get, mock_token):
        import zoho_functions

        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = {
            "data": [{"ticketNumber": "215390", "subject": "Libby Authentication"}]
        }

        ticket = zoho_functions.get_zoho_ticket("215390")
        assert ticket["subject"] == "Libby Authentication"

    @patch.dict(os.environ, ZOHO_ENV, clear=True)
    @patch("zoho_functions.get_zoho_access_token", return_value="tok")
    @patch("zoho_functions.requests.get")
    def test_get_ticket_not_found_returns_none(self, mock_get, mock_token):
        import zoho_functions

        mock_get.return_value = MagicMock(status_code=204)
        assert zoho_functions.get_zoho_ticket("999999") is None

    @patch.dict(os.environ, {}, clear=True)
    def test_get_ticket_not_configured_returns_none(self):
        import zoho_functions

        assert zoho_functions.get_zoho_ticket("215390") is None


# ---------------------------------------------------------------------------
# partner_handlers tests
# ---------------------------------------------------------------------------

from partner_handlers import PARTNERS


class TestPartnerHandlers:
    def _register(self):
        from partner_handlers import register_partner_handlers

        app = MagicMock()
        handlers = {}

        def capture_message(pattern, *args, **kwargs):
            def decorator(fn):
                key = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
                fn._matchers = kwargs.get("matchers") or []
                handlers[key] = fn
                return fn

            return decorator

        app.message = capture_message
        register_partner_handlers(app)
        return app, handlers

    def test_innreach_partners(self):
        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("innreach",)}

        handler = handlers[r"(innreach|rapido)\s+partners"]
        handler(say, context)

        say.assert_called_once()
        text = say.call_args[1]["text"]
        assert "INN-Reach Partners" in text
        assert "(7)" in text
        for partner in PARTNERS["innreach"]:
            assert partner in text

    def test_rapido_partners(self):
        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("rapido",)}

        handler = handlers[r"(innreach|rapido)\s+partners"]
        handler(say, context)

        say.assert_called_once()
        text = say.call_args[1]["text"]
        assert "Rapido Partners" in text
        assert "(4)" in text
        for partner in PARTNERS["rapido"]:
            assert partner in text

    def test_partners_sorted_alphabetically(self):
        for product, partners in PARTNERS.items():
            assert partners == sorted(partners), f"{product} partners not sorted"

    def test_innreach_label_formatting(self):
        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("innreach",)}

        handler = handlers[r"(innreach|rapido)\s+partners"]
        handler(say, context)

        text = say.call_args[1]["text"]
        # Should use "INN-Reach" not "innreach"
        assert "INN-Reach" in text

    def test_rapido_label_formatting(self):
        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("rapido",)}

        handler = handlers[r"(innreach|rapido)\s+partners"]
        handler(say, context)

        text = say.call_args[1]["text"]
        assert "Rapido" in text

    def test_output_uses_bullet_points(self):
        app, handlers = self._register()
        say = MagicMock()
        context = {"matches": ("rapido",)}

        handler = handlers[r"(innreach|rapido)\s+partners"]
        handler(say, context)

        text = say.call_args[1]["text"]
        assert text.count("* ") == len(PARTNERS["rapido"])


# ---------------------------------------------------------------------------
# bot_functions data-persistence tests
# ---------------------------------------------------------------------------

import bot_functions


class TestDataPersistence:
    def test_parse_github_repo_url(self):
        coords = bot_functions._parse_github_repo_url(
            "https://github.com/bywatersolutions/secret-repo/blob/main/data.json"
        )
        assert coords == ("bywatersolutions", "secret-repo", "main", "data.json")

    def test_parse_github_repo_url_invalid(self):
        assert bot_functions._parse_github_repo_url("https://example.com/x") is None

    @patch.dict(
        os.environ,
        {
            "BYWATER_BOT_DATA_URL": "https://github.com/o/r/blob/main/data.json",
            "BYWATER_BOT_GITHUB_TOKEN": "tok",
        },
        clear=True,
    )
    @patch("bot_functions.requests.get")
    def test_read_for_update_github(self, mock_get):
        import base64

        content = base64.b64encode(
            json.dumps({"users": {"Eric": {"sms": "+1"}}}).encode()
        ).decode()
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = {"sha": "abc123", "content": content}

        data, ctx = bot_functions.read_bywaterbot_data_for_update()
        assert data["users"]["Eric"]["sms"] == "+1"
        assert ctx["source"] == "github"
        assert ctx["sha"] == "abc123"
        assert ctx["owner"] == "o" and ctx["repo"] == "r" and ctx["branch"] == "main"

    @patch("bot_functions.requests.put")
    def test_write_github_commits_with_sha(self, mock_put):
        mock_put.return_value = MagicMock(status_code=200)
        ctx = {
            "source": "github",
            "owner": "o",
            "repo": "r",
            "branch": "main",
            "path": "data.json",
            "sha": "abc123",
            "token": "tok",
        }
        assert bot_functions.write_bywaterbot_data({"users": {}}, ctx, "msg") is True
        body = mock_put.call_args[1]["json"]
        assert body["sha"] == "abc123"
        assert body["branch"] == "main"
        assert body["message"] == "msg"
        assert "content" in body

    def test_local_read_write_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.delenv("BYWATER_BOT_DATA_URL", raising=False)
        monkeypatch.delenv("BYWATER_BOT_GITHUB_TOKEN", raising=False)
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data.json").write_text(json.dumps({"users": {"Kyle": {}}}))

        data, ctx = bot_functions.read_bywaterbot_data_for_update()
        assert ctx["source"] == "local"
        data["users"]["Kyle"]["sms"] = "+19998887777"
        assert bot_functions.write_bywaterbot_data(data, ctx, "msg") is True

        reread = json.loads((tmp_path / "data.json").read_text())
        assert reread["users"]["Kyle"]["sms"] == "+19998887777"


# ---------------------------------------------------------------------------
# contact_handlers tests
# ---------------------------------------------------------------------------

import contact_handlers

CLAIM_KEY = r"^\s*claim\s+(.+)"
SET_SMS_KEY = (
    r"^\s*(?:set|update)\s+my\s+(?:sms|number|phone|cell)" r"(?:\s+(?:to|is|=))?\s+(.+)"
)
MY_INFO_KEY = r"^\s*(?:my\s+(?:contact\s+)?info|whoami)\s*$"


class TestNormalizePhone:
    def test_us_ten_digits(self):
        assert contact_handlers.normalize_phone("207-660-2101") == "+12076602101"

    def test_us_eleven_digits(self):
        assert contact_handlers.normalize_phone("1 (207) 660-2101") == "+12076602101"

    def test_already_e164(self):
        assert contact_handlers.normalize_phone("+12076602101") == "+12076602101"

    def test_invalid(self):
        assert contact_handlers.normalize_phone("not a number") is None


class TestContactHandlers:
    def _register(self):
        from contact_handlers import register_contact_handlers

        app = MagicMock()
        handlers = {}

        def capture_message(pattern, *args, **kwargs):
            def decorator(fn):
                key = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
                fn._matchers = kwargs.get("matchers") or []
                handlers[key] = fn
                return fn

            return decorator

        app.message = capture_message
        register_contact_handlers(app)
        return app, handlers

    @patch("contact_handlers.write_bywaterbot_data", return_value=True)
    @patch("contact_handlers.read_bywaterbot_data_for_update")
    def test_claim_new_name(self, mock_read, mock_write):
        import config

        config.bywaterbot_data = {}
        data = {"users": {}}
        mock_read.return_value = (data, {"source": "local", "path": "data.json"})

        app, handlers = self._register()
        say = MagicMock()
        message = {"channel_type": "im", "user": "U1"}
        context = {"matches": ("Laura O",)}

        handlers[CLAIM_KEY](message, say, context)

        assert data["users"]["Laura O"]["slack_id"] == "U1"
        mock_write.assert_called_once()
        assert "Laura O" in say.call_args[0][0]

    @patch("contact_handlers.write_bywaterbot_data", return_value=True)
    @patch("contact_handlers.read_bywaterbot_data_for_update")
    def test_claim_refused_when_owned_by_other(self, mock_read, mock_write):
        data = {"users": {"Eric": {"sms": "+1", "slack_id": "U2"}}}
        mock_read.return_value = (data, {"source": "local", "path": "data.json"})

        app, handlers = self._register()
        say = MagicMock()
        message = {"channel_type": "im", "user": "U1"}
        context = {"matches": ("Eric",)}

        handlers[CLAIM_KEY](message, say, context)

        assert "already claimed" in say.call_args[0][0].lower()
        mock_write.assert_not_called()
        assert data["users"]["Eric"]["slack_id"] == "U2"

    @patch("contact_handlers.write_bywaterbot_data", return_value=True)
    @patch("contact_handlers.read_bywaterbot_data_for_update")
    def test_set_my_sms_when_claimed(self, mock_read, mock_write):
        import config

        config.bywaterbot_data = {}
        data = {"users": {"Eric": {"sms": "+1", "slack_id": "U1"}}}
        mock_read.return_value = (data, {"source": "local", "path": "data.json"})

        app, handlers = self._register()
        say = MagicMock()
        message = {"channel_type": "im", "user": "U1"}
        context = {"matches": ("207-660-2101",)}

        handlers[SET_SMS_KEY](message, say, context)

        assert data["users"]["Eric"]["sms"] == "+12076602101"
        mock_write.assert_called_once()
        assert "2101" in say.call_args[0][0]

    @patch("contact_handlers.write_bywaterbot_data", return_value=True)
    @patch("contact_handlers.read_bywaterbot_data_for_update")
    def test_set_my_sms_requires_claim(self, mock_read, mock_write):
        data = {"users": {}}
        mock_read.return_value = (data, {"source": "local", "path": "data.json"})

        app, handlers = self._register()
        say = MagicMock()
        message = {"channel_type": "im", "user": "U1"}
        context = {"matches": ("207-660-2101",)}

        handlers[SET_SMS_KEY](message, say, context)

        assert "claim" in say.call_args[0][0].lower()
        mock_write.assert_not_called()

    @patch("contact_handlers.write_bywaterbot_data", return_value=True)
    @patch("contact_handlers.read_bywaterbot_data_for_update")
    def test_set_my_sms_rejects_bad_number(self, mock_read, mock_write):
        app, handlers = self._register()
        say = MagicMock()
        message = {"channel_type": "im", "user": "U1"}
        context = {"matches": ("nope",)}

        handlers[SET_SMS_KEY](message, say, context)

        assert "phone number" in say.call_args[0][0].lower()
        mock_read.assert_not_called()
        mock_write.assert_not_called()

    def test_my_info_shows_masked_number(self):
        import config

        config.bywaterbot_data = {
            "users": {"Eric": {"sms": "+12076602101", "slack_id": "U1"}}
        }

        app, handlers = self._register()
        say = MagicMock()
        message = {"channel_type": "im", "user": "U1"}

        handlers[MY_INFO_KEY](message, say)

        text = say.call_args[0][0]
        assert "Eric" in text
        assert "2101" in text
        assert "12076602101" not in text  # full number must be masked

    def test_my_info_unclaimed(self):
        import config

        config.bywaterbot_data = {"users": {}}

        app, handlers = self._register()
        say = MagicMock()
        message = {"channel_type": "im", "user": "U1"}

        handlers[MY_INFO_KEY](message, say)

        assert "claim" in say.call_args[0][0].lower()

    def test_commands_ignored_outside_dm(self):
        app, handlers = self._register()
        # All three contact commands are DM-only via a listener matcher
        for key in (CLAIM_KEY, SET_SMS_KEY, MY_INFO_KEY):
            (is_dm,) = handlers[key]._matchers
            assert is_dm({"channel_type": "channel"}) is False
            assert is_dm({"channel_type": "im"}) is True


# ---------------------------------------------------------------------------
# message_matchers tests
# ---------------------------------------------------------------------------

from message_matchers import is_direct_message, is_not_bot_message


class TestMessageMatchers:
    def test_is_direct_message(self):
        assert is_direct_message({"channel_type": "im"}) is True
        assert is_direct_message({"channel_type": "channel"}) is False
        assert is_direct_message({}) is False

    def test_is_not_bot_message_human(self):
        assert is_not_bot_message({"user": "U1", "text": "hi"}) is True

    def test_is_not_bot_message_bot_id(self):
        assert is_not_bot_message({"bot_id": "B08GUPHPLG0"}) is False

    def test_is_not_bot_message_subtype(self):
        assert is_not_bot_message({"subtype": "bot_message"}) is False


# ---------------------------------------------------------------------------
# Handler routing / shadowing — real Bolt dispatch, production registration order
# ---------------------------------------------------------------------------

import bywaterbot


def _build_real_app():
    """A real Bolt App with every handler registered via bywaterbot.register_handlers.

    Uses the actual production registration order so a reordering or a missing
    matcher that reintroduces handler shadowing fails these tests.
    """
    from slack_bolt import App
    from slack_bolt.authorization import AuthorizeResult

    app = App(
        token="xoxb-test",
        signing_secret="secret",
        token_verification_enabled=False,
        request_verification_enabled=False,
        ssl_check_enabled=False,
        raise_error_for_unhandled_request=False,
        authorize=lambda *a, **k: AuthorizeResult(
            enterprise_id=None,
            team_id="T1",
            bot_user_id="UBOTUSER",
            bot_id="BBOTSELF",
            bot_token="xoxb-test",
        ),
    )
    client = MagicMock()
    client.conversations_list.return_value = {
        "channels": [
            {"name": "tickets", "id": "CTICKETS"},
            {"name": "devops-alerts", "id": "CALERTS"},
            {"name": "devops", "id": "CDEVOPS"},
        ]
    }
    client.users_list.return_value = {"members": []}
    client.auth_test.return_value = {"user_id": "UBOTUSER"}
    app._client = client

    import config

    config.bywaterbot_data = {"users": {"Eric": {"sms": "+15550000000"}}}
    bywaterbot.register_handlers(app)
    return app


def _winning_handler(app, event):
    """Name of the listener Bolt would actually run for this event.

    Replicates App.dispatch's first-match-wins selection ( the first listener
    whose matchers and listener middleware pass ) without executing handler
    bodies, so routing/shadowing can be asserted on the pinned slack_bolt 1.14.3
    without mocking every handler's dependencies.
    """
    from slack_bolt.request import BoltRequest
    from slack_bolt.response import BoltResponse
    from slack_bolt.util.utils import get_name_for_callable

    req = BoltRequest(
        body={"type": "event_callback", "team_id": "T1", "event": event},
        mode="socket_mode",
    )
    resp = BoltResponse(status=200)
    for listener in app._listeners:
        if listener.matches(req=req, resp=resp):
            _, terminated = listener.run_middleware(req=req, resp=resp)
            if not terminated:
                return get_name_for_callable(listener.ack_function)
    return None


def _event(text, channel="CTICKETS", channel_type="channel", bot=False, user="UHUMAN"):
    event = {
        "type": "message",
        "channel": channel,
        "ts": "1.1",
        "channel_type": channel_type,
        "text": text,
    }
    if bot:
        event["subtype"] = "bot_message"
        event["bot_id"] = "BZOHOFLOW"
    else:
        event["user"] = user
    return event


class TestHandlerRouting:
    """The right handler wins for each message under real first-match dispatch."""

    TICKET = (
        "*New Ticket:* ZD #215440 - Aspen searches timing out\n"
        "*Product:* Koha\n*Partner:* CLAMS\n"
        "<https://help.bywatersolutions.com/support/x#Cases/dv/1>"
    )

    def test_zoho_new_ticket_reaches_notifier(self):
        # The Zoho Flow post contains "help" ( in the URL ) and "ZD #215440",
        # which match message_help and the ticket lookup; it must still win.
        app = _build_real_app()
        assert (
            _winning_handler(app, _event(self.TICKET, bot=True))
            == "handle_ticket_created"
        )

    def test_devops_failure_with_trigger_words_reaches_watcher(self):
        # A failure post containing "help"/"hello"/"bug 5" must not be swallowed
        # by a human handler before reaching the #devops-alerts watcher.
        app = _build_real_app()
        for text in (
            "Build failed, need help",
            "hello, the build failed",
            "rebase failed on bug 5",
        ):
            assert (
                _winning_handler(app, _event(text, channel="CALERTS", bot=True))
                == "handle_alerts_message"
            )

    def test_help_is_dm_only_and_does_not_shadow_channels(self):
        app = _build_real_app()
        assert (
            _winning_handler(app, _event("help", channel="D1", channel_type="im"))
            == "message_help"
        )
        # "help" in a channel must not be grabbed ( and thus shadowed ) by help
        assert _winning_handler(app, _event("I need help here")) != "message_help"

    def test_human_commands_route_correctly(self):
        app = _build_real_app()
        cases = {
            "hello": "message_hello",
            "kyle++": "handle_individual_karma",
            "zd 215390": "handle_zoho_ticket",
            "bug 38120": "handle_koha_bug",
            "branches 38120": "handle_branches",
            "TEXT Kyle hi": "handle_text_command",
            "innreach partners": "handle_partners",
        }
        for text, expected in cases.items():
            assert _winning_handler(app, _event(text)) == expected

    def test_partner_and_contact_not_shadowed_by_watcher(self):
        # These regressed before the watcher was moved last: the catch-all
        # @app.event("message") used to swallow them.
        app = _build_real_app()
        assert _winning_handler(app, _event("innreach partners")) == "handle_partners"
        assert (
            _winning_handler(
                app, _event("claim Laura O", channel="D1", channel_type="im")
            )
            == "claim_name"
        )
        assert (
            _winning_handler(app, _event("my info", channel="D1", channel_type="im"))
            == "my_info"
        )

    def test_weekend_duty_test_only_in_tickets(self):
        app = _build_real_app()
        assert (
            _winning_handler(app, _event("test weekend duty sms", channel="CTICKETS"))
            == "handle_weekend_duty_test"
        )
        assert (
            _winning_handler(app, _event("test weekend duty sms", channel="CXYZ"))
            != "handle_weekend_duty_test"
        )

    def test_version_command_dm_only(self):
        app = _build_real_app()
        assert (
            _winning_handler(app, _event("version", channel="D1", channel_type="im"))
            == "message_version"
        )
        assert _winning_handler(app, _event("version")) != "message_version"
