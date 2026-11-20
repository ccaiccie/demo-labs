"""Unit tests for config_diff.py."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config_diff  # noqa: E402

SAMPLE_BEFORE = PROJECT_ROOT / "samples" / "backups" / "edge-rtr1_2026-11-18.cfg"
SAMPLE_AFTER = PROJECT_ROOT / "samples" / "backups" / "edge-rtr1_2026-11-19.cfg"


class TestClassifySection(unittest.TestCase):
    def test_known_section_categories(self) -> None:
        cases = [
            ("global", "global"),
            ("interface GigabitEthernet0/0", "interface"),
            ("interface Loopback0", "interface"),
            ("router bgp 65010", "router"),
            ("router ospf 1", "router"),
            ("line vty 0 4", "line"),
            ("line con 0", "line"),
            ("ip access-list extended MGMT", "access-list"),
            ("ip access-list standard SNMP_RO", "access-list"),
            ("route-map ISP_IN permit 10", "route-map"),
            ("policy-map WAN_SHAPE", "policy-map"),
            ("class-map match-any VOICE", "class-map"),
            ("crypto map VPN_MAP 10 ipsec-isakmp", "crypto"),
            ("vlan 20", "vlan"),
            ("vrf definition MGMT", "vrf"),
        ]
        for header, expected in cases:
            with self.subTest(header=header):
                self.assertEqual(config_diff.classify_section(header), expected)

    def test_fallback_category(self) -> None:
        specific = {
            "global",
            "interface",
            "router",
            "line",
            "access-list",
            "route-map",
            "policy-map",
            "class-map",
            "crypto",
            "vlan",
            "vrf",
        }
        category = config_diff.classify_section("aaa group server tacacs+ CORP")
        self.assertIsInstance(category, str)
        self.assertTrue(category)
        self.assertNotIn(category, specific)


class TestParseConfig(unittest.TestCase):
    def test_crlf_and_lf_produce_identical_sections(self) -> None:
        lf_text = (
            "hostname edge-rtr1\n"
            "!\n"
            "interface GigabitEthernet0/0\n"
            " description WAN\n"
            " ip address 198.51.100.1 255.255.255.252\n"
            "!\n"
        )
        crlf_text = lf_text.replace("\n", "\r\n")

        lf_sections = config_diff.parse_config(lf_text)
        crlf_sections = config_diff.parse_config(crlf_text)

        self.assertEqual(list(lf_sections.keys()), list(crlf_sections.keys()))
        for name in lf_sections:
            self.assertEqual(lf_sections[name].name, crlf_sections[name].name)
            self.assertEqual(lf_sections[name].category, crlf_sections[name].category)
            self.assertEqual(list(lf_sections[name].lines), list(crlf_sections[name].lines))
            for line in crlf_sections[name].lines:
                self.assertNotIn("\r", line)

    def test_skips_comments_and_blank_lines(self) -> None:
        text = (
            "! Top banner comment\n"
            "\n"
            "hostname edge-rtr1\n"
            "   \n"
            "!\n"
            "interface GigabitEthernet0/0\n"
            " ! indented comment\n"
            "\n"
            " description LAN\n"
            "!\n"
            "! trailing comment\n"
        )
        sections = config_diff.parse_config(text)

        self.assertEqual(list(sections.keys()), ["global", "interface GigabitEthernet0/0"])
        global_lines = [line.strip() for line in sections["global"].lines]
        self.assertEqual(global_lines, ["hostname edge-rtr1"])
        iface_lines = [line.strip() for line in sections["interface GigabitEthernet0/0"].lines]
        self.assertEqual(iface_lines, ["description LAN"])

    def test_global_and_named_sections(self) -> None:
        text = (
            "hostname edge-rtr1\n"
            "!\n"
            "interface GigabitEthernet0/0\n"
            " no shutdown\n"
            "!\n"
            "logging host 10.20.0.50\n"
            "ntp server 10.20.0.10\n"
        )
        sections = config_diff.parse_config(text)

        self.assertEqual(list(sections.keys()), ["global", "interface GigabitEthernet0/0"])
        self.assertEqual(sections["global"].category, "global")
        self.assertEqual(
            [line.strip() for line in sections["global"].lines],
            ["hostname edge-rtr1", "logging host 10.20.0.50", "ntp server 10.20.0.10"],
        )
        iface = sections["interface GigabitEthernet0/0"]
        self.assertEqual(iface.name, "interface GigabitEthernet0/0")
        self.assertEqual(iface.category, "interface")
        self.assertEqual([line.strip() for line in iface.lines], ["no shutdown"])
        self.assertIsInstance(iface.start_line, int)

    def test_empty_named_section(self) -> None:
        text = "hostname rtr1\n!\ninterface Loopback0\n!\n"
        sections = config_diff.parse_config(text)

        self.assertIn("interface Loopback0", sections)
        loopback = sections["interface Loopback0"]
        self.assertEqual(loopback.category, "interface")
        self.assertEqual(list(loopback.lines), [])

    def test_duplicate_sections_merged_in_first_seen_order(self) -> None:
        text = (
            "interface GigabitEthernet0/0\n"
            " description first-block\n"
            "!\n"
            "router bgp 65010\n"
            " bgp router-id 1.1.1.1\n"
            "!\n"
            "interface GigabitEthernet0/0\n"
            " ip address 10.0.0.1 255.255.255.0\n"
            "!\n"
        )
        sections = config_diff.parse_config(text)

        self.assertEqual(
            list(sections.keys()),
            ["interface GigabitEthernet0/0", "router bgp 65010"],
        )
        merged_lines = [line.strip() for line in sections["interface GigabitEthernet0/0"].lines]
        self.assertEqual(
            merged_lines,
            ["description first-block", "ip address 10.0.0.1 255.255.255.0"],
        )

    def test_config_section_default_start_line(self) -> None:
        section = config_diff.ConfigSection(name="global", category="global", lines=())
        self.assertIsNone(section.start_line)


class TestDiffConfigs(unittest.TestCase):
    def test_no_changes(self) -> None:
        cfg = (
            "hostname rtr1\n"
            "!\n"
            "interface GigabitEthernet0/0\n"
            " ip address 10.0.0.1 255.255.255.0\n"
            "!\n"
        )
        diff = config_diff.diff_configs(cfg, cfg, before_source="a.cfg", after_source="b.cfg")

        self.assertFalse(diff.has_changes)
        self.assertEqual(diff.total_added, 0)
        self.assertEqual(diff.total_removed, 0)
        self.assertEqual(diff.before_source, "a.cfg")
        self.assertEqual(diff.after_source, "b.cfg")
        changed = [sec for sec in diff.sections if sec.status != "unchanged"]
        self.assertEqual(changed, [])

    def test_added_removed_and_modified_sections(self) -> None:
        before = (
            "hostname rtr1\n"
            "!\n"
            "interface GigabitEthernet0/0\n"
            " description old\n"
            " ip address 10.0.0.1 255.255.255.0\n"
            "!\n"
            "interface GigabitEthernet0/1\n"
            " description legacy\n"
            "!\n"
        )
        after = (
            "hostname rtr1\n"
            "!\n"
            "interface GigabitEthernet0/0\n"
            " description new\n"
            " ip address 10.0.0.1 255.255.255.0\n"
            " no shutdown\n"
            "!\n"
            "interface GigabitEthernet0/2\n"
            " description added\n"
            "!\n"
        )
        diff = config_diff.diff_configs(before, after)
        by_name = {sec.section: sec for sec in diff.sections}

        self.assertTrue(diff.has_changes)
        self.assertEqual(diff.total_added, 3)
        self.assertEqual(diff.total_removed, 2)

        self.assertEqual(by_name["interface GigabitEthernet0/0"].status, "modified")
        self.assertEqual(
            [line.strip() for line in by_name["interface GigabitEthernet0/0"].removed],
            ["description old"],
        )
        self.assertEqual(
            [line.strip() for line in by_name["interface GigabitEthernet0/0"].added],
            ["description new", "no shutdown"],
        )
        self.assertEqual(by_name["interface GigabitEthernet0/1"].status, "removed")
        self.assertEqual(len(by_name["interface GigabitEthernet0/1"].removed), 1)
        self.assertEqual(by_name["interface GigabitEthernet0/2"].status, "added")
        self.assertEqual(len(by_name["interface GigabitEthernet0/2"].added), 1)

    def test_empty_added_and_removed_sections_included(self) -> None:
        before = "hostname rtr1\n!\ninterface Loopback10\n!\n"
        after = "hostname rtr1\n!\ninterface Loopback20\n!\n"

        diff = config_diff.diff_configs(before, after)
        by_name = {sec.section: sec for sec in diff.sections}

        self.assertTrue(diff.has_changes)
        self.assertIn("interface Loopback10", by_name)
        self.assertEqual(by_name["interface Loopback10"].status, "removed")
        self.assertEqual(list(by_name["interface Loopback10"].added), [])
        self.assertEqual(list(by_name["interface Loopback10"].removed), [])

        self.assertIn("interface Loopback20", by_name)
        self.assertEqual(by_name["interface Loopback20"].status, "added")
        self.assertEqual(list(by_name["interface Loopback20"].added), [])
        self.assertEqual(list(by_name["interface Loopback20"].removed), [])

    def test_duplicate_lines_handled_by_sequencematcher(self) -> None:
        before = (
            "ip access-list extended TEST\n"
            " permit ip any any\n"
            " permit ip any any\n"
            "!\n"
        )
        after_removed_one = (
            "ip access-list extended TEST\n"
            " permit ip any any\n"
            "!\n"
        )
        diff_remove = config_diff.diff_configs(before, after_removed_one)
        sec_remove = next(s for s in diff_remove.sections if s.section == "ip access-list extended TEST")
        self.assertEqual(sec_remove.status, "modified")
        self.assertEqual(len(sec_remove.removed), 1)
        self.assertEqual(len(sec_remove.added), 0)
        self.assertEqual(diff_remove.total_removed, 1)
        self.assertEqual(diff_remove.total_added, 0)

        diff_add = config_diff.diff_configs(after_removed_one, before)
        sec_add = next(s for s in diff_add.sections if s.section == "ip access-list extended TEST")
        self.assertEqual(sec_add.status, "modified")
        self.assertEqual(len(sec_add.added), 1)
        self.assertEqual(len(sec_add.removed), 0)
        self.assertEqual(diff_add.total_added, 1)
        self.assertEqual(diff_add.total_removed, 0)

    def test_by_category_preserves_order(self) -> None:
        before = (
            "interface GigabitEthernet0/0\n"
            " description a\n"
            "!\n"
            "router bgp 65010\n"
            " bgp router-id 1.1.1.1\n"
            "!\n"
            "interface GigabitEthernet0/1\n"
            " description b\n"
            "!\n"
        )
        after = (
            "interface GigabitEthernet0/0\n"
            " description a-updated\n"
            "!\n"
            "interface GigabitEthernet0/1\n"
            " description b-updated\n"
            "!\n"
            "line vty 0 4\n"
            " transport input ssh\n"
            "!\n"
        )
        diff = config_diff.diff_configs(before, after)
        grouped = diff.by_category()

        self.assertEqual(list(grouped.keys()), ["interface", "router", "line"])
        self.assertEqual(
            [sec.section for sec in grouped["interface"]],
            ["interface GigabitEthernet0/0", "interface GigabitEthernet0/1"],
        )
        self.assertEqual([sec.section for sec in grouped["router"]], ["router bgp 65010"])
        self.assertEqual([sec.section for sec in grouped["line"]], ["line vty 0 4"])

    def test_to_dict_structure(self) -> None:
        before = "hostname rtr1\n!\ninterface Loopback0\n description a\n!\n"
        after = "hostname rtr1\n!\ninterface Loopback0\n description b\n!\n"
        diff = config_diff.diff_configs(before, after, before_source="b.cfg", after_source="a.cfg")
        payload = diff.to_dict()

        expected_keys = {
            "before_source",
            "after_source",
            "has_changes",
            "total_added",
            "total_removed",
            "changed_sections",
            "sections",
            "by_category",
        }
        self.assertTrue(expected_keys.issubset(payload.keys()))
        self.assertEqual(payload["before_source"], "b.cfg")
        self.assertEqual(payload["after_source"], "a.cfg")
        self.assertTrue(payload["has_changes"])
        self.assertEqual(payload["total_added"], 1)
        self.assertEqual(payload["total_removed"], 1)
        self.assertIsInstance(payload["sections"], list)
        self.assertIsInstance(payload["by_category"], dict)

        changed_section_dicts = [s for s in payload["sections"] if s["status"] != "unchanged"]
        self.assertEqual(len(changed_section_dicts), 1)
        sec_dict = changed_section_dicts[0]
        self.assertEqual(
            set(sec_dict.keys()),
            {"section", "category", "status", "added", "removed"},
        )
        self.assertEqual(sec_dict["section"], "interface Loopback0")
        self.assertEqual(sec_dict["status"], "modified")


class TestSampleBackupsAndCli(unittest.TestCase):
    def test_diff_sample_backups(self) -> None:
        diff = config_diff.diff_files(SAMPLE_BEFORE, SAMPLE_AFTER)

        self.assertTrue(diff.has_changes)
        self.assertEqual(diff.total_added, 7)
        self.assertEqual(diff.total_removed, 3)

        changed = [sec for sec in diff.sections if sec.status != "unchanged"]
        self.assertEqual(len(changed), 5)
        self.assertEqual(
            {sec.section for sec in changed},
            {
                "global",
                "interface GigabitEthernet0/2",
                "router bgp 65010",
                "ip access-list extended MGMT",
                "line vty 0 4",
            },
        )
        statuses = {sec.section: sec.status for sec in changed}
        self.assertEqual(statuses["global"], "modified")
        self.assertEqual(statuses["interface GigabitEthernet0/2"], "added")
        self.assertEqual(statuses["router bgp 65010"], "modified")
        self.assertEqual(statuses["ip access-list extended MGMT"], "modified")
        self.assertEqual(statuses["line vty 0 4"], "modified")

    def test_format_text_diff(self) -> None:
        diff = config_diff.diff_files(SAMPLE_BEFORE, SAMPLE_AFTER)
        text = config_diff.format_text_diff(diff)

        self.assertIn("interface GigabitEthernet0/2", text)
        self.assertIn("router bgp 65010", text)
        self.assertIn("ip access-list extended MGMT", text)
        self.assertIn("line vty 0 4", text)
        self.assertIn("snmp-server community public RW", text)

        clean = config_diff.diff_configs("hostname r1\n", "hostname r1\n")
        clean_text = config_diff.format_text_diff(clean)
        self.assertTrue(clean_text.strip())

    def test_cli_text_output(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = config_diff.main([str(SAMPLE_BEFORE), str(SAMPLE_AFTER)])

        self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("interface GigabitEthernet0/2", output)
        self.assertIn("transport input telnet ssh", output)

    def test_cli_json_output(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = config_diff.main([str(SAMPLE_BEFORE), str(SAMPLE_AFTER), "--json"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["has_changes"])
        self.assertEqual(payload["total_added"], 7)
        self.assertEqual(payload["total_removed"], 3)
        changed = [s for s in payload["sections"] if s["status"] != "unchanged"]
        self.assertEqual(len(changed), 5)

        diff = config_diff.diff_files(SAMPLE_BEFORE, SAMPLE_AFTER)
        self.assertEqual(payload, json.loads(config_diff.format_json_diff(diff)))

    def test_cli_missing_file_returns_error(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = config_diff.main(["does_not_exist_before.cfg", str(SAMPLE_AFTER)])
        self.assertEqual(code, 1)
        self.assertTrue(stderr.getvalue().strip())

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = config_diff.main([str(SAMPLE_BEFORE), "does_not_exist_after.cfg"])
        self.assertEqual(code, 1)
        self.assertTrue(stderr.getvalue().strip())

    def test_build_parser(self) -> None:
        parser = config_diff.build_parser()
        args = parser.parse_args(["before.cfg", "after.cfg", "--json"])
        self.assertTrue(args.json)


if __name__ == "__main__":
    unittest.main()
