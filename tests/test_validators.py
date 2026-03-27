import json
import urllib.error
from unittest.mock import patch, MagicMock
from src.wizard.validators import (
    format_check_todoist, live_check_todoist,
    format_check_telegram, live_check_telegram,
    format_check_fireflies, live_check_fireflies,
    format_check_clockify, live_check_clockify,
    format_check_slack, live_check_slack,
    format_check_google_client, detect_telegram_ids
)

def test_format_check_todoist():
    assert format_check_todoist('short') == {'valid': False, 'message': 'Token is too short'}
    assert format_check_todoist('a'*40) == {'valid': True, 'message': 'Format OK', 'token': 'a'*40}

@patch('src.wizard.validators.urllib.request.urlopen')
def test_live_check_todoist(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps([{"id": 1}, {"id": 2}]).encode()
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    res = live_check_todoist('a'*40)
    assert res['valid'] is True
    assert 'Connected' in res['message']

def test_format_check_telegram():
    assert format_check_telegram('invalid') == {'valid': False, 'message': 'Token format incorrect. Expected: 123456789:ABCdef... (from @BotFather)'}
    valid_token = '123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi'
    assert format_check_telegram(valid_token) == {'valid': True, 'message': 'Format OK', 'token': valid_token}

@patch('src.wizard.validators.urllib.request.urlopen')
def test_live_check_telegram(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"ok": True, "result": {"username": "testbot"}}).encode()
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    valid_token = '123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi'
    res = live_check_telegram(valid_token)
    assert res['valid'] is True
    assert res['token'] == valid_token

def test_format_check_google_client():
    assert format_check_google_client('invalid_json')['valid'] is False
    valid_json = json.dumps({
        "installed": {
            "client_id": "test_id",
            "client_secret": "test_secret",
            "redirect_uris": ["http://localhost"]
        }
    })
    res = format_check_google_client(valid_json)
    assert res['valid'] is True
    assert res['client_id'] == "test_id"
