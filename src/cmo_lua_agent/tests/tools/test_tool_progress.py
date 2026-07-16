from __future__ import annotations

import pytest

from cmo_lua_agent.tools.tool_base.progress import ToolProgressReporter


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_type", "unknown"),
        ("status", "unknown"),
        ("progress", -0.1),
        ("progress", 1.1),
    ],
)
def test_reporter_rejects_invalid_protocol_values(field: str, value: object) -> None:
    reporter = ToolProgressReporter(tool_use_id="tool-1", tool_name="test")
    arguments = {
        "event_type": "output",
        "status": "running",
        "message": "message",
        field: value,
    }

    with pytest.raises(ValueError):
        reporter.emit(**arguments)


def test_reporter_copies_metadata_and_isolates_callback_failure() -> None:
    metadata = {"pulse": 1}
    events = []
    reporter = ToolProgressReporter(
        tool_use_id="tool-1",
        tool_name="test",
        callback=events.append,
    )

    reporter.output("running", metadata=metadata)
    metadata["pulse"] = 2
    assert events[0].metadata == {"pulse": 1}

    failing_reporter = ToolProgressReporter(
        tool_use_id="tool-1",
        tool_name="test",
        callback=lambda event: (_ for _ in ()).throw(RuntimeError("display failed")),
    )
    failing_reporter.output("still running")
