"""Concise standalone FAM launcher for Omarchy and ordinary Linux desktops."""

from __future__ import annotations

import sys

from fam_os.product.cli import main as fam_os_main


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        return fam_os_main(["agent", "--interactive", "--source", "fam-tui"])
    if arguments[0] == "console":
        return fam_os_main(["console", *arguments[1:]])
    if arguments[0] in {"tui", "chat"}:
        return fam_os_main([
            "agent", "--interactive", "--source", "fam-tui", *arguments[1:],
        ])
    if arguments[0] == "goal":
        if len(arguments) == 1:
            return fam_os_main([
                "agent", "--interactive", "--goal", "--source", "fam-goal-tui",
            ])
        return fam_os_main(["agent", "--goal", *arguments[1:]])
    if arguments[0] == "agent":
        return fam_os_main(["agent", *arguments[1:]])
    return fam_os_main(["agent", *arguments])


if __name__ == "__main__":
    raise SystemExit(main())
