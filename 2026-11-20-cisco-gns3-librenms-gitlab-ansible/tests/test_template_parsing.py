"""Exercise real YAML/Jinja layers when optional parser dependencies exist."""
import re
import unittest
from pathlib import Path

try:
    import yaml
    import jinja2
except ImportError:
    yaml = jinja2 = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(yaml and jinja2, "Requires PyYAML and Jinja2; run with guest Ansible Python")
class TemplateParsing(unittest.TestCase):
    def test_stanzas_survive_yaml_jinja_lf_and_crlf(self):
        play = yaml.safe_load((ROOT / 'ansible/description.yml').read_text())
        environment = jinja2.Environment()
        environment.filters['regex_findall'] = lambda value, pattern: re.findall(pattern, value)
        checked = 0
        for task in play[0]['tasks']:
            for key, template in task.get('ansible.builtin.set_fact', {}).items():
                if key not in ('stanzas', 'verified_stanzas'):
                    continue
                # No literal CR should be introduced by YAML decoding.
                self.assertNotIn('\r', template)
                for newline in ('\n', '\r\n'):
                    with self.subTest(key=key, newline=repr(newline)):
                        fixture = newline.join(['interface GigabitEthernet0/2',
                                                ' description PRACTICE-LINK', '!', ''])
                        output = environment.from_string(template).render(
                            running={'stdout': [fixture]}, verified={'stdout': [fixture]})
                        self.assertEqual(output, "[' description PRACTICE-LINK\\n']")
                        checked += 1
        self.assertEqual(checked, 4)
