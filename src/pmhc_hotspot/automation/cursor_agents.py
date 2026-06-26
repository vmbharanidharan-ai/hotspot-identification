"""Dispatch binder-conditioning pipeline phases via the Cursor SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTS_DIR = REPO_ROOT / ".cursor" / "agents"

PHASE_AGENTS = {
    "ingest": "ingest",
    "features": "feature",
    "design-export": "design",
    "design-eval": "eval",
    "gatekeeper": "gatekeeper",
    "orchestrator": "orchestrator",
}


@dataclass
class AgentDispatch:
    phase: str
    agent_name: str
    prompt: str


def _read_agent_instructions(agent_name: str) -> str:
    path = AGENTS_DIR / f"{agent_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Missing agent definition: {path}")
    text = path.read_text()
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3 :].lstrip()
    return text.strip()


def build_phase_prompt(phase: str, *, extra: str = "") -> AgentDispatch:
    agent_name = PHASE_AGENTS.get(phase, "orchestrator")
    instructions = _read_agent_instructions(agent_name)
    body = (
        f"You are running pipeline phase **{phase}** for pmhc-hotspot.\n\n"
        f"{instructions}\n\n"
        "Repo root is the current working directory. "
        "Read `pmhc-hotspot-dev-plan.md` and `configs/*.yaml` before editing.\n"
        "Run tests for any code you change (`pytest tests/ -q`).\n"
    )
    if extra:
        body += f"\nAdditional context:\n{extra}\n"
    return AgentDispatch(phase=phase, agent_name=agent_name, prompt=body)


def run_phase_sdk(
    phase: str,
    *,
    api_key: Optional[str] = None,
    model: str = "composer-2.5",
    extra: str = "",
    stream: bool = False,
) -> str:
    """
    Run one pipeline phase headlessly with the Cursor SDK.

    Requires: pip install cursor-sdk
    Auth: set CURSOR_API_KEY (https://cursor.com/dashboard → Integrations / API keys)
    """
    key = api_key or os.environ.get("CURSOR_API_KEY")
    if not key:
        raise RuntimeError(
            "CURSOR_API_KEY is required for SDK agents. "
            "Create one at https://cursor.com/dashboard — IDE subagents do not need this."
        )

    try:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
    except ImportError as exc:
        raise RuntimeError("Install the SDK: pip install cursor-sdk") from exc

    dispatch = build_phase_prompt(phase, extra=extra)
    options = AgentOptions(
        api_key=key,
        model=model,
        local=LocalAgentOptions(cwd=str(REPO_ROOT)),
    )

    if stream:
        with Agent.create(options) as agent:
            run = agent.send(dispatch.prompt)
            chunks: list[str] = []
            for event in run.stream():
                if event.type == "assistant":
                    for block in event.message.content:
                        if block.type == "text":
                            chunks.append(block.text)
            return "".join(chunks)

    result = Agent.prompt(dispatch.prompt, options)
    return str(getattr(result, "result", result))


def run_cycle_sdk(
    phases: Iterable[str],
    *,
    api_key: Optional[str] = None,
    model: str = "composer-2.5",
) -> list[tuple[str, str]]:
    """Run multiple phases sequentially (orchestrator last if included)."""
    outputs: list[tuple[str, str]] = []
    for phase in phases:
        text = run_phase_sdk(phase, api_key=api_key, model=model, stream=True)
        outputs.append((phase, text))
    return outputs
