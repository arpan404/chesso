import copy
import unittest

from hint_bank import attach_outputs, generation_requests
from study import load_protocol


class HintBankTests(unittest.TestCase):
    def setUp(self):
        self.protocol = load_protocol()
        self.requests = generation_requests(self.protocol)
        self.outputs = dict(format="chesso-hint-outputs-v1", protocol_hash=self.requests["protocol_hash"],
                            hints=[dict(item_id=r["item_id"], position_hash=r["position_hash"],
                                        text="Synthetic hint for this test only.",
                                        reflection_prompt="Synthetic question for this test only?",
                                        generation=dict(model="SYNTHETIC_TEST_MODEL", prompt=r["prompt"],
                                                        generated_at="2026-10-06T00:00:00+00:00"))
                                   for r in self.requests["requests"]])

    def test_only_training_is_sent_for_generation(self):
        ids = {r["item_id"] for r in self.requests["requests"]}
        expected = {i["id"] for i in self.protocol["items"] if i["set"] == "training"}
        self.assertEqual(ids, expected)
        self.assertEqual(len(ids), 8)

    def test_import_keeps_real_prompt_and_remains_draft(self):
        attached = attach_outputs(self.protocol, self.outputs)
        self.assertEqual(attached["hint_source"], "llm")
        self.assertEqual(attached["status"], "pilot")
        for item in attached["items"]:
            if item["set"] == "training":
                self.assertEqual(item["hint"]["review_status"], "draft")
                self.assertEqual(item["hint"]["generation"]["model"], "SYNTHETIC_TEST_MODEL")
        self.assertEqual(self.protocol["hint_source"], "human_template")

    def test_stale_position_or_prompt_is_rejected(self):
        for field, bad in (("position_hash", "other_position"), ("protocol_hash", "old_protocol")):
            output = copy.deepcopy(self.outputs)
            if field == "protocol_hash":
                output[field] = bad
            else:
                output["hints"][0][field] = bad
            with self.assertRaises(ValueError):
                attach_outputs(self.protocol, output)
        self.outputs["hints"][0]["generation"]["prompt"] = "different prompt"
        with self.assertRaises(ValueError):
            attach_outputs(self.protocol, self.outputs)

    def test_duplicate_or_missing_response_is_rejected(self):
        self.outputs["hints"].append(self.outputs["hints"][0])
        with self.assertRaises(ValueError):
            attach_outputs(self.protocol, self.outputs)
        self.outputs["hints"] = self.outputs["hints"][:3]
        with self.assertRaises(ValueError):
            attach_outputs(self.protocol, self.outputs)
