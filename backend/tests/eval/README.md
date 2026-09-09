# Emotion accuracy eval

Measures what `EmotionService` actually does on labelled faces, rather than
that it runs without raising. The unit tests in `tests/unit` cover the geometry
and the plumbing; nothing until now covered whether the answers are right.

```bash
python backend/tests/eval/build_fixtures.py   # one time, downloads 20 images
python backend/tests/eval/run_eval.py         # ~10s
python backend/tests/eval/run_eval.py --json out.json
```

It is not part of `pytest` and does not run in CI: it needs the full ML stack
and a network fetch the first time. Run it by hand after touching detection,
the crop, or the model.

## Method

Fixtures come from `muxspace/facial_expressions`, roughly 13.7k hand-labelled
photographs. 20 are drawn with a fixed seed, stratified across the seven
DeepFace classes rather than sampled naturally, because the source is 92%
neutral and happy and a natural draw would say nothing about the other five.
Anything under 200px on either side is skipped: the source mixes 350x350
portraits with thumbnails as small as 47x68, and the thumbnails fail detection
for reasons a webcam frame never reproduces.

The eval drives the real `analyze_frame`, so Haar detection, the margin crop and
classification are all exercised the way a live frame exercises them.

Detection and classification are scored separately. A frame with no face is a
detection failure, and charging it to the classifier as well would conflate two
problems with different fixes.

### The second opinion

The source labels are crowd-sourced and turned out to be the weakest part of the
benchmark. Four agents were shown the same 20 images blind, with no access to
the source labels or to each other, and asked for a first choice, second choice
and confidence. Their labels are in `annotator_labels.json`.

They agree with the source on only 12 of 20. So the headline accuracy is
measured against ground truth that is itself about 60% reliable, and the subset
where both passes agree is the closest thing here to a trustworthy number.

## Results, 2026-09-08

DeepFace 0.0.100, `facial_expression_model_weights.h5`, on the committed
fixtures.

| metric | value |
| --- | --- |
| faces detected | 17/20 (85%) |
| top-1 of detected, vs source labels | 53% |
| top-2 of detected, vs source labels | 71% |
| top-1 end to end (detection failures counted as wrong) | 45% |
| model vs blind annotator | 59% of detected |
| **trusted subset (source == annotator), n=12** | **8/11 detected correct, 73%** |
| latency | median 6.5ms, max 22.4ms per frame |
| chance baseline | 14% (1 of 7) |

Read the 73% as the honest figure and the 45% as the pessimistic one. The gap
between them is mostly label noise, not model behaviour.

### What fails, and how

**Disgust and fear are not usable.** 0/2 disgust correct, 1/3 fear. This is the
one place the model and the annotators agree with each other and not with the
source: all three disgust fixtures and all three fear fixtures were disputed by
the blind pass, which read them as anger or sadness. Two independent readings
calling the same six images something other than their label is a stronger
signal than either alone. Treat any disgust or fear score coming out of this
pipeline as noise, and do not surface it as debate feedback.

**Sadness collapses into anger.** Two of three sad fixtures came back angry, at
0.48 and 0.69 confidence. For a debate coach this is the costly direction to be
wrong in: telling a nervous speaker they look angry is worse than saying nothing.

**Happiness is solid.** 3/3, at 0.93 to 1.00 confidence. Smiling is the one
signal here worth acting on without hedging.

**Confidence does not track correctness.** The single most confident wrong
answer scored 0.96 (a disgust fixture returned as angry, T14). Thresholding on
`confidence` will not filter the bad predictions out.

### Detection

Three fixtures produced no face at all, all of them 350x350:

- `Jennifer_Capriati_0037` and `Paula_Radcliffe_0004` are found by loosening
  `detectMultiScale` from `1.1, 5` to `1.05, 3`. That takes detection from 17/20
  to 19/20 and produced no spurious extra boxes on these 20. It costs 4.2ms to
  6.9ms per 350x350 frame, so roughly +64% on the detection half of the budget.
  Worth weighing against the `DETECT_WIDTH` measurements, since detection is
  already the expensive stage.
- `Zumrati_Juma_0001` is found by nothing tried: not the default cascade, not
  `alt2`, not `profileface`, not the looser settings. Low contrast and a
  headscarf covering the hairline.

### One code note

`analyze_frame` converts the crop with `cv2.COLOR_BGR2RGB` before handing it to
DeepFace, whose `analyze` documents its numpy input as BGR. On the five colour
images tested the swap moved individual emotion scores by up to 10.8 points but
did not flip the dominant emotion on any of them. It is not the cause of the
accuracy figures above, and most of this fixture set is greyscale so the swap is
a no-op there. Still worth removing: `calculate_summary` averages the whole
score timeline, so a systematic per-frame perturbation of that size reaches the
session summary even when the per-frame label survives.

## Caveats

- n=20. A single fixture is 5 points of headline accuracy, and the per-class
  cells are 2 or 3 images each. Treat the per-class numbers as direction, not
  measurement.
- 15 of the 20 are greyscale, and all are stills of public figures rather than
  webcam video of someone mid-argument. Lighting, motion blur and the fixed
  camera angle of a real session are all untested here.
- The stratified draw makes the headline number pessimistic against real
  footage, which is mostly neutral and happy, the two classes this model
  handles best.
