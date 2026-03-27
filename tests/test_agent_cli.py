from unittest.mock import patch, MagicMock
from src.wizard.agent_cli import _resolve_command, _assistant_status, detect, install_default

@patch('src.wizard.agent_cli.shutil.which')
@patch('src.wizard.agent_cli._refresh_known_paths')
def test_resolve_command(mock_refresh, mock_which):
    mock_which.return_value = '/fake/path/codex'
    assert _resolve_command('codex') == '/fake/path/codex'

@patch('src.wizard.agent_cli._resolve_command')
def test_assistant_status(mock_resolve):
    mock_resolve.return_value = '/usr/bin/codex'
    status = _assistant_status('codex')
    assert status['key'] == 'codex'
    assert status['installed'] is True
    assert status['path'] == '/usr/bin/codex'

@patch('src.wizard.agent_cli._assistant_status')
@patch('src.wizard.agent_cli.SUPPORTED_PLATFORM', True)
@patch('src.wizard.agent_cli.WINDOWS', False)
@patch('src.wizard.agent_cli.MACOS', True)
def test_detect_macos(mock_status):
    mock_status.side_effect = [
        {'key': 'codex', 'label': 'Codex', 'command': 'codex', 'installed': True, 'path': '/opt/codex'},
        {'key': 'claude', 'label': 'Claude', 'command': 'claude', 'installed': False, 'path': None}
    ]
    res = detect()
    assert res['supported'] is True
    assert res['platform'] == 'macos'
    assert res['installed_any'] is True
    assert res['preferred'] == 'codex'

@patch('src.wizard.agent_cli._run')
@patch('src.wizard.agent_cli._resolve_command')
@patch('src.wizard.agent_cli.detect')
def test_install_default_macos(mock_detect, mock_resolve_command, mock_run):
    mock_detect.return_value = {
        'supported': True,
        'platform': 'macos',
        'assistants': [{'key': 'codex', 'installed': False, 'path': None}],
        'installed_any': False,
        'preferred': None
    }
    mock_resolve_command.side_effect = ['/usr/local/bin/npm', '/usr/local/bin/npm']
    mock_run.return_value = MagicMock()

    res = install_default()
    assert 'ok' in res
