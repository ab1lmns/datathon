import unittest
import numpy as np
from research.train_action_probe import encode_sequence, decision


class ActionInputTests(unittest.TestCase):
    def test_last_presence_cannot_see_earlier_people(self):
        end = np.arange(8)
        a = encode_sequence('visitor_present_end', [np.zeros(8), end])
        b = encode_sequence('visitor_present_end', [np.ones(8)*999, end])
        np.testing.assert_array_equal(a, b)

    def test_temporal_input_changes_when_order_reversed(self):
        z = [np.zeros(8), np.ones(8)]
        a = encode_sequence('visitor_exit', z)
        b = encode_sequence('visitor_exit', z[::-1])
        self.assertFalse(np.array_equal(a, b))

    def test_uncertain_positive_abstains(self):
        class Head:
            classes_ = np.array(['NO', 'YES'])
            def predict_proba(self, x):
                return np.array([[.3, .7]])
        self.assertEqual(decision(Head(), np.zeros(8))[0], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
