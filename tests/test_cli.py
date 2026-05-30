from agentops.cli import build_parser


def test_cli_parser_has_program_description() -> None:
    parser = build_parser()

    assert parser.prog == "agentops"
    assert "AI coding" in parser.description
