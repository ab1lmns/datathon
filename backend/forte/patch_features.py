"""Frozen spatial DINOv2 features and the validated folder head configuration."""
import cv2
import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel

MODEL = 'facebook/dinov2-base'
REVISION = 'f9e44c814b77203eaa57a6bdbbd535f21ede1415'
CLASSES = ('folder', 'bag', 'cash')
CONFIG = dict(long_side=784, patch_size=14, threshold=0.90, min_patches=2,
              negatives_per_frame=128, seed=20261018, logistic_C=1.0,
              hard_negative_rounds=2, mining_threshold=0.5)


class Features:
    def __init__(self, device, embedder=None):
        self.device = device
        self.processor = AutoImageProcessor.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
        if embedder is not None and getattr(embedder.model.config, '_commit_hash', None) == REVISION:
            self.model = embedder.model
        else:
            self.model = AutoModel.from_pretrained(MODEL, revision=REVISION, local_files_only=True).to(device).eval()

    @torch.inference_mode()
    def __call__(self, image):
        w, h = image.size
        scale = CONFIG['long_side'] / max(w, h)
        nw, nh = [max(14, round(x*scale/14)*14) for x in (w, h)]
        image = image.resize((nw, nh), Image.Resampling.BICUBIC)
        inputs = self.processor(images=image, do_resize=False, do_center_crop=False, return_tensors='pt').to(self.device)
        features = self.model(**inputs).last_hidden_state[:, 1:]
        features = torch.nn.functional.normalize(features, dim=-1)
        return features[0].float().cpu().numpy(), (nh//14, nw//14)


def boxes_from_probabilities(probs, grid, size):
    h, w = grid
    iw, ih = size
    mask = (probs.reshape(h, w) >= CONFIG['threshold']).astype('uint8')
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for k in range(1, n):
        x, y, bw, bh, area = stats[k]
        if area < CONFIG['min_patches']:
            continue
        out.append(dict(box=[x/w*iw, y/h*ih, (x+bw)/w*iw, (y+bh)/h*ih],
                        score=float(probs.reshape(h, w)[labels == k].mean())))
    return out


