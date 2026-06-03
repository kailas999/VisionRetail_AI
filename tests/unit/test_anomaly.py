# PROMPT: "Write comprehensive pytest unit tests for a Z-score anomaly detection engine that has
# three functions: _compute_zscore(current, historical), _severity(z_score), and _confidence(z, n_points).
# Cover edge cases: empty historical, insufficient data, zero variance, positive spike, negative drop,
# boundary values at each severity threshold (2.5, 2.8, 3.0), and confidence scaling with data volume.
# Also test that RECOMMENDED_ACTIONS dict covers all four anomaly types and contains no hedging language."
#
# CHANGES MADE:
# - Added TestRecommendedActions class (AI did not generate this — added manually to test determinism guarantee).
# - Changed 'assert z > 3.0' to 'assert z > 2.0' in test_zscore_normal_distribution — AI's threshold was too tight.
# - Added test_zscore_positive_spike to explicitly document the zero-variance edge case (AI missed this).
# - Removed a duplicate test_confidence_always_between_0_and_1 that AI generated (covered by test_confidence_in_range).
"""Unit tests for anomaly detection Z-score engine."""
import pytest
import numpy as np

from app.services.anomaly import _compute_zscore, _severity, _confidence


class TestZScore:

    def test_zscore_positive_spike(self):
        historical = [10.0] * 10
        z = _compute_zscore(25.0, historical)
        # All historical identical → std approaches 0 → z undefined
        assert z is None  # Zero variance

    def test_zscore_normal_distribution(self):
        historical = [10, 12, 9, 11, 10, 13, 8, 11, 10, 12]
        z = _compute_zscore(20.0, historical)  # Clear spike
        assert z is not None
        assert z > 2.0  # Clearly above mean

    def test_zscore_low_value_negative(self):
        historical = [20, 22, 19, 21, 20, 23, 18, 21, 20, 22]
        z = _compute_zscore(5.0, historical)  # Clear drop
        assert z is not None
        assert z < -2.0

    def test_zscore_at_mean_is_zero(self):
        historical = [10, 12, 8, 11, 9]
        mean = np.mean(historical)
        z = _compute_zscore(float(mean), historical)
        assert z is not None
        assert abs(z) < 0.5

    def test_insufficient_data_returns_none(self):
        z = _compute_zscore(10.0, [5.0, 8.0])  # Only 2 points
        assert z is None

    def test_empty_historical_returns_none(self):
        z = _compute_zscore(10.0, [])
        assert z is None


class TestSeverity:

    def test_medium_severity(self):
        assert _severity(2.6) == "MEDIUM"
        assert _severity(-2.6) == "MEDIUM"

    def test_high_severity(self):
        assert _severity(2.9) == "HIGH"
        assert _severity(-2.9) == "HIGH"

    def test_critical_severity(self):
        assert _severity(3.5) == "CRITICAL"
        assert _severity(-3.5) == "CRITICAL"

    def test_exactly_critical_threshold(self):
        assert _severity(3.0) == "CRITICAL"


class TestConfidence:

    def test_low_confidence_few_data_points(self):
        conf = _confidence(3.0, 3)  # Only 3 days of data
        assert conf < 0.5

    def test_high_confidence_many_points(self):
        conf = _confidence(4.0, 14)  # 2 weeks of data
        assert conf > 0.5

    def test_confidence_in_range(self):
        for n in [3, 7, 14]:
            for z in [2.5, 3.0, 4.0]:
                conf = _confidence(z, n)
                assert 0.0 <= conf <= 1.0

    def test_higher_zscore_higher_confidence(self):
        conf_low = _confidence(2.6, 10)
        conf_high = _confidence(4.0, 10)
        assert conf_high > conf_low


class TestRecommendedActions:
    """Ensure recommended actions are always rule-based, never empty."""

    def test_all_anomaly_types_have_actions(self):
        from app.services.anomaly import RECOMMENDED_ACTIONS
        expected_types = {"QUEUE_SPIKE", "CONVERSION_DROP", "DEAD_ZONE", "TRAFFIC_DROP"}
        for atype in expected_types:
            assert atype in RECOMMENDED_ACTIONS
            assert len(RECOMMENDED_ACTIONS[atype]) > 20  # Meaningful, not empty

    def test_actions_do_not_contain_hallucination_markers(self):
        from app.services.anomaly import RECOMMENDED_ACTIONS
        for atype, action in RECOMMENDED_ACTIONS.items():
            assert "probably" not in action.lower()
            assert "maybe" not in action.lower()
            assert "might" not in action.lower()
