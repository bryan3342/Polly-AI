"""Gesture metrics, and what they refuse to claim.

Hands are tracked so that delivery can be graded on more than voice and face:
a speaker who never brings their hands into view reads as stiff, one whose
hands never stop reads as distracting. Both are measurable from the frames.

What is *not* measurable from the frames is the difference between "this
speaker kept their hands down" and "hand tracking was unavailable". Both leave
an empty timeline, and only the first deserves a low score. That distinction is
what most of these tests are about.

Nothing here loads MediaPipe: the summary is arithmetic over frame results, and
keeping it that way is what lets it run in CI.
"""

from app.services.gesture_service import GestureService, empty_result
from app.services.scoring_service import calculate_overall_score, score_gestures

summarise = GestureService.calculate_summary


def _frame(hands=0, wrist=(0.5, 0.5)):
    """One frame result, with `hands` hands whose wrist sits at `wrist`."""
    if not hands:
        return empty_result()
    landmarks = [[wrist[0], wrist[1]]] + [[0.5, 0.5]] * 20
    return {
        "hands": [{"handedness": "Right", "landmarks": landmarks,
                   "fingertips": [[0.5, 0.5]] * 5}] * hands,
        "hands_detected": True,
        "hand_count": hands,
    }


class TestSummary:
    def test_an_empty_timeline_measures_nothing(self):
        """No frames is not 'no gestures'; it is no information."""
        assert summarise([])["hands_visible_ratio"] is None

    def test_visible_ratio_counts_frames_with_hands(self):
        timeline = [_frame(1), _frame(1), _frame(0), _frame(0)]

        assert summarise(timeline)["hands_visible_ratio"] == 0.5

    def test_a_speaker_who_never_raises_their_hands_is_measured_not_skipped(self):
        """This is a real observation about their delivery, and must reach the
        score -- unlike an empty timeline, which is an absence of data."""
        summary = summarise([_frame(0) for _ in range(10)])

        assert summary["frames"] == 10
        assert summary["hands_visible_ratio"] == 0.0
        assert score_gestures({"gesture_summary": summary}) is not None

    def test_movement_is_measured_between_consecutive_visible_frames(self):
        timeline = [_frame(1, (0.2, 0.5)), _frame(1, (0.3, 0.5))]

        assert summarise(timeline)["movement_per_frame"] == 0.1

    def test_a_gap_in_tracking_is_not_counted_as_movement(self):
        """Hands leaving frame and returning elsewhere is not a gesture; without
        this, losing tracking for a moment would register as a large sweep."""
        timeline = [_frame(1, (0.1, 0.1)), _frame(0), _frame(1, (0.9, 0.9))]

        assert summarise(timeline)["movement_per_frame"] is None

    def test_a_still_speaker_records_no_movement(self):
        timeline = [_frame(1, (0.5, 0.5)) for _ in range(5)]

        assert summarise(timeline)["movement_per_frame"] == 0.0


class TestScoring:
    def test_unavailable_tracking_is_omitted_rather_than_scored(self):
        """The regression this guards: hand tracking failing to load, and every
        session silently losing marks for it."""
        assert score_gestures({"gesture_summary": summarise([])}) is None
        assert score_gestures({}) is None

    def test_a_natural_amount_of_gesturing_scores_full_marks(self):
        timeline = [_frame(1) for _ in range(6)] + [_frame(0) for _ in range(4)]

        assert score_gestures({"gesture_summary": summarise(timeline)}) == 100.0

    def test_hands_never_visible_scores_lowest(self):
        summary = summarise([_frame(0) for _ in range(10)])

        assert score_gestures({"gesture_summary": summary}) == 60.0

    def test_gestures_join_the_overall_score(self):
        timeline = [_frame(1) for _ in range(5)] + [_frame(0) for _ in range(5)]
        summary = {"gesture_summary": summarise(timeline)}

        with_gestures = calculate_overall_score({}, {}, summary)

        assert with_gestures == 100.0, "gesture score should reach the overall score"

    def test_the_overall_score_ignores_gestures_when_they_were_not_tracked(self):
        """Absent hand tracking must not drag the score down, and must not prop
        it up either -- it simply is not one of the components."""
        assert calculate_overall_score({}, {}, {"gesture_summary": summarise([])}) is None
