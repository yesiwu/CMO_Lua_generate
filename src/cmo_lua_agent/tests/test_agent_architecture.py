from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_strategy_llm_decision_implementations_live_in_flat_agents_package() -> None:
    expected = {
        "strategy_proposal_agent.py",
        "strategy_intent_agent.py",
        "strategy_patch_agent.py",
    }
    actual = {path.name for path in (PACKAGE_ROOT / "agents").glob("*.py")}

    assert expected <= actual
    assert not (PACKAGE_ROOT / "optimization" / "strategy_proposal_agent.py").exists()
    assert not (PACKAGE_ROOT / "optimization" / "candidate_intent_planner.py").exists()
    assert not (PACKAGE_ROOT / "optimization" / "candidate_patch_generator.py").exists()


def test_retired_parallel_orchestrators_and_broken_modules_are_absent() -> None:
    retired = (
        PACKAGE_ROOT / "evolution" / "workflow.py",
        PACKAGE_ROOT / "evolution" / "cli.py",
        PACKAGE_ROOT.parents[1] / "scripts" / "run_phase9_evolution.py",
        PACKAGE_ROOT / "optimization" / "candidate_selector.py",
        PACKAGE_ROOT / "optimization" / "convergence.py",
        PACKAGE_ROOT / "evaluation" / "semantic_validator.py",
        PACKAGE_ROOT / "generation" / "candidate_generator.py",
        PACKAGE_ROOT / "generation" / "strategy_generator.py",
        PACKAGE_ROOT / "generation" / "strategy_spec.py",
        PACKAGE_ROOT / "generation" / "lua_generator.py",
        PACKAGE_ROOT / "generation" / "lua_static_checker.py",
    )

    assert [str(path) for path in retired if path.exists()] == []
