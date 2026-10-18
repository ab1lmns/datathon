import unittest
from forte.evidence_selection import select_evidence_times

class EvidenceSelectionTest(unittest.TestCase):
    def test_two_become_before_event_after(self):
        self.assertEqual(select_evidence_times(8.8,[8.8,9.8],20),[7.800000000000001,8.8,9.8])
    def test_boundaries_and_short_video(self):
        for event,duration in [(0,20),(19.95,20),(0.1,0.2)]:
            values=select_evidence_times(event,[event],duration)
            self.assertEqual(len(values),len(set(values)))
            self.assertTrue(all(0<=v<=duration-.05 for v in values))
            self.assertLessEqual(len(values),3)
        self.assertEqual(len(select_evidence_times(0,[0],20)),3)
        self.assertEqual(len(select_evidence_times(0.1,[0.1],0.2)),1)
    def test_preserves_main_with_many_evidence_points(self):
        values=select_evidence_times(10,[2,4,12,18],20)
        self.assertEqual(values,[2,10,18])
