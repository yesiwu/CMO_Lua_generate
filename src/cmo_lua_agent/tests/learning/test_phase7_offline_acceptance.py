from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cmo_lua_agent.agents.comparative_learning_agent import ComparativeLearningAgent
from cmo_lua_agent.learning.builders import CandidateLearningViewBuilder
from cmo_lua_agent.learning.store import ExperienceStore
from cmo_lua_agent.learning.workflow import GenerationLearningWorkflow
from cmo_lua_agent.llm.json_client import ClaudeJsonClient, JsonCompletionError


class _MessageClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def create_message(self, **_: object) -> object:
        self.calls += 1
        return type("Message", (), {"content": [type("Text", (), {"text": self.text})()]})()


def test_claude_json_client_accepts_a_single_json_object() -> None:
    client = _MessageClient('{"answer": 1}')

    assert ClaudeJsonClient(client).complete_json(system="system", prompt="prompt") == {"answer": 1}
    assert client.calls == 1


def test_claude_json_client_accepts_one_isolated_json_fence() -> None:
    client = _MessageClient("```json\n{\"answer\": 1}\n```")

    assert ClaudeJsonClient(client).complete_json(system="system", prompt="prompt") == {"answer": 1}


def test_claude_json_client_rejects_trailing_text_with_restricted_diagnostics() -> None:
    with pytest.raises(JsonCompletionError) as raised:
        ClaudeJsonClient(_MessageClient("```json\n{\"answer\": 1}\n```\nextra")).complete_json(
            system="system", prompt="prompt"
        )

    assert raised.value.code == "proposal_json_invalid"
    assert raised.value.diagnostics["has_markdown_fence"] is True
    assert raised.value.diagnostics["has_trailing_text"] is True
    assert "response" not in raised.value.diagnostics


def test_claude_json_client_marks_raw_json_trailing_text() -> None:
    with pytest.raises(JsonCompletionError) as raised:
        ClaudeJsonClient(_MessageClient('{"answer": 1} extra')).complete_json(
            system="system", prompt="prompt"
        )

    assert raised.value.diagnostics["has_trailing_text"] is True


@pytest.mark.parametrize("text", ["", "prefix {\"answer\": 1}", "[]"])
def test_claude_json_client_rejects_non_single_json_object(text: str) -> None:
    with pytest.raises(ValueError):
        ClaudeJsonClient(_MessageClient(text)).complete_json(system="system", prompt="prompt")


