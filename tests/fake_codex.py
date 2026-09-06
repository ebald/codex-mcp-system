#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys


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

for raw_line in sys.stdin:
    request = json.loads(raw_line)
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})
    if request_id is None:
        continue
    if method == "initialize":
        send({"id": request_id, "result": {"userAgent": "fake-app-server"}})
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
        send({"id": request_id, "result": {"value": params.get("value")}})
    elif method == "thread/start":
        send({"id": request_id, "result": {"thread": {"id": "thr_fake"}}})
    elif method == "turn/start":
        send({"id": request_id, "result": {"turn": {"id": "turn_fake"}}})
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr_fake",
                    "turnId": "turn_fake",
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
                        "threadId": "thr_fake",
                        "turnId": "turn_fake",
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
                        "threadId": "thr_fake",
                        "turn": {"id": "turn_fake", "status": "completed", "items": []},
                    },
                }
            )
        elif turn_mode == "failed":
            send(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thr_fake",
                        "turn": {
                            "id": "turn_fake",
                            "status": "failed",
                            "items": [],
                            "error": {"message": "policy refusal"},
                        },
                    },
                }
            )
    elif method == "turn/interrupt":
        send({"id": request_id, "result": {}})
    else:
        send({"id": request_id, "error": {"code": -32601, "message": "unknown"}})
