from __future__ import annotations

import os
import re
from pathlib import Path


def ensure_root_key(config_file: Path, key: str, value: str) -> None:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    lines = config_file.read_text().splitlines(keepends=True) if config_file.exists() else []

    key_pattern = re.compile(rf"^[ \t]*{re.escape(key)}[ \t]*=")
    table_index = next(
        (index for index, line in enumerate(lines) if line.lstrip().startswith("[")),
        None,
    )

    output: list[str] = []
    wrote_key = False
    for index, line in enumerate(lines):
        in_root = table_index is None or index < table_index
        if in_root and key_pattern.match(line):
            if not wrote_key:
                output.append(f"{key} = {value}\n")
                wrote_key = True
            continue
        if table_index is not None and index == table_index and not wrote_key:
            output.append(f"{key} = {value}\n\n")
            wrote_key = True
        output.append(line)

    if not wrote_key:
        if output and not output[-1].endswith("\n"):
            output[-1] = f"{output[-1]}\n"
        if output and output[-1].strip():
            output.append("\n")
        output.append(f"{key} = {value}\n")

    tmp_file = config_file.with_suffix(f"{config_file.suffix}.tmp")
    tmp_file.write_text("".join(output))
    os.replace(tmp_file, config_file)
    config_file.chmod(0o600)
