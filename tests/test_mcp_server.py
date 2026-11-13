"""The MCP server exposes a Novel OS workspace to MCP clients (Claude Code etc.)."""

import json

import anyio
import pytest

pytest.importorskip("mcp")

from mcp.shared.memory import create_connected_server_and_client_session  # noqa: E402

from api.services import ProjectService  # noqa: E402
from core.mcp_server import build_server  # noqa: E402


def _payload(result):
    assert not result.isError, result.content
    if result.structuredContent is not None:
        sc = result.structuredContent
        return sc.get("result", sc)
    return json.loads(result.content[0].text)


def test_mcp_round_trip(tmp_path):
    pid = ProjectService(tmp_path).create_sample_project().id
    server = build_server(tmp_path)

    async def scenario():
        async with create_connected_server_and_client_session(server._mcp_server) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            assert {"list_projects", "get_story_state", "get_chapter", "write_chapter",
                    "run_continuity", "search_codex", "add_codex_entry"} <= names

            projects = _payload(await client.call_tool("list_projects", {}))
            assert [p["id"] for p in projects] == [pid]

            state = _payload(await client.call_tool("get_story_state", {"project_id": pid}))
            assert state.get("characters")

            saved = _payload(await client.call_tool(
                "write_chapter",
                {"project_id": pid, "number": 1, "text": "The frost came early to the orchard."},
            ))
            assert saved["saved"] and saved["word_count"] > 0

            chapter = _payload(await client.call_tool("get_chapter", {"project_id": pid, "number": 1}))
            assert "frost came early" in chapter["final_text"]

            report = _payload(await client.call_tool("run_continuity", {"project_id": pid}))
            assert "findings" in report and isinstance(report["critical"], int)

    anyio.run(scenario)
