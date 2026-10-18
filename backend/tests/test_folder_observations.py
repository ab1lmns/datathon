import copy
import unittest

from forte.registry import REGISTRY
from forte.folder_observations import append_folder_event, evidence_observations


class CandidateBoundaryTests(unittest.TestCase):
    def test_original_result_and_events_are_preserved(self):
        old = {'verdict': 'violation', 'violations': [
            {'type': 'existing', 'timecode_sec': 2, 'description': 'original', 'evidence_frames': []}],
            'explain': [{'code': 'existing'}], 'meta': {'job_id': 'sample'}}
        snapshot = copy.deepcopy(old)
        result, added = append_folder_event(old, 14, [{'timestamp_sec': 14}])
        self.assertTrue(added)
        self.assertEqual(old, snapshot)
        self.assertEqual(result['violations'][0], old['violations'][0])
        self.assertEqual(result['explain'][0], old['explain'][0])
        self.assertEqual(result['explain'][-1]['details']['basis_status'], 'not_established')
        self.assertEqual(result['explain'][-1]['refs'], [])

    def test_nearby_same_type_is_not_duplicated(self):
        old = {'verdict': 'violation', 'violations': [
            {'type': REGISTRY['A_unattended_valuables']['name'], 'timecode_sec': 13.5}]}
        result, added = append_folder_event(old, 14, [])
        self.assertFalse(added)
        self.assertEqual(result, old)

    def test_evidence_contains_distinct_before_condition_after(self):
        observations = [{'frame_index': i, 'pts_sec': i/2} for i in range(30)]
        evidence = evidence_observations(observations, 14)
        self.assertEqual([o['pts_sec'] for o in evidence], [13, 14, 14.5])

    def test_short_recording_does_not_duplicate_evidence(self):
        observations = [{'frame_index': 0, 'pts_sec': 0}]
        self.assertEqual(evidence_observations(observations, 0), observations)


if __name__ == '__main__':
    unittest.main()
