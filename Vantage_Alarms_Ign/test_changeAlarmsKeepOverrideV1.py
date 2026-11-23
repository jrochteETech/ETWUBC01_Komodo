import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


SOURCE = Path(__file__).with_name("changeAlarmsKeepOverrideV1.py")


class AlarmOverrideTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text())
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        self.tag = SimpleNamespace(getConfiguration=Mock(), configure=Mock())
        self.file = SimpleNamespace(readFileAsBytes=Mock())
        self.namespace = {
            "system": SimpleNamespace(tag=self.tag, file=self.file),
            "unicode": str,
            "print": Mock(),
        }
        exec(compile(tree, str(SOURCE), "exec"), self.namespace)
        self.decision = {"path": "DerivedUDT/Status", "alarmName": "High"}
        self.config = {
            "name": "Status",
            "tagType": "AtomicTag",
            "opcItemPath": {"bindType": "parameter", "binding": "{Device}/Status"},
            "alarms": [
                {
                    "name": "High",
                    "priority": "Critical",
                    "label": {"bindType": "Expression", "value": "{Name}"},
                    "enabled": False,
                    "setpointA": 42,
                    "CustomEmailSubject": "Retain this",
                },
                {"name": "Low", "priority": "Low", "label": "Retain this too"},
            ],
        }

    def apply(self, dry_run=False):
        return self.namespace["apply_decision"](self.decision, 1, 1, dry_run, "Test")

    def modified_config(self):
        result = copy.deepcopy(self.config)
        result["alarms"][0].pop("priority")
        result["alarms"][0].pop("label")
        return result

    def test_live_write_removes_only_selected_fields(self):
        original = copy.deepcopy(self.config)
        expected = self.modified_config()
        self.tag.getConfiguration.side_effect = [[self.config], [expected]]
        self.tag.configure.return_value = [SimpleNamespace(isGood=lambda: True)]

        self.assertEqual(self.apply(), (True, True, True))
        self.tag.configure.assert_called_once_with("[Test]_types_/DerivedUDT", [expected], "o")
        self.assertEqual(self.config, original)
        self.assertEqual(self.decision["status"], "OK")
        self.assertEqual(self.decision["previousPriority"], "Critical")
        self.assertEqual(self.decision["previousLabel"], original["alarms"][0]["label"])

    def test_dry_run_does_not_write_or_mutate(self):
        original = copy.deepcopy(self.config)
        self.tag.getConfiguration.return_value = [self.config]
        self.assertEqual(self.apply(dry_run=True), (True, True, True))
        self.tag.configure.assert_not_called()
        self.assertEqual(self.config, original)
        self.assertEqual(self.decision["status"], "DRY RUN")

    def test_absent_fields_and_single_field_overrides(self):
        for fields, expected_flags in [
            ((), (False, False)),
            (("priority",), (True, False)),
            (("label",), (False, True)),
        ]:
            with self.subTest(fields=fields):
                config = self.modified_config()
                for field in fields:
                    config["alarms"][0][field] = self.config["alarms"][0][field]
                self.tag.getConfiguration.return_value = [config]
                self.assertEqual(self.apply(dry_run=True), (True,) + expected_flags)
        self.tag.configure.assert_not_called()

    def test_missing_tag_or_alarm_does_not_write(self):
        for configs in [[], [{"name": "Status"}], [{"alarms": [{"name": "Other"}]}]]:
            with self.subTest(configs=configs):
                self.tag.getConfiguration.return_value = configs
                self.assertEqual(self.apply(), (False, False, False))
                self.assertEqual(self.decision["status"], "ERROR")
        self.tag.configure.assert_not_called()

    def test_failed_write_and_failed_readback_are_reported(self):
        changed = self.modified_config()
        changed["alarms"][0]["setpointA"] = 99
        for qualities, readback in [
            ([], []),
            ([SimpleNamespace(isGood=lambda: False)], []),
            ([SimpleNamespace(isGood=lambda: True)], [self.config]),
            ([SimpleNamespace(isGood=lambda: True)], []),
            ([SimpleNamespace(isGood=lambda: True)], [changed]),
        ]:
            with self.subTest(qualities=qualities, readback=readback):
                self.tag.getConfiguration.side_effect = [[self.config], readback]
                self.tag.configure.return_value = qualities
                self.assertEqual(self.apply(), (False, False, False))
                self.assertEqual(self.decision["status"], "ERROR")

    def test_csv_requires_only_path_and_alarm_name(self):
        self.namespace["bytes_to_unicode"] = lambda value: value
        self.file.readFileAsBytes.return_value = (
            'path,alarmName\nDerivedUDT/Config/Status,"High, Alarm"\n'
            '[Test]_types_/DerivedUDT/Status,High\nDerivedUDT/Status,\n'
        )
        decisions, skipped = self.namespace["read_decisions"]("Test", "input.csv")
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["alarmName"], "High, Alarm")
        self.assertEqual(len(skipped), 2)
        for text in ["", "path,action\nDerivedUDT/Status,keep\n"]:
            with self.subTest(text=text):
                self.file.readFileAsBytes.return_value = text
                self.assertEqual(self.namespace["read_decisions"]("Test", "input.csv"), ([], []))


if __name__ == "__main__":
    unittest.main()
