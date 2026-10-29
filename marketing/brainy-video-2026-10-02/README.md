# Musebook / Clawd — Follow the connections

One-minute marketing video, 2 October 2026. 13 scenes at 30 fps; landscape 1920×1080 and vertical 1080×1920. Both exports contain exactly 1,800 video frames.

Uses brainy.mov, brainy34.mov, clawd-builder-320.webp, and clawd-mascot-dark.png. The two recordings have no audio streams. Soundtrack: supplied SOLGPT Night - Track 2 - Treblo.mp3, starting at 0.603719 seconds. Automated beat analysis found approximately 117.45 BPM; every scene entrance follows the measured beat grid, rounded to the nearest frame. The ending is intentionally fixed at 60 seconds rather than a beat beyond one minute.

Motion: staggered title fades with eased horizontal entrances, floating Clawd hero cards, eased footage entrances, gentle footage push-ins, and beat-aligned scene cuts. Original assets are preserved. The montage shows the supplied graph, launch tank, and Town footage without adding simulated activity.

## Editable sources
source/render.py controls clips, typography, framing, character motion, music, and shot order. source/timeline.json and timeline.csv document the edit. PNG layers and supplied character images are included with fonts and their licenses. Original MOVs and full MP3 remain at their original absolute paths and are not duplicated in the package.

Reproduce from this directory with ffmpeg/ffprobe installed:
```sh
python3 -m venv source/.venv
source/.venv/bin/pip install pillow
source/.venv/bin/python source/render.py
source/.venv/bin/python source/package_and_verify.py
```
Update the source paths in render.py when moving machines. beats.json contains the measured music beats, so reanalysis is unnecessary.

## QA and publication
review/qa.json contains full-decode checks, duration/frame count, volume peaks, beat timing error, and export hashes. Contact sheets show every scene. Nothing published.
