#!/usr/bin/env python3
"""Print the endpoint in config.yaml as shell exports for CodeScribe (OPENAI_COMP_*, MODEL)."""

import os
import re
import shlex
import sys
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def read_config(path):
    """
    Flat view of config.yaml: top-level keys and "section.key" for nested ones
    """
    config, section = {}, ""

    for line in path.read_text().splitlines():
        match = re.match(r"^(\s*)([\w-]+):\s*(.*?)\s*(#.*)?$", line)
        if not match:
            continue

        indent, key, value = match.group(1), match.group(2), match.group(3)
        if not indent:
            section = key if not value else ""
            config[key] = value
        else:
            config[f"{section}.{key}"] = value

    return {
        key: os.path.expandvars(value.strip("\"'")) for key, value in config.items()
    }


def main():
    """
    Print export lines for eval in a shell
    """
    config = read_config(CONFIG)
    model = config.get("agent.loop_model") or config.get("agent.model", "")

    for key in ["OPENAI_COMP_BASEURL", "OPENAI_COMP_APIKEY", "OPENAI_COMP_PROVIDER"]:
        print(f"export {key}={shlex.quote(config.get(key, ''))}")

    print(f"export MODEL={shlex.quote('oaic-' + model)}")


if __name__ == "__main__":
    sys.exit(main())
