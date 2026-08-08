from __future__ import annotations

from cmo_lua_agent.training.failures import FailureClassifier, FailureKind


def test_failure_classifier_distinguishes_input_code_and_transient_failures() -> None:
    classifier = FailureClassifier()

    assert classifier.classify(FileNotFoundError("scenario.json")).kind is FailureKind.INPUT
    assert classifier.classify(TimeoutError("CMO timeout")).kind is FailureKind.TRANSIENT
    assert classifier.classify(ImportError("cannot import name Runner")).kind is FailureKind.CODE
    assert classifier.classify(ValueError("candidate semantic validation failed")).kind is FailureKind.BUSINESS
