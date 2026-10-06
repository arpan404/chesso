import unittest

from research import attempts, clean_for_sos, sequences


class LegacySequenceTests(unittest.TestCase):
    def row(self, number, grade="Good", hint=False):
        return dict(kind="attempt", subject="SYNTHETIC", session="test", puzzle_id="one",
                    t=number, move_no_in_line=number, cp_loss=0, grade=grade, hint_used=hint)

    def test_exclusion_cannot_bridge_across_a_hinted_move(self):
        rows = [self.row(1, "Best"), self.row(2, hint=True), self.row(3, "Blunder")]
        eligible = {id(r) for r in clean_for_sos(rows)}
        pairs = [(a,b) for a,b in sequences(attempts(rows)) if id(a) in eligible and id(b) in eligible]
        self.assertEqual(pairs, [])

    def test_repeat_reset_is_not_a_follow_up_pair(self):
        first = self.row(3)
        repeat = self.row(1); repeat["t"] = 4
        self.assertEqual(sequences([first, repeat]), [])
