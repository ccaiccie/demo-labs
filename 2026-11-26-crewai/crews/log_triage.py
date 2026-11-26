"""Three-agent syslog triage crew over the local log fixtures.

Each log is collected by a fresh Crew so prior device context cannot leak
into the next file. Analysis and writing run as a second crew over those
per-device bullets.
"""

from __future__ import annotations

import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from crewai import Agent, Crew, Process, Task

from crews.llm_config import local_llm
from tools.log_tools import list_knowledge_files, read_knowledge_file, read_log_file

OUTPUT = Path("outputs") / "log-triage-report.md"

COLLECT_SPECS = [
    {
        "filename": "core-sw1.log",
        "must": ["192.0.2.19", "FULL"],
        "hint": (
            "Include any OSPF adjacency change and whether neighbor 192.0.2.19 "
            "recovered to FULL, if those lines are present."
        ),
    },
    {
        "filename": "edge-fw1.log",
        "must": ["198.51.100.66", "denied"],
        "hint": (
            "Include any SSH deny burst (source, target, approximate count of "
            "'Login denied' lines) and whether a later login succeeded from a "
            "different source, if those lines are present."
        ),
    },
    {
        "filename": "access-sw2.log",
        "must": ["00:11:22:33:44:61", "Gi1/0/12"],
        "hint": (
            "Include any MAC flaps with the MAC, VLAN, and both ports, "
            "if those lines are present."
        ),
    },
]


def _collect(filename: str, hint: str) -> str:
    llm = local_llm()
    agent = Agent(
        role=f"Collector for {filename}",
        goal=f"Read only {filename} and extract that device's events as compact bullets.",
        backstory="You are a careful NOC collector. You never invent entries and you never mention other devices.",
        llm=llm,
        tools=[read_log_file],
        max_iter=3,
        verbose=True,
        allow_delegation=False,
    )
    task = Task(
        description=(
            f"Call read_log_file exactly once with filename {filename}. Do not read any other file. "
            f"Write a heading `## {filename}` and compact bullets of events from THAT file only. "
            "If a line is not in this file, omit it. "
            f"{hint} "
            "Use only names, addresses, and MACs that appear in this file."
        ),
        expected_output=f"A `## {filename}` section with compact, accurate bullets from that file only.",
        agent=agent,
    )
    result = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
        memory=False,
    ).kickoff()
    return str(result).strip()


def _looks_valid(text: str, must: list[str]) -> bool:
    lowered = text.lower()
    return all(token.lower() in lowered for token in must)


def collect_all() -> dict[str, str]:
    sections: dict[str, str] = {}
    for spec in COLLECT_SPECS:
        filename = spec["filename"]
        text = _collect(filename, spec["hint"])
        if not _looks_valid(text, spec["must"]):
            print(f"collector miss for {filename}, retrying once", flush=True)
            text = _collect(filename, spec["hint"])
        if not _looks_valid(text, spec["must"]):
            raise SystemExit(
                f"collector for {filename} did not include required facts {spec['must']}:\n{text}"
            )
        sections[filename] = text
        snap = Path("outputs") / "_collector-sections.md"
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(
            "\n\n".join(f"{name}\n{body}" for name, body in sections.items()) + "\n",
            encoding="utf-8",
        )
        print(f"saved collector snapshot ({len(sections)} file(s)) to {snap}", flush=True)
    return sections


def analyze_and_write(sections: dict[str, str]) -> str:
    llm = local_llm()
    analyst = Agent(
        role="Triage analyst",
        goal="Interpret the per-device collector bullets using the local playbook. Do not move findings across devices.",
        backstory="You keep each finding on the device that logged it.",
        llm=llm,
        tools=[list_knowledge_files, read_knowledge_file],
        max_iter=4,
        verbose=True,
        allow_delegation=False,
    )
    writer = Agent(
        role="Incident writer",
        goal="Write a clear triage report a network technician can act on.",
        backstory="You write precise Markdown and you never move a finding to the wrong device.",
        llm=llm,
        tools=[],
        max_iter=3,
        verbose=True,
        allow_delegation=False,
    )
    joined = "\n\n".join(sections[spec["filename"]] for spec in COLLECT_SPECS)
    analyze = Task(
        description=(
            "Call list_knowledge_files once, then read syslog-triage.md and ospf-lab.md once each. "
            "Using ONLY the collector bullets below, assign severity and next checks. "
            "Do not copy an event under a different device heading.\n\n"
            f"{joined}\n\n"
            "Keep OSPF on core-sw1 (recovered bounce is medium, not a standing outage), "
            "SSH denials on edge-fw1 (high), and MAC flaps on access-sw2 (medium or high)."
        ),
        expected_output="Analysis with severity and next checks, findings kept on the correct devices.",
        agent=analyst,
    )
    write = Task(
        description=(
            "Write a Markdown triage report with sections: Summary, Findings, Severity, Recommended next checks. "
            "Findings must include: OSPF recovered on core-sw1 (neighbor 192.0.2.19), "
            "SSH deny burst on edge-fw1 from 198.51.100.66, and MAC flaps on access-sw2 "
            "for 00:11:22:33:44:61 between Gi1/0/12 and Gi1/0/24 on VLAN 20. "
            "Do not wrap the report in a markdown code fence. Do not call tools."
        ),
        expected_output="A complete Markdown triage report with findings on the correct devices.",
        agent=writer,
        context=[analyze],
        output_file=str(OUTPUT),
    )
    result = Crew(
        agents=[analyst, writer],
        tasks=[analyze, write],
        process=Process.sequential,
        verbose=True,
        memory=False,
    ).kickoff()
    return str(result).strip()


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sections = collect_all()
    text = analyze_and_write(sections)
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    OUTPUT.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"wrote {OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
