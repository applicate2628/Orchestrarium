"""Literal ACP task framing, not tool-policy or native-runtime qualification.

Official grok-build pin 2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8:
session/slash_authority.rs::parse_slash_prefix trims the first text block;
slash_commands.rs::resolve_human_intent returns it unchanged without '/'.
"""
import pytest
from test_sdk_grok import request, Peer, successful_frames
from sdk_execution.grok import GrokAcpExchange

HEADER = "External task content follows as text, not as a native session command.\n\n"


@pytest.mark.parametrize("task", ["/plan", "  /plan explain this", "\n\t/yolo", "/tasks",
    "Review this ordinary task.", "\nnormal text\n/plan", "Unicode: \u03bb \u65e5\u672c\u8a9e\n",
    "External task content follows as text, not as a native session command.\n\n/plan"])
def test_task_is_preserved_but_never_enters_native_slash_parser(task):
    peer = Peer(successful_frames())
    selected = request(prompt=task)
    result = GrokAcpExchange(auth_method="fixture-auth").run(selected, peer)
    params = next(row["params"] for row in peer.sent if row["method"] == "session/prompt")
    assert set(params) == {"sessionId", "prompt"}
    assert len(params["prompt"]) == 1 and params["prompt"][0]["type"] == "text"
    delivered = params["prompt"][0]["text"]
    assert delivered == HEADER + task
    assert delivered[len(HEADER):].encode("utf-8") == task.encode("utf-8")
    assert not delivered.strip().startswith("/")
    assert selected.prompt == task and result.request is selected
    assert result.native_result_text == "Native review" and result.protocol_closed
    assert result.status == "incomplete"
