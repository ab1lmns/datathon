import copy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from forte.scene import Track
from research.reflection_probe import verified_track_segment, verify_pairs


class ReflectionIntervalTests(unittest.TestCase):
    def test_early_reflection_is_not_restored(self):
        track = Track(1, list(range(7)), [[0,0,10,20]]*7, list(range(7)))
        before = copy.deepcopy(track)
        answers = [dict(time_sec=0,relationship='same_person_or_reflection'),
                   dict(time_sec=3,relationship='different_people'),
                   dict(time_sec=6,relationship='different_people')]
        restored = verified_track_segment(track,[dict(answers=answers)])
        self.assertEqual(restored.t,[3,4,5,6])
        self.assertEqual(track,before)

    def test_unknown_between_positive_votes_does_not_bridge_gap(self):
        track = Track(1,list(range(7)),[[0,0,10,20]]*7,list(range(7)))
        answers = [dict(time_sec=t,relationship=v) for t,v in
                   [(0,'different_people'),(3,'uncertain'),(6,'different_people')]]
        self.assertIsNone(verified_track_segment(track,[dict(answers=answers)]))

    def test_each_possible_twin_must_be_ruled_out(self):
        track = Track(1,list(range(7)),[[0,0,10,20]]*7,list(range(7)))
        yes = [dict(time_sec=t,relationship='different_people') for t in (0,3,6)]
        no = [dict(time_sec=t,relationship='same_person_or_reflection') for t in (0,3,6)]
        self.assertIsNone(verified_track_segment(track,[dict(answers=yes),dict(answers=no)]))

    @patch('forte.video.read_frame', return_value=None)
    def test_decode_failure_is_unknown_and_does_not_call_model(self, read_frame):
        track = Track(1,list(range(7)),[[0,0,10,20]]*7,list(range(7)))
        samples = [dict(time_sec=t,box_a=[0,0,10,20],box_b=[10,0,20,20])
                   for t in (0,3,6)]
        model = Mock()
        recovered, diagnostics = verify_pairs(Path('unreadable.mov'),
            [dict(track=track,comparisons=[dict(other_tid=2,samples=samples)])],model)
        self.assertEqual(recovered,[])
        self.assertFalse(diagnostics[0]['recovered'])
        self.assertEqual([a['time_sec'] for a in diagnostics[0]['comparisons'][0]['answers']], [0,3,6])
        model.ask.assert_not_called()


if __name__=='__main__':
    unittest.main()
