# Emotion accuracy eval

Measures what `EmotionService` actually returns on labelled faces, rather than
that it runs without raising. The unit tests in `tests/unit` cover the geometry
and the plumbing; this covers whether the answers are right.

```bash
python backend/tests/eval/build_fixtures.py   # one time, 20 images
python backend/tests/eval/run_eval.py         # the smoke test, ~10s

python backend/tests/eval/build_pool.py       # one time, 175 images
python backend/tests/eval/run_eval.py --pool  # what changes are decided on
```

Neither is collected by `pytest`: `pytest.ini` restricts `testpaths` to
`tests/unit`, and these need the full ML stack plus a one time network fetch.
Run them by hand after touching detection, the crop, or the models.

**Use `--pool` to judge a change.** At n=20 a single image is five points, so
every candidate pipeline looks the same; the 20 fixtures are a smoke test, not
evidence. Every number quoted below came from the 175.

## Method

Images come from `muxspace/facial_expressions`, roughly 13.7k hand-labelled
photographs, drawn with a fixed seed and stratified across the seven classes
because the source is 92% neutral and happy. Anything under 200px on either side
is skipped: the source mixes 350x350 portraits with thumbnails as small as
47x68, and the thumbnails fail detection for reasons a webcam frame never
reproduces.

The eval drives the real `analyze_frame`, so detection, alignment, the crop and
classification are all exercised the way a live frame exercises them. Detection
and classification are scored separately, because a frame with no face is a
detection failure and charging it to the classifier as well would conflate two
problems with different fixes.

### Two ground truths

The source labels are crowd-sourced and are the weakest part of this benchmark.
Independent agents were shown the same images blind, with no access to the
source labels or to each other, and asked for a label and a confidence. Those
are in `annotator_labels.json` and `pool_labels.json`.

They agree with the source on 104 of 175 (59%). So accuracy against the source
alone understates the pipeline, and the **trusted subset**, where both passes
agree, is the figure worth quoting.

### Read balanced accuracy, not just top-1

The pool is class-imbalanced and so is the trusted subset (23% neutral). A model
that over-predicts one common class scores well on plain top-1 without being
better. Balanced accuracy, the mean of the per-class recalls, is what caught
that during tuning, and `run_eval.py` prints it.

## Results, 2026-09-08

On the 175-image pool. "Before" is Haar detection with DeepFace's FER2013
classifier; "after" is what ships now.

| metric | before | after |
| --- | --- | --- |
| faces detected | 159/175 (91%) | 174/175 (99%) |
| **trusted subset, of detected** | **49/99 (50%)** | **76/103 (74%)** |
| trusted subset, end to end | 47% | 73% |
| **balanced accuracy (trusted)** | **37%** | **51%** |
| macro F1 (trusted) | 0.35 | 0.51 |
| top-1 vs source labels | 41% | 55% |
| latency | 6.1 ms | 10.3 ms |
| chance baseline | 14% | 14% |

On the 20 committed fixtures: detection 17/20 to 20/20, end to end 45% to 55%,
trusted subset 73% to 83%.

### What changed, and what each part was worth

Measured one at a time on the pool, against the source labels, so the numbers
are depressed by label noise but the ranking is sound:

| pipeline | detected | top-1 of detected |
| --- | --- | --- |
| Haar + DeepFace (before) | 90.9% | 40.9% |
| Haar + DeepFace, without the RGB conversion | 90.9% | 40.9% |
| YuNet + DeepFace | 99.4% | 39.1% |
| YuNet + align + DeepFace | 99.4% | 40.8% |
| YuNet + align + FER+ | 99.4% | 54.0% |
| YuNet + align + FER+ + mirror averaging | 99.4% | 55.2% |

- **The detector was the free win.** YuNet found 174 of 175 faces against Haar's
  159, and did it *faster*, 2.8 ms against 3.8 ms. It is a small ONNX file run
  through `cv2.dnn`, so it added no dependency. Loosening Haar's
  `detectMultiScale` to `1.05, 3` was the alternative: it reaches 95%, but costs
  7.0 ms, nearly twice YuNet for less accuracy.
- **The classifier was the real ceiling.** DeepFace's model is trained on the
  original FER2013 labels. FER+ is the same images relabelled by ten annotators
  each, and swapping it in was worth 13 points on identical crops at the same
  speed. It is also an ONNX file, so it too cost no new dependency.
- **Alignment and mirror averaging are worth about a point each**, which is
  inside the noise at this n. They are kept because they are nearly free and
  point the right way, not because this set proves them.
- **Margin is not worth tuning.** Sweeping 0.0 to 0.4 moved top-1 by up to 4.6
  points with no monotonic trend, which is noise, not signal. The 0.18 default
  stands.

## What still fails

**Disgust and fear are still not usable**, 2/12 and 3/13. FER+ almost never
predicts either: across 174 faces it returned disgust twice and fear four times.
An independent blind pass also disputed the source label on nearly every one of
those images, reading them as anger or sadness, so the true rate is unknown and
the sample is too small to fix that. `UNRELIABLE` in `emotion_service.py` names
them. Nothing downstream should present them as findings.

**Sadness is now under-reported rather than over-reported.** Recall fell from
50% to 39%, but precision rose from 43% to 88%. That is the right direction for
a debate coach: the old pipeline's habit of reading a sad face as angry is gone
(anger precision went from 68% to 100%), and telling a nervous speaker they look
angry is worse than saying nothing.

**Neutral is over-predicted.** 91% recall but only 50% precision, so half of
what it calls neutral is not. It is the safest possible failure for this product
and it is why balanced accuracy (51%) is well below top-1 (74%).

**Confidence still does not track correctness** well enough to threshold on.

## Caveats

- The trusted subset is 104 images, and its disgust and fear cells are 1 and 2
  images. Per-class figures for those two are not measurements.
- The images are stills of public figures, many greyscale, not webcam video of
  someone mid-argument. Lighting, motion blur and a fixed camera angle are all
  untested here.
- The stratified draw makes the headline pessimistic against real session
  footage, which is mostly neutral and happy.
- Latency is a developer machine. The ratio between stages is what transfers to
  a fractional-CPU host, not the absolute numbers; see `Config.DETECT_WIDTH`.
