#!/usr/bin/env python3
"""Render ECS task definition JSON with immutable image tag."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "Usage: render_taskdef.py <input-json> <output-json> <container-name> <image-uri>",
            file=sys.stderr,
        )
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    container_name = sys.argv[3]
    image_uri = sys.argv[4]

    task = json.loads(input_path.read_text(encoding="utf-8"))
    containers = task.get("containerDefinitions", [])
    changed = False

    for container in containers:
        if container.get("name") == container_name:
            container["image"] = image_uri
            changed = True
            break

    if not changed:
        print(f"Container '{container_name}' not found in task definition.", file=sys.stderr)
        return 1

    for key in (
        "taskDefinitionArn",
        "revision",
        "status",
        "requiresAttributes",
        "compatibilities",
        "registeredAt",
        "registeredBy",
        "deregisteredAt",
        "tags",
    ):
        task.pop(key, None)

    output_path.write_text(json.dumps(task, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
