"""Uniform original-frame review export; records actual decoded PTS, no labels."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
from PIL import Image, ImageDraw


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--step', type=float, default=2)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256(a.video.read_bytes()).hexdigest()
    cap = cv2.VideoCapture(str(a.video))
    rows, tiles = [], []
    target, index = 0., -1
    while cap.grab():
        index += 1
        pts = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
        if pts < target:
            continue
        ok, frame = cap.retrieve()
        if not ok:
            raise RuntimeError('decode failed')
        pts = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
        im = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        filename = f'{index:06d}.png'
        path = a.output/filename
        im.save(path)
        rows.append(dict(source_video=a.video.name, source_sha256=digest, frame_index=index,
            pts_sec=pts, path=filename, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            width=im.width, height=im.height))
        tile = Image.new('RGB', (232, 448), 'white')
        im.thumbnail((232, 424))
        tile.paste(im, (0, 24))
        ImageDraw.Draw(tile).text((5, 5), f'{len(rows)-1}: {pts:.3f}s frame {index}', fill='black')
        tiles.append(tile)
        target += a.step
    cap.release()
    (a.output/'frames.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    for start in range(0, len(tiles), 12):
        page = Image.new('RGB', (928, 448*3), '#dddddd')
        for j, tile in enumerate(tiles[start:start+12]):
            page.paste(tile, ((j%4)*232, (j//4)*448))
        page.save(a.output/f'review_{start//12}.jpg', quality=92)
    print(json.dumps(dict(frames=len(rows), first=rows[0]['pts_sec'], last=rows[-1]['pts_sec'])))


if __name__ == '__main__':
    main()
