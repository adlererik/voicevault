#!/usr/bin/env python3
"""Call the local KiCad MCP copper-acceptance tool; no remote service or upload."""
import argparse
import asyncio
import json
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[2]
async def main():
    p=argparse.ArgumentParser();p.add_argument('qualification',type=Path);args=p.parse_args()
    async with stdio_client(StdioServerParameters(command=str(ROOT/'hardware/mcp'),args=[])) as (read,write):
        async with ClientSession(read,write) as client:
            await client.initialize()
            result=await client.call_tool('accept_qualified_copper',{'qualification_path':str(args.qualification.resolve())})
            if result.isError:raise RuntimeError(result.model_dump_json(exclude_none=True))
            print(result.model_dump_json(exclude_none=True))

if __name__=='__main__':asyncio.run(main())
