#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time


def send(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    sys.stdout.flush()


if "--version" in sys.argv:
    print("codex-cli 999.0.0-fake")
    raise SystemExit

if "app-server" not in sys.argv:
    raise SystemExit(2)

turn_mode = os.environ.get("FAKE_TURN_MODE", "success")
auth_mode = os.environ.get("FAKE_AUTH_MODE", "chatgpt")
artifact = os.environ.get("FAKE_CODEX_ARTIFACT", "/tmp/fake-image.png")
history: list[str] = []
turn_inputs: list[object] = []
thread_params: list[object] = []
thread_count = 0
turn_count = 0
initialized = False
echoes: list[dict[str, object]] = []

for raw_line in sys.stdin:
    request = json.loads(raw_line)
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})
    history.append(method)
    if method == "initialized":
        initialized = True
    if request_id is None:
        continue
    if method == "initialize":
        time.sleep(float(os.environ.get("FAKE_INIT_DELAY", "0")))
        send({"id": request_id, "result": {"userAgent": "fake-app-server"}})
    elif not initialized:
        send({"id": request_id, "error": {"code": -32000, "message": "not initialized"}})
    elif method == "account/read":
        account = {"type": auth_mode}
        if auth_mode == "chatgpt":
            account.update({"email": "private@example.invalid", "planType": "plus"})
        send(
            {
                "id": request_id,
                "result": {"account": account, "requiresOpenaiAuth": True},
            }
        )
    elif method == "skills/list":
        send(
            {
                "id": request_id,
                "result": {
                    "data": [
                        {
                            "cwd": params.get("cwds", ["."])[0],
                            "skills": [
                                {
                                    "name": "imagegen",
                                    "description": "fake",
                                    "enabled": True,
                                    "path": "/system/imagegen/SKILL.md",
                                    "scope": "system",
                                }
                            ],
                            "errors": [],
                        }
                    ]
                },
            }
        )
    elif method == "debug/env":
        send(
            {
                "id": request_id,
                "result": {"hasOpenAIKey": "OPENAI_API_KEY" in os.environ},
            }
        )
    elif method == "test/echo":
        echoes.append({"id": request_id, "result": {"value": params.get("value")}})
        if len(echoes) == 3:
            for response in reversed(echoes):
                send(response)
            echoes.clear()
    elif method == "test/stats":
        send(
            {
                "id": request_id,
                "result": {"methods": history, "inputs": turn_inputs, "threads": thread_params},
            }
        )
    elif method == "test/set-auth":
        auth_mode = params["authMode"]
        send({"id": request_id, "result": {}})
    elif method == "test/malformed":
        sys.stdout.write("not-json\n")
        sys.stdout.flush()
    elif method == "test/invalid-result":
        send({"id": request_id, "result": []})
    elif method == "thread/start":
        thread_params.append(params)
        thread_count += 1
        thread_id = f"thr_fake_{thread_count}"
        if os.environ.get("FAKE_AUTH_ON_THREAD_START"):
            auth_mode = os.environ["FAKE_AUTH_ON_THREAD_START"]
        send({"id": request_id, "result": {"thread": {"id": thread_id}}})
    elif method == "thread/unsubscribe":
        send({"id": request_id, "result": {"status": "unsubscribed"}})
    elif method == "turn/start":
        turn_count += 1
        turn_id = f"turn_fake_{turn_count}"
        turn_inputs.append(params.get("input"))
        if turn_mode == "lost_start":
            continue
        send({"id": request_id, "result": {"turn": {"id": turn_id}}})
        if turn_mode == "exit_after_start":
            raise SystemExit(0)
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": thread_id,
                    "turnId": turn_id,
                    "completedAtMs": 1,
                    "item": {"id": "user", "type": "userMessage", "content": []},
                },
            }
        )
        if turn_mode == "success":
            send(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": thread_id,
                        "turnId": turn_id,
                        "completedAtMs": 2,
                        "item": {
                            "id": "image",
                            "type": "imageGeneration",
                            "status": "completed",
                            "result": "x" * 70_000,
                            "savedPath": artifact,
                            "revisedPrompt": None,
                            "transparentBackground": False,
                        },
                    },
                }
            )
            send(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": thread_id,
                        "turn": {"id": turn_id, "status": "completed", "items": []},
                    },
                }
            )
        elif turn_mode == "failed":
            send(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": thread_id,
                        "turn": {
                            "id": turn_id,
                            "status": "failed",
                            "items": [],
                            "error": {"message": "policy refusal"},
                        },
                    },
                }
            )
    elif method == "turn/interrupt":
        send({"id": request_id, "result": {}})
        if turn_mode != "interrupt_stuck":
            send(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": params["threadId"],
                        "turn": {"id": params["turnId"], "status": "interrupted", "items": []},
                    },
                }
            )
    else:
        send({"id": request_id, "error": {"code": -32601, "message": "unknown"}})
