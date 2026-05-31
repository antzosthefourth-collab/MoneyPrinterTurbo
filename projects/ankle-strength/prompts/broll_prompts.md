# Generative B-roll prompts (OPTIONAL — not part of the MVP)

The MVP uses real stock/local footage because current text/image-to-video models
**visibly warp feet and ankles** (the hardest body part to animate). Only consider
generating a couple of *establishing* shots (full-body, no intricate foot motion) and
stage them as local clips. Do NOT generate the detailed ankle-work clips.

Recommended routes (2026): fal.ai (LTX-2 has native 9:16; Wan supports a reference
clip for a consistent person) or Google Veo 3.1 (native 9:16). See README for the
gated `enable_generative_broll` switch.

## Consistent character prompt (use unchanged across scenes)
A realistic athletic adult fitness instructor in a bright clean home gym. Neutral
workout clothes, natural lighting, calm confident expression, realistic body
proportions, clear view of feet, ankles, and lower legs. Instructional fitness video
style, vertical 9:16, 1080x1920, steady camera, no cinematic blur.

## Negative prompt
cartoon, anime, distorted feet, extra toes, warped legs, unstable joints, blurry
motion, bad anatomy, extreme muscles, dark room, cinematic smoke, text over feet,
crowded background, unsafe form, medical clinic setting

## Establishing-shot example (safe to generate)
The same realistic fitness instructor steps into frame in a bright clean home gym and
stands ready, full body visible. Vertical 9:16, steady camera, natural lighting,
instructional fitness video. (Cut to real footage for the actual exercises.)
