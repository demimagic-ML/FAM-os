from __future__ import annotations

import unittest

from fam_os.product.owner_identity import local_owner_id


class LocalOwnerIdentityTests(unittest.TestCase):
    def test_uid_is_the_canonical_decimal_owner_identifier(self) -> None:
        self.assertEqual(local_owner_id(1000), "1000")

    def test_negative_uid_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            local_owner_id(-1)

    def test_bool_and_non_integer_uid_are_rejected(self) -> None:
        for value in (True, "1000", 1000.0, None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, "must be an integer"):
                    local_owner_id(value)  # type: ignore[arg-type]
