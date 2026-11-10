#!/usr/bin/env python3
"""MCP server (stdio, JSON-RPC 2.0, stdlib only) exposing DeepSeek as a tool.

Tool: ask_deepseek(prompt: str, system_prompt?: str) -> str
Env:
  DEEPSEEK_API_KEY   required
  DEEPSEEK_MODEL     default: deepseek-chat
  DEEPSEEK_BASE_URL  default: https://api.deepseek.com
  DEEPSEEK_TIMEOUT   seconds, default: 300
"""
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

PROTOCOL_VERSION = "2024-11-05"
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
API_URL = BASE_URL + "/chat/completions"
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
TIMEOUT = int(os.environ.get("DEEPSEEK_TIMEOUT", "300"))

TOOLS = [
    {
        "name": "ask_deepseek",
        "description": (
            "Send a task to DeepSeek (deepseek-chat) and return its text answer. "
            "Best for code writing and implementation. Stateless: the prompt must "
            "contain all the context DeepSeek needs (DeepSeek cannot read files)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The task or user message for DeepSeek.",
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional system instructions (role, conventions, constraints).",
                },
            },
            "required": ["prompt"],
        },
    }
]

_write_lock = threading.Lock()


def send(msg):
    with _write_lock:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def ok(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def err(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def call_deepseek(prompt, system_prompt=None):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set in the environment")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    body = json.dumps({"model": MODEL, "messages": messages, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"DeepSeek HTTP {e.code}: {detail}")

    return data["choices"][0]["message"]["content"]


def handle_tools_call(rid, params):
    name = params.get("name")
    args = params.get("arguments") or {}
    if name != "ask_deepseek":
        return err(rid, -32602, f"Unknown tool: {name}")

    prompt = args.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return err(rid, -32602, "Argument 'prompt' is required and must be a non-empty string")

    system_prompt = args.get("system_prompt")
    if system_prompt is not None and not isinstance(system_prompt, str):
        return err(rid, -32602, "Argument 'system_prompt' must be a string")

    try:
        text = call_deepseek(prompt, system_prompt)
        return ok(rid, {"content": [{"type": "text", "text": text}], "isError": False})
    except Exception as e:  # report as tool error, keep server alive
        return ok(rid, {"content": [{"type": "text", "text": f"DeepSeek error: {e}"}], "isError": True})


def handle(req):
    method = req.get("method")
    params = req.get("params") or {}
    rid = req.get("id")

    if method == "initialize":
        return ok(rid, {
            "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "deepseek", "version": "1.0.0"},
        })
    if method == "ping":
        return ok(rid, {})
    if method == "tools/list":
        return ok(rid, {"tools": TOOLS})
    if method == "tools/call":
        return handle_tools_call(rid, params)
    return err(rid, -32601, f"Method not found: {method}")


def main():
    # Tool calls run in a pool so parallel subagent calls don't queue behind each other.
    pool = ThreadPoolExecutor(max_workers=8)

    def run(req):
        resp = handle(req)
        if resp is not None:
            send(resp)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            send(err(None, -32700, "Parse error"))
            continue

        if "id" not in req:  # notification (e.g. notifications/initialized): no reply
            continue

        if req.get("method") == "tools/call":
            pool.submit(run, req)
        else:
            run(req)

    pool.shutdown(wait=True)


if __name__ == "__main__":
    main()
