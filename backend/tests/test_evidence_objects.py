import unittest
from forte.evidence_objects import evidence_object, state_history


class EvidenceObjectsTest(unittest.TestCase):
    def test_boxes_use_actual_frame_and_clip_boundaries(self):
        obj = evidence_object('safe', 'safe', 'Сейф', 'закрыт', [-10, 20, 80, 200], 100, 200, (200, 200, 0))
        self.assertEqual(obj['bbox'], [0, .1, .8, 1])
        self.assertEqual(obj['color'], '#00c8c8')
        self.assertIsNone(evidence_object('x', 'x', 'x', 'x', [5, 0, 2, 9], 10, 10, (0, 0, 0)))

    def test_history_keeps_transitions_and_exposes_missing_coverage(self):
        history = state_history([(0, .1), (.5, .2), (1, .9), (5, .1)], lambda p: 'open' if p >= .5 else 'closed', max_gap=1.5)
        self.assertEqual(history, [{'timestamp_sec': 0, 'state': 'closed'}, {'timestamp_sec': 1, 'state': 'open'},
                                   {'timestamp_sec': 2.5, 'state': 'Состояние не определено'}, {'timestamp_sec': 5, 'state': 'closed'}])

    def test_no_history_is_not_a_closed_state(self):
        self.assertEqual(state_history([], str), [])
