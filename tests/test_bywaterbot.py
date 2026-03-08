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
        csv_content = 'PQ: Some partner quote\n'
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch("bot_functions.random.choice", return_value="PQ: Some partner quote"):
                result = get_quote("http://example.com/quotes.csv")
        assert result.startswith("Partner Quote: ")
        assert "PQ: " not in result

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_prefix_replacement_haha(self, mock_retrieve):
        csv_content = 'HAHA: Funny thing\n'
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch("bot_functions.random.choice", return_value="HAHA: Funny thing"):
                result = get_quote("http://example.com/quotes.csv")
        assert result == "Funny thing"

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_prefix_replacement_move(self, mock_retrieve):
        csv_content = 'MOVE: Take a walk\n'
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch("bot_functions.random.choice", return_value="MOVE: Take a walk"):
                result = get_quote("http://example.com/quotes.csv")
        assert result == "Get up and move! Take a walk"

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_prefix_replacement_fact(self, mock_retrieve):
        csv_content = 'FACT: The sky is blue\n'
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch("bot_functions.random.choice", return_value="FACT: The sky is blue"):
                result = get_quote("http://example.com/quotes.csv")
        assert result == "Fun Fact! The sky is blue"

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_prefix_replacement_koha(self, mock_retrieve):
        csv_content = 'Koha sys pref: SomePref\n'
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch("bot_functions.random.choice", return_value="Koha sys pref: SomePref"):
                result = get_quote("http://example.com/quotes.csv")
        assert "Koha SysPref Quiz!" in result

    @patch("bot_functions.urllib.request.urlretrieve")
    def test_no_prefix(self, mock_retrieve):
        csv_content = 'Just a normal quote\n'
        with patch("builtins.open", mock_open(read_data=csv_content)):
            with patch("bot_functions.random.choice", return_value="Just a normal quote"):
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
            "channel": {
                "topic": {"value": "Fire duty is Kyle Hall\nSome other info"}
            }
        }
        result = get_devops_fire_duty_asignee(app, "C123")
        assert result == "Kyle Hall"

    def test_extracts_single_name(self):
        app = MagicMock()
        app.client.conversations_info.return_value = {
            "channel": {
                "topic": {"value": "Current duty is Kyle\nMore info"}
            }
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

        def capture_message(pattern):
            def decorator(fn):
                handlers[pattern if isinstance(pattern, str) else pattern.pattern] = fn
                return fn
            return decorator

        app.message = capture_message
        register_general_handlers(app)
        return app, handlers

    def test_help_only_in_dm(self):
        app, handlers = self._register()
        say = MagicMock()
        # Not a DM - should not respond
        handlers["help"]({"channel_type": "channel"}, say)
        say.assert_not_called()

    def test_help_responds_in_dm(self):
        app, handlers = self._register()
        say = MagicMock()
        handlers["help"]({"channel_type": "im"}, say)
        say.assert_called_once()
        assert "capabilities" in say.call_args[0][0].lower()

    def test_hello(self):
        app, handlers = self._register()
        say = MagicMock()
        handlers["hello"]({"user": "U123"}, say)
        say.assert_called_once()
        assert "<@U123>" in say.call_args[0][0]

    def test_wow_sends_image_block(self):
        app, handlers = self._register()
        say = MagicMock()
        handlers["^wow"]({"user": "U123"}, say)
        say.assert_called_once()
        blocks = say.call_args[1]["blocks"]
        assert blocks[0]["type"] == "image"

    def test_refresh_only_in_dm(self):
        app, handlers = self._register()
        say = MagicMock()
        handlers["Refresh Data"]({"channel_type": "channel"}, say)
        say.assert_not_called()

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

        def capture_message(pattern):
            def decorator(fn):
                key = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
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
        # Should post the "tag ticket" message
        app.client.chat_postMessage.assert_called()
        call_args = app.client.chat_postMessage.call_args
        assert "devops_fire" in call_args[1]["text"]

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

        config.bywaterbot_data = {
            "users": {"Kyle": {"sms": "+15551234567"}}
        }
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
        from support_handlers import register_support_handlers

        app = MagicMock()
        handlers = {}

        def capture_message(pattern):
            def decorator(fn):
                key = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
                handlers[key] = fn
                return fn
            return decorator

        app.message = capture_message
        register_support_handlers(app)
        return app, handlers

    @patch("support_handlers.requests.get")
    def test_handle_koha_bug(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "bugs": [{"summary": "Fix login", "status": "NEW"}]
        })
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
