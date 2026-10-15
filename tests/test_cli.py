"""Proves the `sechound` umbrella CLI: every subcommand maps to a real module
with a main(), help works, unknown commands fail, and the new tools are wired."""
import importlib

import cli


def test_every_subcommand_resolves_to_a_module_with_main():
    for name, module in cli.SUBCOMMANDS.items():
        mod = importlib.import_module(module)
        assert callable(getattr(mod, "main", None)), f"{name} -> {module} has no main()"


def test_every_subcommand_has_help_text():
    for name in cli.SUBCOMMANDS:
        assert cli.HELP.get(name), f"{name} missing help text"


def test_new_tools_are_wired():
    for verb in ("mcp-probe", "rag-probe", "grounding-gate", "benchmark",
                 "skill-miner", "skill-lint"):
        assert verb in cli.SUBCOMMANDS


def test_help_and_unknown_command(capsys):
    assert cli.main.__module__          # import sanity
    import sys
    old = sys.argv
    try:
        sys.argv = ["sechound", "--help"]
        assert cli.main() == 0
        sys.argv = ["sechound", "no-such-command"]
        assert cli.main() == 2
    finally:
        sys.argv = old
