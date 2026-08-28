import unittest

from fam_os.console.widget_routes import handle_widget_post


class _Api:
    def __init__(self):
        self.calls = []

    def open_candidate(self, goal_id):
        self.calls.append(("candidate", goal_id))
        return {"opened": True}

    def execute_command(self, command_id, action, callback, **kwargs):
        self.calls.append(("command", command_id, action, kwargs.get("goal_id")))
        return {**callback(), "commandId": command_id, "accepted": True}


class _Handler:
    def __init__(self):
        self.server = type("Server", (), {"widget_api": _Api()})()
        self.responses = []

    def _widget_authorized(self):
        return True

    def _json(self, status, document):
        self.responses.append((status, document))

    def send_error(self, status):
        self.responses.append((status, None))


class WidgetRouteContractTests(unittest.TestCase):
    def test_stable_candidate_open_route_uses_goal_identity(self):
        handler = _Handler()
        self.assertTrue(handle_widget_post(
            handler, "/api/v1/candidate/open", {
                "commandId": "command-0007", "goalId": "goal-7",
            },
        ))
        self.assertEqual(handler.server.widget_api.calls, [
            ("command", "command-0007", "candidate.open", "goal-7"),
            ("candidate", "goal-7"),
        ])
        self.assertEqual(handler.responses, [(202, {
            "opened": True, "commandId": "command-0007", "accepted": True,
        })])

    def test_candidate_open_rejects_ambiguous_payload(self):
        handler = _Handler()
        with self.assertRaisesRegex(ValueError, "exactly commandId and goalId"):
            handle_widget_post(
                handler, "/api/v1/candidate/open",
                {
                    "commandId": "command-0007", "goalId": "goal-7",
                    "path": "/tmp/not-authoritative",
                },
            )


if __name__ == "__main__":
    unittest.main()
