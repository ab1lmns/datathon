"""Presentation only: readable Russian labels without tracker IDs or scores."""
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

@lru_cache(maxsize=8)
def font(size):
    return ImageFont.truetype(str(Path(__file__).resolve().parents[1] / 'assets/fonts/DejaVuSans.ttf'),size)


def render_labels(frame, labels):
    image = Image.fromarray(frame[:, :, ::-1])
    draw = ImageDraw.Draw(image)
    face = font(max(12, min(20, round(image.width / 40))))
    for box, color, text, below in labels:
        x1,y1,x2,y2 = map(int,box)
        bounds = draw.textbbox((0,0),text,font=face)
        width,height = bounds[2]-bounds[0]+10,bounds[3]-bounds[1]+8
        x = max(0,min(x1,image.width-width))
        y = max(0,min(y2+3 if below else y1-height-3,image.height-height))
        draw.rounded_rectangle((x,y,x+width,y+height),radius=3,fill=(24,30,40))
        draw.rectangle((x,y,x+3,y+height),fill=tuple(reversed(color)))
        draw.text((x+7,y+4-bounds[1]),text,font=face,fill=(255,255,255))
    return np.asarray(image)[:,:,::-1].copy()
