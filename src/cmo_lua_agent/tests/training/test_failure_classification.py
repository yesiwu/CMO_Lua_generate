from __future__ import annotations

from cmo_lua_agent.training.failures import FailureClassifier, FailureKind


def test_failure_classifier_distinguishes_input_code_and_transient_failures() -> None:
    classifier = FailureClassifier()

    assert classifier.classify(FileNotFoundError("scenario.json")).kind is FailureKind.INPUT
    assert classifier.classify(TimeoutError("CMO timeout")).kind is FailureKind.TRANSIENT
    assert classifier.classify(ImportError("cannot import name Runner")).kind is FailureKind.CODE
    assert classifier.classify(ValueError("candidate semantic validation failed")).kind is FailureKind.BUSINESS


def test_failure_classifier_treats_provider_connection_errors_as_transient() -> None:
    class APIConnectionError(Exception):
        pass

    assert FailureClassifier().classify(APIConnectionError("Connection error.")).kind is FailureKind.TRANSIENT


def test_failure_classifier_retries_a_temporarily_locked_worker_state_file() -> None:
    error = PermissionError(
        13,
        "Permission denied",
        r"D:\\project\\runs\\evolution\\campaign\\workers\\g000_phase6.json",
    )

    assert FailureClassifier().classify(error).kind is FailureKind.TRANSIENT
