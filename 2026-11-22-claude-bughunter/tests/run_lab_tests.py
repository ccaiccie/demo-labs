#!/usr/bin/env python3
"""
Authorized local-only security QA & verification runner for the
NetOps Inventory & Ticket Portal fixture (http://127.0.0.1:8765).

Loads synthetic test cases from testdata/test-payloads.json, verifies
True Positives (SQLi, Reflected XSS, Horizontal IDOR), confirms False Positives
(safe JSON echo), checks HTTP security headers, and validates before/after
remediation states.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_HOSTS = {"127.0.0.1", "localhost"}

SKILL_MAP = {
    "xss": "hunt-xss",
    "sqli": "hunt-sqli",
    "idor": "hunt-idor",
    "false_positive": "triage-validation",
    "baseline": "bb-methodology",
}


def enforce_loopback(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(
            f"Refusing non-loopback target '{base_url}'. "
            "Authorized local lab scope allows ONLY 127.0.0.1 / localhost."
        )
    return base_url.rstrip("/")


def http_get(
    base_url: str,
    path: str,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {})
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{query}"

    req = urllib.request.Request(url, method="GET")
    for k, v in (headers or {}).items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_body = resp.read().decode("utf-8", errors="replace")
            resp_headers = {k: v for k, v in resp.headers.items()}
            return {
                "url": url,
                "status_code": resp.status,
                "headers": resp_headers,
                "body": raw_body,
            }
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        resp_headers = {k: v for k, v in exc.headers.items()}
        return {
            "url": url,
            "status_code": exc.code,
            "headers": resp_headers,
            "body": raw_body,
        }


def get_header_ci(headers: dict[str, str], name: str) -> str:
    target = name.lower()
    for k, v in headers.items():
        if k.lower() == target:
            return v
    return ""


def evaluate_case(
    case: dict[str, Any],
    response: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    expected = case["expected_patched"] if mode == "patched" else case["expected_vulnerable"]
    status = response["status_code"]
    body = response["body"]
    content_type = get_header_ci(response["headers"], "Content-Type")
    nosniff = get_header_ci(response["headers"], "X-Content-Type-Options")

    checks: list[dict[str, Any]] = []

    if "status_code" in expected:
        checks.append({
            "check": "status_code",
            "expected": expected["status_code"],
            "observed": status,
            "passed": status == expected["status_code"],
        })

    if "content_type_contains" in expected:
        exp_ct = expected["content_type_contains"]
        checks.append({
            "check": "content_type_contains",
            "expected": exp_ct,
            "observed": content_type,
            "passed": exp_ct.lower() in content_type.lower(),
        })

    if "body_contains" in expected:
        needle = expected["body_contains"]
        checks.append({
            "check": "body_contains",
            "expected": needle,
            "observed": needle in body,
            "passed": needle in body,
        })

    if "must_not_contain" in expected:
        forbidden = expected["must_not_contain"]
        checks.append({
            "check": "must_not_contain",
            "expected": f"absent:{forbidden}",
            "observed": "absent" if forbidden not in body else "present",
            "passed": forbidden not in body,
        })

    if "unescaped_marker" in expected:
        marker = expected["unescaped_marker"]
        checks.append({
            "check": "unescaped_marker",
            "expected": marker,
            "observed": marker in body,
            "passed": marker in body,
        })

    if "escaped_marker" in expected:
        marker = expected["escaped_marker"]
        checks.append({
            "check": "escaped_marker",
            "expected": marker,
            "observed": marker in body,
            "passed": marker in body,
        })

    if "expected_device_count" in expected or "min_device_count" in expected:
        device_count = None
        try:
            parsed_json = json.loads(body)
            if isinstance(parsed_json, dict) and "count" in parsed_json:
                device_count = int(parsed_json["count"])
            elif isinstance(parsed_json, dict) and isinstance(parsed_json.get("devices"), list):
                device_count = len(parsed_json["devices"])
        except (json.JSONDecodeError, TypeError, ValueError):
            device_count = None

        if "expected_device_count" in expected:
            exp_cnt = expected["expected_device_count"]
            checks.append({
                "check": "expected_device_count",
                "expected": exp_cnt,
                "observed": device_count,
                "passed": device_count == exp_cnt,
            })
        if "min_device_count" in expected:
            min_cnt = expected["min_device_count"]
            checks.append({
                "check": "min_device_count",
                "expected": f">={min_cnt}",
                "observed": device_count,
                "passed": device_count is not None and device_count >= min_cnt,
            })

    if expected.get("not_executable_html"):
        is_json = "application/json" in content_type.lower()
        is_not_html = "text/html" not in content_type.lower()
        checks.append({
            "check": "not_executable_html",
            "expected": "application/json (non-HTML)",
            "observed": f"Content-Type={content_type}; X-Content-Type-Options={nosniff or 'none'}",
            "passed": is_json and is_not_html,
        })

    all_passed = all(c["passed"] for c in checks)

    category = case["category"]
    if category == "baseline":
        verdict = "BASELINE_PASS" if all_passed else "BASELINE_FAIL"
    elif category == "false_positive":
        verdict = "FP_CONFIRMED" if all_passed else "FP_CHECK_FAIL"
    elif mode == "patched":
        verdict = "PATCHED_VERIFIED" if all_passed else "STILL_VULNERABLE"
    else:
        verdict = "TP_CONFIRMED" if all_passed else "NOT_REPRODUCED"

    main_idx = body.find("<main>")
    body_preview = body[main_idx : main_idx + 1200] if main_idx != -1 else body[:1200]

    return {
        "id": case["id"],
        "category": category,
        "skill": SKILL_MAP.get(category, "bb-methodology"),
        "name": case["name"],
        "expected_classification": case["expected_classification"],
        "verdict": verdict,
        "passed": all_passed,
        "request": {
            "method": case["method"],
            "url": response["url"],
            "headers": case.get("headers", {}),
        },
        "response": {
            "status_code": status,
            "content_type": content_type,
            "headers": response["headers"],
            "body_preview": body_preview,
            "body_length": len(body),
        },
        "checks": checks,
        "rationale": case["rationale"],
    }


def check_security_headers(base_url: str) -> dict[str, Any]:
    resp = http_get(base_url, "/")
    tracked = [
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Strict-Transport-Security",
    ]
    present: dict[str, str] = {}
    missing: list[str] = []
    for h in tracked:
        val = get_header_ci(resp["headers"], h)
        if val:
            present[h] = val
        else:
            missing.append(h)
    return {
        "url": resp["url"],
        "status_code": resp["status_code"],
        "present": present,
        "missing": missing,
        "note": (
            "Per triage-validation skill, missing security headers alone are "
            "Informational/Low unless chained to a concrete exploit."
        ),
    }


def format_text_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("Claude-BugHunter Local Lab Security Assessment & Verification Report")
    lines.append("=" * 78)
    lines.append(f"Timestamp (UTC): {report['timestamp_utc']}")
    lines.append(f"Target Base URL: {report['target_base_url']}")
    lines.append(f"Fixture Mode:    {report['fixture_mode']}")
    lines.append(f"Fixture Patches: {json.dumps(report['fixture_patches'])}")
    lines.append(
        f"Summary:         total={report['summary']['total_cases']} "
        f"passed={report['summary']['passed']} failed={report['summary']['failed']} "
        f"tp_confirmed={report['summary']['tp_confirmed']} "
        f"patched_verified={report['summary']['patched_verified']} "
        f"fp_confirmed={report['summary']['fp_confirmed']}"
    )
    lines.append("")

    sh = report["security_headers"]
    lines.append("--- Security Headers Check (GET /) ---")
    lines.append(f"Status:  {sh['status_code']}")
    lines.append(f"Present: {json.dumps(sh['present'])}")
    lines.append(f"Missing: {', '.join(sh['missing']) if sh['missing'] else 'none'}")
    lines.append(f"Note:    {sh['note']}")
    lines.append("")

    for res in report["results"]:
        lines.append("-" * 78)
        lines.append(
            f"[{res['id']}] {res['name']} | skill={res['skill']} | "
            f"verdict={res['verdict']} | pass={res['passed']}"
        )
        lines.append(f"Request:  {res['request']['method']} {res['request']['url']}")
        if res["request"]["headers"]:
            lines.append(f"Headers:  {json.dumps(res['request']['headers'])}")
        lines.append(
            f"Response: HTTP {res['response']['status_code']} "
            f"({res['response']['content_type']}, {res['response']['body_length']} bytes)"
        )
        for chk in res["checks"]:
            status_tag = "OK" if chk["passed"] else "FAIL"
            lines.append(
                f"  [{status_tag}] {chk['check']}: expected={chk['expected']} "
                f"observed={chk['observed']}"
            )
        lines.append("Body Preview:")
        lines.append(res["response"]["body_preview"])
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run authorized local-only security tests against http://127.0.0.1:8765"
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8765",
        help="Loopback fixture URL (default: http://127.0.0.1:8765)",
    )
    parser.add_argument(
        "--payloads",
        default="testdata/test-payloads.json",
        help="Path to test-payloads.json",
    )
    parser.add_argument("--out-txt", help="Optional path to write text report")
    parser.add_argument("--out-json", help="Optional path to write JSON report")
    args = parser.parse_args()

    base_url = enforce_loopback(args.base_url)
    payloads_path = Path(args.payloads)
    if not payloads_path.exists():
        print(f"ERROR: payloads file not found: {payloads_path}", file=sys.stderr)
        return 2

    data = json.loads(payloads_path.read_text(encoding="utf-8"))

    health_resp = http_get(base_url, "/health")
    if health_resp["status_code"] != 200:
        print(
            f"ERROR: /health returned HTTP {health_resp['status_code']}: {health_resp['body']}",
            file=sys.stderr,
        )
        return 2

    health_json = json.loads(health_resp["body"])
    mode = health_json.get("mode", "vulnerable")
    patches = health_json.get("patches", {})

    results: list[dict[str, Any]] = []
    for case in data["cases"]:
        resp = http_get(
            base_url,
            case["path"],
            params=case.get("params"),
            headers=case.get("headers"),
        )
        results.append(evaluate_case(case, resp, mode))

    sec_headers = check_security_headers(base_url)

    summary = {
        "total_cases": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "tp_confirmed": sum(1 for r in results if r["verdict"] == "TP_CONFIRMED"),
        "patched_verified": sum(1 for r in results if r["verdict"] == "PATCHED_VERIFIED"),
        "fp_confirmed": sum(1 for r in results if r["verdict"] == "FP_CONFIRMED"),
        "baselines_passed": sum(1 for r in results if r["verdict"] == "BASELINE_PASS"),
    }

    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_base_url": base_url,
        "fixture_mode": mode,
        "fixture_patches": patches,
        "security_headers": sec_headers,
        "summary": summary,
        "results": results,
    }

    text_report = format_text_report(report)
    print(text_report)

    if args.out_txt:
        out_txt = Path(args.out_txt)
        out_txt.parent.mkdir(parents=True, exist_ok=True)
        out_txt.write_text(text_report, encoding="utf-8")

    if args.out_json:
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
