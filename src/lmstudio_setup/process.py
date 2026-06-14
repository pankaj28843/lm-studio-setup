from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    args: Sequence[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def combined_output(self) -> str:
        return "".join(part for part in (self.stdout, self.stderr) if part)


async def run_command(
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    capture: bool = True,
    check: bool = False,
    input_text: str | None = None,
) -> CommandResult:
    stdin = asyncio.subprocess.PIPE if input_text is not None else None
    stdout = asyncio.subprocess.PIPE if capture else None
    stderr = asyncio.subprocess.PIPE if capture else None
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        env=dict(env) if env is not None else None,
    )
    raw_stdout, raw_stderr = await process.communicate(
        input_text.encode() if input_text is not None else None
    )
    result = CommandResult(
        args=args,
        returncode=process.returncode,
        stdout=(raw_stdout or b"").decode(errors="replace"),
        stderr=(raw_stderr or b"").decode(errors="replace"),
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed with exit {result.returncode}: {' '.join(args)}\n"
            f"{result.combined_output}"
        )
    return result
