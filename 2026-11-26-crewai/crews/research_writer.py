"""Researcher + writer crew over the local OSPF lab notes."""

from __future__ import annotations

import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from crewai import Agent, Crew, Process, Task

from crews.llm_config import local_llm
from tools.log_tools import list_knowledge_files, read_knowledge_file

OUTPUT = Path("outputs") / "ospf-brief.md"


def build_crew() -> Crew:
    llm = local_llm()
    researcher = Agent(
        role="Lab researcher",
        goal="Read the local OSPF lab notes once and extract topology, neighbor IDs, and expected failover behavior.",
        backstory="You only use the lab knowledge files. You never invent addresses or interfaces.",
        llm=llm,
        tools=[list_knowledge_files, read_knowledge_file],
        max_iter=5,
        verbose=True,
    )
    writer = Agent(
        role="Brief writer",
        goal="Turn the researcher's notes into a short, accurate OSPF lab brief for network technicians.",
        backstory="You write clearly and only use facts the researcher already collected. You do not call tools.",
        llm=llm,
        tools=[],
        max_iter=3,
        verbose=True,
    )
    research = Task(
        description=(
            "Call list_knowledge_files once. Then call read_knowledge_file exactly once with filename ospf-lab.md. "
            "Do not re-read that file. Extract: devices, interfaces, neighbor/router IDs, documentation prefixes, "
            "and what a recovered OSPF bounce means versus a neighbor that stays down. "
            "Return compact bullets only."
        ),
        expected_output="Compact bullets covering topology, addresses, and expected OSPF recovery behavior.",
        agent=researcher,
    )
    write = Task(
        description=(
            "Using only the researcher's bullets, write a short Markdown brief. "
            "Include a topology section, a 'what good looks like' section, and a 'how to judge an OSPF bounce' section. "
            "Do not call tools. Do not invent facts."
        ),
        expected_output="A Markdown brief suitable to save as ospf-brief.md.",
        agent=writer,
        context=[research],
        output_file=str(OUTPUT),
    )
    return Crew(agents=[researcher, writer], tasks=[research, write], process=Process.sequential, verbose=True)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result = build_crew().kickoff()
    OUTPUT.write_text(str(result).strip() + "\n", encoding="utf-8")
    print(result)
    print(f"wrote {OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
