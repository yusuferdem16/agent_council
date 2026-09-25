from types import SimpleNamespace

from google.adk.events.event_actions import EventActions
from google.adk.tools import exit_loop


def test_exit_loop_sets_escalate_and_skip_summarization():
    fake_tool_context = SimpleNamespace(actions=EventActions())

    exit_loop(fake_tool_context)

    assert fake_tool_context.actions.escalate is True
    assert fake_tool_context.actions.skip_summarization is True
