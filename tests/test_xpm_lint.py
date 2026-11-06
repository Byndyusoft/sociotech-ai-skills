"""Offline regression cases. No service calls or production writes."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/experience-process-mapping/scripts/lint_xpm.py"
spec = importlib.util.spec_from_file_location("lint_xpm", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def node(node_id, kind="KeyPoint", name="Согласование заказа", start=False):
    layers = [] if kind == "Trigger" else [
        {"type": "Input", "isEnabled": True, "values": ["Запрос клиента"]},
        {"type": "Output", "isEnabled": True, "values": ["Согласованные условия"]},
    ]
    return {"id": node_id, "name": name, "type": kind, "isStart": start, "layers": layers}


def model():
    return {"lanes": [
        {"id": "customer", "rows": [{"id": "c-row", "nodes": [node("a1", start=True), node("a2")]}]},
        {"id": "operator", "rows": [{"id": "o-row", "nodes": [node("b1"), node("b2")]}]},
    ], "links": []}


def link(link_id, a, b, kind="Interaction", label="Согласование"):
    return {"id": link_id, "sourceNodeId": a, "targetNodeId": b, "type": kind, "label": label}


class LintCases(unittest.TestCase):
    def codes(self, value):
        return {issue["code"] for issue in module.inspect_map(value)["issues"]}

    def test_distinct_contacts_and_no_mutation(self):
        value = model()
        value["links"] = [link("i1", "a1", "b1"), link("i2", "a2", "b2")]
        before = copy.deepcopy(value)
        self.assertEqual(module.inspect_map(value)["error_count"], 0)
        self.assertEqual(value, before)

    def test_transitive_interaction_group(self):
        value = model()
        value["links"] = [link("i1", "a1", "b1"), link("i2", "a2", "b1")]
        self.assertIn("interaction_group_repeats_lane", self.codes(value))

    def test_reverse_interaction_duplicate(self):
        value = model()
        value["links"] = [link("i1", "a1", "b1"), link("i2", "b1", "a1")]
        self.assertIn("reverse_interaction_duplicate", self.codes(value))

    def test_conditional_dash_is_review_not_error(self):
        value = model()
        value["links"] = [link("s1", "a1", "a2", "SequenceDashed", "Нет — выбран отказ")]
        self.assertIn("conditional_dashed", self.codes(value))
        self.assertEqual(module.inspect_map(value)["error_count"], 0)
        value["links"][0]["label"] = "Нет ответа; ожидание подтверждения"
        self.assertNotIn("conditional_dashed", self.codes(value))

    def test_trigger_without_layers_can_be_complete(self):
        value = model()
        value["lanes"][0]["rows"][0]["nodes"].append(node("g", "Trigger", "Условия согласованы?"))
        value["links"] = [link("y", "g", "a1", "SequenceSolid", "Да"), link("n", "g", "a2", "SequenceSolid", "Нет")]
        codes = self.codes(value)
        self.assertNotIn("key_point_missing_io", codes)
        self.assertNotIn("trigger_missing_outcome", codes)
        value["links"][1]["label"] = ""
        self.assertIn("trigger_unlabelled_outcome", self.codes(value))

    def test_cross_lane_sequence_is_not_automatically_forbidden(self):
        value = model()
        value["links"] = [link("s1", "a1", "b1", "SequenceSolid", "Передача результата")]
        self.assertIn("cross_lane_sequence", self.codes(value))
        self.assertEqual(module.inspect_map(value)["error_count"], 0)

    def test_wrapped_content_and_unknown_format(self):
        value = model()
        wrapped = {"content": [{"type": "text", "text": json.dumps(value)}]}
        self.assertEqual(module.inspect_map(wrapped), module.inspect_map(value))
        with self.assertRaises(ValueError):
            module.inspect_map({"unrelated": []})


if __name__ == "__main__":
    unittest.main()
