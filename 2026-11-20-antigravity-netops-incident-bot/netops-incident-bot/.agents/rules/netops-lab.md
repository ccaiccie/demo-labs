---
trigger: always_on
---

# NetOps Lab Project Rules

Follow these constraints for all code, configuration, tests, and sample data in the NetOps incident bot project:

## Networking & Ports
- Bind host-exposed services exclusively to `127.0.0.1`.
- Use UDP port `5515` for syslog ingestion and TCP port `8097` for the web/REST API.
- Never use ports `3000`, `5514`, `5678`, `8088`, `8090`, `8099`, or `9095`; they are already occupied on this machine.

## Runtime & Dependencies
- Use Python 3.12 and the Python standard library only.
- Do not add third-party packages or run `pip install`.

## Testing
- Every Python module must have corresponding `unittest` tests.

## Security & Secrets
- Never print, log, or commit secrets, tokens, or API keys.

## Sample Data
- Use only RFC 5737 documentation IP ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`).
- Use clearly made-up hostnames (no real hostnames or internal domain names).
