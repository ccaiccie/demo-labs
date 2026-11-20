"""Offline contract/regex checks, NOT a replacement for Ansible syntax-check."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = r"(?m)^interface GigabitEthernet0/2\n((?:[ \t].*\n)*)"


class PlaybookContract(unittest.TestCase):
    def test_stanza_does_not_borrow_other_interface_description(self):
        config = "interface GigabitEthernet0/0\n description PRACTICE-LINK\n!\ninterface GigabitEthernet0/2\n ip forwarding\n!\n"
        stanza = re.findall(PATTERN, config)
        self.assertEqual(len(stanza), 1)
        self.assertNotIn(" description PRACTICE-LINK\n", stanza[0])

    def test_description_need_not_be_first_line(self):
        config = "interface GigabitEthernet0/2\n ip forwarding\n description PRACTICE-LINK\n!\n"
        self.assertIn(" description PRACTICE-LINK\n", re.findall(PATTERN, config)[0])

    def test_duplicate_interface_is_ambiguous(self):
        config = "interface GigabitEthernet0/2\n description PRACTICE-LINK\n!\n" * 2
        self.assertEqual(len(re.findall(PATTERN, config)), 2)

    def test_guardrails_and_no_save(self):
        content = (ROOT / "ansible/description.yml").read_text()
        for guard in ["execute_lab_change: false", "dedicated_ubuntu_vm_confirmed: false",
                      "become: false", "gather_facts: false", "save_when: never",
                      "expected_before == device_specs[inventory_hostname].before", "ansible_host not in ['192.0.2.10', '192.0.2.11']"]:
            self.assertIn(guard, content)
        self.assertNotIn("write memory", content)
        self.assertNotIn("ansible.builtin.shell", content)
        self.assertIn("cisco.ios.ios_config:", content)
        self.assertIn("operation: adopt", content)
        self.assertIn("check_mode: \"{{ operation in ['adopt', 'review'] or ansible_check_mode }}\"", content)
        self.assertIn("exact_interface_confirmed: false", content)
        self.assertIn("demo_platform == device_specs[inventory_hostname].platform", content)
        ci = (ROOT / ".gitlab-ci.yml").read_text()
        commands = [line.strip() for line in ci.splitlines() if "ansible-playbook" in line]
        self.assertEqual(commands, ["- ansible-playbook -i ansible/inventory.example.yml ansible/description.yml --syntax-check"])
        for forbidden in ("execute_lab_change", "operation=apply", "operation=rollback", "stage: deploy"):
            self.assertNotIn(forbidden, ci)


if __name__ == "__main__":
    unittest.main()
