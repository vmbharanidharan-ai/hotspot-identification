"""Launch Cursor SDK agents in parallel (separate Agent.create per role)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from pmhc_hotspot.automation.overnight import build_agent_prompt
from pmhc_hotspot.automation.paths import AGENT_OUTPUTS_DIR, AGENTS_DIR, REPO_ROOT

ROLE_FILES = {
    "analyst": "analyst.md",
    "biology_reviewer": "biology-reviewer.md",
    "patcher": "patcher.md",
    "reviewer": "reviewer.md",
}

DEFAULT_MODEL = os.environ.get("PMHC_AGENT_MODEL", "composer-2.5")


def sdk_available() -> bool:
    try:
        import cursor_sdk  # noqa: F401

        return bool(os.environ.get("CURSOR_API_KEY"))
    except ImportError:
        return False


def role_prompt(role: str, *, extra: str = "") -> str:
    filename = ROLE_FILES[role]
    path = AGENTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing subagent file: {path}")
    return build_agent_prompt(filename, extra=extra)


def run_sdk_agent(role: str, prompt: str) -> dict:
    """One isolated Cursor SDK agent (own Agent.create lifecycle)."""
    AGENT_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AGENT_OUTPUTS_DIR / f"{role}.txt"

    from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

    api_key = os.environ["CURSOR_API_KEY"]
    try:
        with Agent.create(
            AgentOptions(
                api_key=api_key,
                model=DEFAULT_MODEL,
                local=LocalAgentOptions(cwd=str(REPO_ROOT)),
            ),
        ) as agent:
            run = agent.send(prompt)
            run.wait()
            text = run.text() if hasattr(run, "text") else ""
            if not text:
                result = run.wait()
                text = getattr(result, "result", "") or str(result)
            out_path.write_text(text or "")
            return {
                "role": role,
                "status": "ok",
                "output_path": str(out_path),
                "text_preview": (text or "")[:500],
            }
    except Exception as exc:
        return {"role": role, "status": "error", "error": str(exc)}


def launch_parallel(roles: list[str], *, extra_by_role: dict[str, str] | None = None) -> list[dict]:
    extra_by_role = extra_by_role or {}
    prompts = {role: role_prompt(role, extra=extra_by_role.get(role, "")) for role in roles}
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, len(roles))) as pool:
        futures = {pool.submit(run_sdk_agent, role, prompts[role]): role for role in roles}
        for future in as_completed(futures):
            results.append(future.result())
    return results
