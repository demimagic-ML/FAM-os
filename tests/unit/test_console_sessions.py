import unittest
from unittest.mock import patch

from fam_os.console.sessions import ConsoleSessionStore
from fam_os.core.admission import RequestIdentity


class ConsoleSessionStoreTests(unittest.TestCase):
    def test_session_identity_remains_valid_when_random_token_starts_with_symbol(self):
        store = ConsoleSessionStore("b" * 32)

        with patch(
            "fam_os.console.sessions.secrets.token_urlsafe",
            side_effect=("_leading-session-token", "-leading-csrf-token"),
        ):
            session = store.exchange("b" * 32)

        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.session_id, "console-_leading-session-token")
        self.assertIs(store.authenticate(session.session_id), session)
        RequestIdentity("local-owner", session.session_id, "authority-1")


if __name__ == "__main__":
    unittest.main()
