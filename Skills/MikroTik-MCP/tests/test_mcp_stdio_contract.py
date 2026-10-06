from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def test_stdio_mcp_contract(tmp_path) -> None:
    profiles = tmp_path / "MikroTikSkill" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "lab.json").write_text(
        json.dumps(
            {
                "name": "lab",
                "host": "192.0.2.1",
                "port": 22,
                "username": "readonly",
                "default_interface": "ether1",
            }
        ),
        encoding="utf-8",
    )

    async def run() -> None:
        env = dict(os.environ)
        env["APPDATA"] = str(tmp_path)

        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mikrotik_skill.mcp_server"],
            env=env,
        )

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                assert names == {
                    "mikrotik_devices",
                    "mikrotik_status",
                    "mikrotik_inventory",
                    "mikrotik_torch_flows",
                    "mikrotik_full",
                }

                status_tool = next(
                    tool for tool in tools.tools
                    if tool.name == "mikrotik_status"
                )
                assert status_tool.annotations is not None
                assert status_tool.annotations.read_only_hint is True

                devices = await session.call_tool(
                    "mikrotik_devices",
                    {},
                )
                assert devices.is_error is False
                assert devices.structured_content is not None
                assert devices.structured_content["device_count"] == 1
                assert devices.structured_content["devices"][0]["device"] == "lab"

                invalid = await session.call_tool(
                    "mikrotik_status",
                    {
                        "device": "invalid profile name",
                        "section": "health",
                    },
                )
                assert invalid.is_error is True

    asyncio.run(run())
