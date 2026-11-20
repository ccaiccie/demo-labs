# netops-tools — `syslog_triage.py`

A lightweight, standard-library-only Python 3 CLI tool for parsing and triaging Cisco IOS and ASA RFC 3164 syslog files.

## Features

- Parses RFC 3164 `<PRI>` headers (0–191) and decodes syslog **facility** (`PRI // 8`) and **PRI severity** (`PRI % 8`).
- Extracts timestamp, host, Cisco `%FACILITY-SEV-MNEMONIC` tag (and its parts), and message body.
- Uses the Cisco tag severity as the authoritative severity when a tag is present (falling back to the PRI severity for untagged lines).
- Counts parsed and unparsed lines.
- Prints a summary by severity and by host, an **ALERTS** section for:
  - Severities `0`–`3` (`emerg`, `alert`, `crit`, `err`)
  - `LOGIN_FAILED` events
  - BPDU guard events
  - Err-disable events
- Prints a **MISMATCHES** section listing lines where the PRI severity differs from the Cisco tag severity.
- Supports optional `--json` output and reading from `stdin`.

## Usage

```bash
# Human-readable triage report
python syslog_triage.py samples/sample.log

# JSON output
python syslog_triage.py samples/sample.log --json

# Read from stdin
cat samples/sample.log | python syslog_triage.py
```

## Running Tests

```bash
python -m unittest discover -s tests -v
```
