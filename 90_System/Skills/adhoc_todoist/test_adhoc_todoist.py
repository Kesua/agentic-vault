import argparse
import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("adhoc_todoist.py")
SPEC = importlib.util.spec_from_file_location("adhoc_todoist", MODULE_PATH)
todoist = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(todoist)


class TodoistOrganizationCommandsTests(unittest.TestCase):
    def test_move_task_places_existing_task_under_requested_parent(self):
        """Fails if a move calls another endpoint or omits the parent ID."""
        args = argparse.Namespace(task_id="child-1", parent_id="parent-1")
        response = {
            "id": "child-1",
            "content": "Child task",
            "project_id": "inbox-1",
            "parent_id": "parent-1",
            "labels": [],
            "priority": 1,
        }

        with (
            patch.object(todoist.todo_base, "_load_todoist_token", return_value="token"),
            patch.object(todoist, "_todoist_request", return_value=response) as request_call,
            patch.object(todoist.todo_base, "_fetch_name_map", return_value={"inbox-1": "Inbox"}),
            redirect_stdout(io.StringIO()) as output,
        ):
            todoist.command_move_task(args)

        request_call.assert_called_once_with(
            "POST",
            "https://api.todoist.com/api/v1/tasks/child-1/move",
            token="token",
            payload={"parent_id": "parent-1"},
        )
        self.assertIn('"parent_id": "parent-1"', output.getvalue())

    def test_clear_due_sends_null_due_to_todoist_sync(self):
        """Fails if clearing a due date leaves a calendar entry behind."""
        args = argparse.Namespace(task_id="child-1")

        def successful_sync(_token, command):
            return {"sync_status": {command["uuid"]: "ok"}}

        with (
            patch.object(todoist.todo_base, "_load_todoist_token", return_value="token"),
            patch.object(todoist, "_todoist_sync_command", side_effect=successful_sync) as sync_call,
            redirect_stdout(io.StringIO()) as output,
        ):
            todoist.command_clear_due(args)

        self.assertEqual(sync_call.call_args.args[0], "token")
        command = sync_call.call_args.args[1]
        self.assertEqual(command["type"], "item_update")
        self.assertEqual(command["args"], {"id": "child-1", "due": None})
        self.assertIn('"cleared_due": true', output.getvalue())

    def test_clear_due_rejects_failed_sync_command(self):
        """Fails if Todoist rejects clearing the due date but the CLI reports success."""
        args = argparse.Namespace(task_id="child-1")

        with (
            patch.object(todoist.todo_base, "_load_todoist_token", return_value="token"),
            patch.object(todoist, "_todoist_sync_command", side_effect=RuntimeError("Todoist rejected command")),
        ):
            with self.assertRaisesRegex(RuntimeError, "rejected"):
                todoist.command_clear_due(args)


if __name__ == "__main__":
    unittest.main()
