"""Canonical identities for resources owned by the local operating-system user."""

from __future__ import annotations


def local_owner_id(uid: int) -> str:
    """Return the product-wide durable owner identifier for one Unix UID."""
    if isinstance(uid, bool) or not isinstance(uid, int):
        raise TypeError("local owner UID must be an integer")
    if uid < 0:
        raise ValueError("local owner UID cannot be negative")
    return str(uid)
