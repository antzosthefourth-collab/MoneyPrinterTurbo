# Drop your footage here

Vertical (9:16) clips that clearly show feet/ankles/lower legs, named:

```
00_hook.mp4  01_calf_raises.mp4  02_tibialis_raises.mp4  03_band_4way.mp4
04_single_leg_balance.mp4  05_toe_walks.mp4  06_heel_walks.mp4
07_short_foot.mp4  08_lateral_step_downs.mp4
```

`build.py` stages these into `storage/local_videos/ankle/` automatically. Minimum
480×480; portrait orientation recommended. Missing clips are skipped and footage is
looped to fill the narration. No clips? Run `build.py --source pexels`.
