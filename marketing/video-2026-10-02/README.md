# Musebook beat-synced marketing video — 2 October 2026

Duration: 33.40s. Ten scenes; 30 fps. Landscape 1920×1080 and vertical 1080×1920. H.264/AAC with faststart.

Music: supplied SOLGPT Night - Track 2 - Treblo.mp3, starting at 0.604s. Detected tempo 117.45 BPM. Cuts follow detected beats, rounded to the nearest video frame. Recording audio is retained underneath the music with short edge fades; no generated narration.

## Extracted audio
- recording-1.m4a / .wav: Screen Recording 2026-10-02 at 1.17.02 PM.mov
- recording-2.m4a / .wav: Screen Recording 2026-10-02 at 2.07.00 PM.mov
- recording-3.m4a / .wav: Screen Recording 2026-10-02 at 1.14.51 PM.mov

M4A files retain the original AAC audio without re-encoding. WAV files are PCM editing copies. The second recording is particularly quiet.

## Editing and reproduction
The editable shot list is source/timeline.json and source/timeline.csv. All title layers are PNGs in source/landscape and source/vertical. Fonts and their licenses are included. source/render.py defines typography, layouts, clips, titles, music timing, and audio mix. It recreates the timeline when run; edit that script for changes.

From the campaign folder:
```sh
python3 -m venv source/.venv
source/.venv/bin/pip install pillow numpy scipy librosa
source/.venv/bin/python source/render.py
source/.venv/bin/python source/package_and_verify.py
```
Requires ffmpeg/ffprobe and original source recordings and music at the absolute paths in render.py/timeline.json. Original videos and full music are not duplicated in the package. Update paths when moving machines. Beat analysis was performed by source/analyze_media.py; beats.json is included.

## Validation
Both exports fully decoded without errors. Frame contact sheets and stream/audio measurements are in review/. Cuts are within one half-frame of the detected beat timestamps. Music beat detection is automated, not a manually transcribed musical score.

Nothing published. Source recordings and music are preserved unchanged.
