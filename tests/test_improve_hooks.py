import json

from agentops.core.memory import FailureMode
from agentops.improve.hooks import derive_hook_proposals
from agentops.memory.candidates import RECURRENCE_THRESHOLD
from agentops.memory.failure_modes import CONFIRMED_DRIFT


def _mode(
    code: str,
    occurrence_count: int = RECURRENCE_THRESHOLD,
    *,
    hot_paths: tuple[str, ...] = (),
) -> FailureMode:
    return FailureMode(
        code=code,
        occurrence_count=occurrence_count,
        sample_count=4,
        hot_paths=hot_paths,
        last_seen="2026-06-06T00:00:00Z",
        summary="s",
    )


def test_sub_threshold_modes_produce_nothing() -> None:
    modes = (_mode("undeclared_change", RECURRENCE_THRESHOLD - 1),)

    assert derive_hook_proposals(modes) == ()


def test_empty_input_produces_empty() -> None:
    assert derive_hook_proposals(()) == ()


def test_unknown_code_is_ignored() -> None:
    modes = (_mode("intent_alignment", 5),)

    assert derive_hook_proposals(modes) == ()


def test_scope_failure_modes_use_eval_proposal() -> None:
    modes = (
        _mode("undeclared_change", 3, hot_paths=("src/a.py",)),
        _mode("cross_module_breadth", 2, hot_paths=("src",)),
    )
    proposals = derive_hook_proposals(modes)

    assert {p.command for p in proposals} == {"agentops eval --repo ."}
    assert all(p.event == "Stop" for p in proposals)


def test_all_scope_failure_modes_collapse_into_one_eval_proposal() -> None:
    modes = (
        _mode("undeclared_change", 3, hot_paths=("src/a.py",)),
        _mode("declared_not_changed", 2, hot_paths=("src/b.py",)),
        _mode("cross_module_breadth", 3, hot_paths=("src",)),
        _mode(CONFIRMED_DRIFT, 2, hot_paths=("src/auth.py",)),
    )
    proposals = derive_hook_proposals(modes)

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.command == "agentops eval --repo ."
    assert set(proposal.failure_codes) == {
        "undeclared_change",
        "declared_not_changed",
        "cross_module_breadth",
        CONFIRMED_DRIFT,
    }


def test_cross_module_and_confirmed_drift_collapse_into_eval_proposal() -> None:
    modes = (
        _mode("cross_module_breadth", 3, hot_paths=("src",)),
        _mode(CONFIRMED_DRIFT, 2, hot_paths=("src/auth.py",)),
    )
    proposals = derive_hook_proposals(modes)

    eval_proposals = [p for p in proposals if p.command == "agentops eval --repo ."]
    assert len(eval_proposals) == 1
    assert set(eval_proposals[0].failure_codes) == {
        "cross_module_breadth",
        CONFIRMED_DRIFT,
    }


def test_settings_snippet_is_valid_json_with_command() -> None:
    proposals = derive_hook_proposals((_mode("undeclared_change", 3),))
    parsed = json.loads(proposals[0].settings_snippet)

    assert "Stop" in parsed["hooks"]
    inner = parsed["hooks"]["Stop"][0]["hooks"][0]
    assert inner == {
        "type": "command",
        "command": "agentops eval --repo .",
    }


def test_output_order_is_deterministic() -> None:
    modes = (
        _mode("cross_module_breadth", 3),
        _mode("undeclared_change", 2),
    )
    first = derive_hook_proposals(modes)
    second = derive_hook_proposals(modes)

    assert [p.slug for p in first] == [p.slug for p in second]
    assert [p.command for p in first] == ["agentops eval --repo ."]


def test_slug_is_stable_for_event_command() -> None:
    proposals = derive_hook_proposals((_mode("cross_module_breadth", 3),))

    assert proposals[0].slug == "eval-stop-hook"
