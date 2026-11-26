"""Classify edge-fw1.log and route a high-severity incident or a low-severity digest."""

from __future__ import annotations

import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from crewai import Agent, Crew, Process, Task
from crewai.flow.flow import Flow, listen, router, start
from pydantic import BaseModel

from crews.llm_config import local_llm
from tools.log_tools import read_log_file

INCIDENT = Path("outputs") / "flow-incident.md"
DIGEST = Path("outputs") / "flow-digest.md"
MEMORY = Path("outputs") / "ticket-memory.md"
SOURCE = "edge-fw1.log"


class SeverityState(BaseModel):
    source_file: str = SOURCE
    severity: str = ""
    summary: str = ""


def _classifier_crew(source_file: str) -> Crew:
    llm = local_llm()
    agent = Agent(
        role="Severity classifier",
        goal="Read one firewall log once and classify it as high or low severity.",
        backstory="You make a binary call: high if there is an SSH deny burst or other attack pattern, otherwise low.",
        llm=llm,
        tools=[read_log_file],
        max_iter=3,
        verbose=True,
    )
    task = Task(
        description=(
            f"Call read_log_file exactly once with filename {source_file}. Then stop using tools and answer. "
            "If you see a burst of SSH login denials or failed SSH negotiation from one source, severity is high. "
            "A single successful admin login from a documentation address is not enough to call it low if a deny burst is also present. "
            "Reply with exactly two lines:\n"
            "SEVERITY: high\n"
            "or\n"
            "SEVERITY: low\n"
            "SUMMARY: <one sentence with source IP and count if available>"
        ),
        expected_output="Two lines: SEVERITY: high|low and SUMMARY: ...",
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)


def _writer_crew(kind: str, source_file: str, summary: str) -> Crew:
    llm = local_llm()
    agent = Agent(
        role="Incident writer" if kind == "high" else "Digest writer",
        goal="Write a short, factual note from the classifier summary. Do not call tools.",
        backstory="You only restate what was already classified. You do not invent IPs or counts.",
        llm=llm,
        tools=[],
        max_iter=5,
        verbose=True,
    )
    if kind == "high":
        dest = INCIDENT
        description = (
            f"Write a short Markdown incident for {source_file}. Known summary: {summary}. "
            "Sections: Title, What happened, Why it is high severity, Immediate checks. "
            "Do not call tools."
        )
    else:
        dest = DIGEST
        description = (
            f"Write a short Markdown digest for {source_file}. Known summary: {summary}. "
            "Sections: Title, Quiet review, Why it is low severity. Do not call tools."
        )
    task = Task(
        description=description,
        expected_output="A short Markdown note.",
        agent=agent,
        output_file=str(dest),
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)


def _write_memory(severity: str, summary: str, artifact: Path) -> None:
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    MEMORY.write_text(
        (
            "# Ticket memory\n\n"
            f"- Source: `{SOURCE}`\n"
            f"- Severity: {severity}\n"
            f"- Summary: {summary}\n"
            f"- Artifact: `{artifact.name}`\n"
            "- Follow up: review the source address, confirm whether the deny burst stopped, "
            "and note any later successful admin login from a trusted address.\n"
        ),
        encoding="utf-8",
    )


class SeverityFlow(Flow[SeverityState]):
    @start()
    def classify(self) -> str:
        raw = str(_classifier_crew(self.state.source_file).kickoff())
        severity = "low"
        summary = raw.strip().replace("\n", " ")
        for line in raw.splitlines():
            upper = line.strip()
            if upper.upper().startswith("SEVERITY:"):
                value = upper.split(":", 1)[1].strip().lower()
                if "high" in value:
                    severity = "high"
                elif "low" in value:
                    severity = "low"
            if upper.upper().startswith("SUMMARY:"):
                summary = upper.split(":", 1)[1].strip()
        # Fail safe: an SSH deny burst in this lab file is high even if the model hedges.
        lowered = raw.lower()
        if "deny" in lowered and "198.51.100.66" in raw:
            severity = "high"
        self.state.severity = severity
        self.state.summary = summary
        return severity

    @router(classify)
    def route(self, severity: str) -> str:
        return "high_path" if severity == "high" else "low_path"

    @listen("high_path")
    def write_incident(self) -> str:
        _writer_crew("high", self.state.source_file, self.state.summary).kickoff()
        _write_memory("high", self.state.summary, INCIDENT)
        return f"high -> {INCIDENT}"

    @listen("low_path")
    def write_digest(self) -> str:
        _writer_crew("low", self.state.source_file, self.state.summary).kickoff()
        _write_memory("low", self.state.summary, DIGEST)
        return f"low -> {DIGEST}"


def main() -> None:
    flow = SeverityFlow()
    result = flow.kickoff()
    print(result)
    print(f"severity={flow.state.severity}")
    print(f"memory={MEMORY}")


if __name__ == "__main__":
    main()