def test_learning_view_never_falls_back_to_outcome_native_score(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidate_00"
    (candidate_dir / "attempts" / "attempt_00").mkdir(parents=True)
    (candidate_dir / "strategy").mkdir()
    (candidate_dir / "candidate_outcome.json").write_text(
        json.dumps({"candidate_id": "candidate_00", "native_score": 260, "scoreable": True}),
        encoding="utf-8",
    )
    (candidate_dir / "strategy" / "final_strategy.json").write_text("{}", encoding="utf-8")

    view = CandidateLearningViewBuilder().build(candidate_dir=candidate_dir, is_baseline=False)

    assert view.official_score is None
    assert view.score_source is None
    assert view.scoreable is False
    assert view.execution_fidelity == "failed"


def test_workflow_replay_reuses_saved_response_without_second_llm_call(tmp_path: Path) -> None:
    root = _write_minimal_optimization(tmp_path / "optimization")
    response = {
        "analysis": {
            "observed_strategy_differences": [],
            "observed_execution_differences": [],
            "observed_outcome_differences": [],
            "evidence_limitations": ["no official score summary"],
            "possible_random_factors": [],
            "next_testable_hypotheses": [],
        },
        "proposals": [],
    }
    class _JsonClient:
        calls = 0
        def complete_json(self, **_: object) -> object:
            self.calls += 1
            return response

    json_client = _JsonClient()
    workflow = GenerationLearningWorkflow(
        agent=ComparativeLearningAgent(json_client),
        store=ExperienceStore(tmp_path / "experiences"),
    )

    _, first = workflow.run(root)
    _, replay = workflow.run(root, reuse_saved_response=True)

    assert first == replay == ()
    assert json_client.calls == 1
    assert (root / "learning" / "candidate-learning-views.json").is_file()
    assert (root / "learning" / "generation-learning-bundle.json").is_file()
    assert (root / "learning" / "comparative-analysis.json").is_file()
    assert (root / "learning" / "experience-candidates.json").is_file()
    comparisons = json.loads((root / "learning" / "candidate-comparisons.json").read_text(encoding="utf-8"))
    assert [row["candidate_id"] for row in comparisons] == ["candidate_00"]


def test_workflow_calls_llm_once_per_candidate_against_the_baseline(tmp_path: Path) -> None:
    root = _write_minimal_optimization(tmp_path / "optimization")
    generation_result = json.loads((root / "generation_result.json").read_text(encoding="utf-8"))
    candidate_paths = generation_result["candidate_outcome_paths"]
    for index in range(1, 4):
        candidate = root / "generation_00" / f"candidate_0{index}"
        (candidate / "attempts" / "attempt_00").mkdir(parents=True)
        (candidate / "strategy").mkdir()
        (candidate / "candidate_outcome.json").write_text(
            json.dumps({"candidate_id": f"candidate_0{index}", "scoreable": False, "semantic_valid": False}),
            encoding="utf-8",
        )
        (candidate / "strategy" / "final_strategy.json").write_text("{}", encoding="utf-8")
        candidate_paths.append(str(candidate / "candidate_outcome.json"))
    (root / "generation_result.json").write_text(json.dumps(generation_result), encoding="utf-8")
    diffs = {f"candidate_0{index}": [] for index in range(4)}
    (root / "strategy_diff.json").write_text(json.dumps(diffs), encoding="utf-8")

    response = {"analysis": {field: [] for field in (
        "observed_strategy_differences", "observed_execution_differences", "observed_outcome_differences",
        "evidence_limitations", "possible_random_factors", "next_testable_hypotheses",
    )}, "proposals": []}
    class _JsonClient:
        calls = 0
        def complete_json(self, **_: object) -> object:
            self.calls += 1
            return response

    client = _JsonClient()
    GenerationLearningWorkflow(
        agent=ComparativeLearningAgent(client), store=ExperienceStore(tmp_path / "experiences"),
    ).run(root)

    comparisons = json.loads((root / "learning" / "candidate-comparisons.json").read_text(encoding="utf-8"))
    assert client.calls == 4
    assert [row["candidate_id"] for row in comparisons] == [f"candidate_0{index}" for index in range(4)]


def test_phase7_offline_entrypoint_is_explicit_and_never_mentions_cmo_execution() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/run_phase7_learning.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "optimization_dir" in completed.stdout
    assert "CMO" not in completed.stdout


def _write_minimal_optimization(root: Path) -> Path:
    root.mkdir(parents=True)
    baseline = root / "baseline" / "candidate_baseline"
    candidate = root / "generation_00" / "candidate_00"
    for directory, candidate_id in ((baseline, "baseline"), (candidate, "candidate_00")):
        (directory / "attempts" / "attempt_00").mkdir(parents=True)
        (directory / "strategy").mkdir()
        (directory / "candidate_outcome.json").write_text(
            json.dumps({"candidate_id": candidate_id, "scoreable": False, "semantic_valid": False}),
            encoding="utf-8",
        )
        (directory / "strategy" / "final_strategy.json").write_text("{}", encoding="utf-8")
    (root / "generation_result.json").write_text(
        json.dumps({
            "optimization_id": "offline_acceptance",
            "baseline_outcome_path": str(baseline / "candidate_outcome.json"),
            "candidate_outcome_paths": [str(candidate / "candidate_outcome.json")],
        }),
        encoding="utf-8",
    )
    (root / "strategy_diff.json").write_text(json.dumps({"candidate_00": ["/attacks/0/fire_quantity"]}), encoding="utf-8")
    (root / "leaderboard.json").write_text("[]", encoding="utf-8")
    return root
