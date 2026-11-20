import unittest

from export_description import export


class ExportDescriptionTests(unittest.TestCase):
    def test_only_selected_port_and_approved_description(self):
        result = export("lab-r1",
                        "Interface Status Protocol Description\n"
                        "Gi0/1 up up PRIVATE-BACKUP-STRING\n"
                        "Gi0/2 admin down down PRACTICE-LINK\n"
                        "Gi0/20 up up OTHER\n")
        self.assertEqual(result, {"schema": 1, "device": "lab-r1",
                                  "interface": "GigabitEthernet0/2",
                                  "description": "PRACTICE-LINK"})

    def test_second_reviewed_value(self):
        line = "GigabitEthernet0/2 up up PRACTICE-SWITCH reviewed demo  "
        self.assertEqual(export("lab-sw1", line)["description"],
                         "PRACTICE-SWITCH reviewed demo")

    def test_wrong_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            export("lab-r1", "interface GigabitEthernet0/2\n description PRACTICE-LINK")

    def test_duplicates_rejected(self):
        line = "Gi0/2 up up PRACTICE-LINK"
        with self.assertRaisesRegex(ValueError, "exactly one"):
            export("lab-r1", line + "\n" + line)

    def test_unexpected_selected_text_not_disclosed(self):
        with self.assertRaisesRegex(ValueError, "^no usable allowlisted description"):
            export("lab-r1", "Gi0/2 up up private-or-unreviewed")

    def test_device_specific_allowlist(self):
        with self.assertRaises(ValueError):
            export("lab-r1", "Gi0/2 up up PRACTICE-SWITCH")

    def test_malformed_second_row_is_ambiguous(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            export("lab-r1", "Gi0/2 up up PRACTICE-LINK\nGi0/2")


if __name__ == "__main__":
    unittest.main()
