import unittest

import numpy as np

from train_patch_objects import boxes_from_probabilities, patch_labels


class SpatialContractTests(unittest.TestCase):
    def test_rectangular_image_coordinates(self):
        # Top-right 2 patches of a 400x200 image must map to x=200..400,y=0..100.
        detections = boxes_from_probabilities(np.array([0, 0, .99, .99, 0, 0, 0, 0]), (2, 4), (400, 200))
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]['box'], [200, 0, 400, 100])

    def test_unknown_is_never_a_negative_training_label(self):
        labels = patch_labels((2, 4), (400, 200), {'label': 'UNKNOWN', 'bbox_xyxy': None})
        np.testing.assert_array_equal(labels, [-1]*8)

    def test_partial_boundary_is_ignored(self):
        labels = patch_labels((1, 4), (400, 100), {'label': 'YES', 'bbox_xyxy': [80, 0, 200, 100]})
        np.testing.assert_array_equal(labels, [-1, 1, 0, 0])

    def test_single_patch_noise_is_suppressed(self):
        self.assertEqual(boxes_from_probabilities(np.array([.99, 0, 0, 0]), (2, 2), (100, 100)), [])


if __name__ == '__main__':
    unittest.main()
