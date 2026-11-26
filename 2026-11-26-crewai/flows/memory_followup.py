"""Write a follow-up from outputs/ticket-memory.md after the severity Flow has run."""

from __future__ import annotations

import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from crewai import Agent, Crew, Process, Task

from crews.llm_config import local_llm

MEMORY = Path("outputs") / "ticket-memory.md"
OUTPUT = Path("outputs") / "memory-followup.md"


def main() -> None:
    if not MEMORY.is_file():
        raise SystemExit(f"missing {MEMORY}; run flows/severity_flow.py first")
    memory = MEMORY.read_text(encoding="utf-8")
    llm = local_llm()
    agent = Agent(
        role="Follow-up engineer",
        goal="Turn ticket memory into a short, actionable follow-up. Do not invent new facts.",
        backstory="You only use the ticket memory text you are given.",
        llm=llm,
        tools=[],
        max_iter=3,
        verbose=True,
    )
    task = Task(
        description=(
            "Using only this ticket memory, write a Markdown follow-up with sections: "
            "Open item, Evidence already on file, Next checks, Suggested close criteria.\n\n"
            f"{memory}\n"
            "Do not call tools. Do not invent IPs, users, or counts that are not in the memory."
        ),
        expected_output="A short Markdown follow-up.",
        agent=agent,
        output_file=str(OUTPUT),
    )
    result = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True).kickoff()
    OUTPUT.write_text(str(result).strip() + "\n", encoding="utf-8")
    print(result)
    print(f"wrote {OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
