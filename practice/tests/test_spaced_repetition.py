"""Pin the contract of the spaced-repetition stub."""

from django.test import SimpleTestCase

from practice import spaced_repetition, theory


class NextRoundWeightsStubTests(SimpleTestCase):
    def test_uniform_weights_for_shipped_forms(self):
        form_ids = list(theory.load_fingerings())
        weights = spaced_repetition.next_round_weights(form_ids)
        self.assertEqual(len(weights), len(form_ids))
        self.assertEqual(weights, [1.0] * len(form_ids))

    def test_all_weights_equal_and_positive(self):
        """Uniform, so weighted choice == uniform random selection."""
        weights = spaced_repetition.next_round_weights(["a", "b", "c", "d"])
        self.assertEqual(len(set(weights)), 1)
        self.assertGreater(weights[0], 0)

    def test_empty_input(self):
        self.assertEqual(spaced_repetition.next_round_weights([]), [])

    def test_history_argument_accepted(self):
        """The future signature takes attempt history; must not break now."""
        weights = spaced_repetition.next_round_weights(
            ["a", "b"], attempt_history=[])
        self.assertEqual(weights, [1.0, 1.0])
