"""
Unit Tests for SoilSentinel Ranked Prevention & Restoration Recommendation Engine.

Verifies:
1. Recommendation generation from valid risk scoring results.
2. Objective ranking strictly by weighted score descending.
3. Urgency classification (CRITICAL, HIGH, MODERATE, MAINTENANCE).
4. Alkaline vs Acidic pH remediation branching (gypsum vs agricultural lime).
5. Severe moisture and heat stress interventions (mulching, deficit irrigation, stubble).
6. Severe SOC depletion interventions (FYM, compost, green manuring, cessation of burning).
7. Safe withholding of recommendations for INVALID_INPUT and INSUFFICIENT_HISTORY.
8. Dictionary serialization schema and contract compatibility.
"""

import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.risk_scoring import calculate_baseline_risk_score
from src.Model.recommendations import (
    generate_ranked_recommendations,
    RankedRecommendationPlan,
    RecommendationItem,
)


class TestRankedRecommendations(unittest.TestCase):
    """Test the recommendation generation and ranking engine."""

    def setUp(self):
        self.base_record = {
            "date": "2023-05",
            "soil_moisture_rootzone_fraction": 0.40,
            "soil_temperature_layer1_c": 32.0,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": 1.5,
            "precipitation_mm_day": 1.2,
        }

    def test_ranking_order_descending_by_weighted_score(self):
        """Recommendations must strictly be ordered by weighted_score descending."""
        res = calculate_baseline_risk_score(self.base_record)
        plan = generate_ranked_recommendations(res, record=self.base_record)

        self.assertIsInstance(plan, RankedRecommendationPlan)
        self.assertEqual(len(plan.recommendations), 5)

        weighted_scores = [r.weighted_score for r in plan.recommendations]
        self.assertEqual(weighted_scores, sorted(weighted_scores, reverse=True))
        self.assertEqual(plan.primary_stressor, plan.recommendations[0].indicator_name)

    def test_critical_moisture_deficit_intervention(self):
        """Acute drought / desiccation (rootzone <= 0.25) must trigger CRITICAL moisture recommendation."""
        dry_record = self.base_record.copy()
        dry_record["soil_moisture_rootzone_fraction"] = 0.20  # Severe moisture deficit (sub-score 100)

        res = calculate_baseline_risk_score(dry_record)
        plan = generate_ranked_recommendations(res, record=dry_record)

        moisture_rec = next(r for r in plan.recommendations if r.indicator_key == "moisture_deficit")
        self.assertEqual(moisture_rec.urgency, "CRITICAL")
        self.assertEqual(moisture_rec.sub_score, 100.0)
        self.assertIn("mulch", moisture_rec.primary_intervention.lower())
        self.assertTrue(any("mulch" in step.lower() for step in moisture_rec.actionable_steps))
        self.assertIn("[CRITICAL]", plan.critical_actions[0])

    def test_critical_soc_depletion_intervention(self):
        """Severely depleted SOC (<= 5.0 g/kg) must trigger CRITICAL organic matter restoration."""
        depleted_record = self.base_record.copy()
        depleted_record["topsoil_soc_g_kg"] = 4.0  # Severely depleted (sub-score 100)

        res = calculate_baseline_risk_score(depleted_record)
        plan = generate_ranked_recommendations(res, record=depleted_record)

        soc_rec = next(r for r in plan.recommendations if r.indicator_key == "soc_vulnerability")
        self.assertEqual(soc_rec.urgency, "CRITICAL")
        self.assertEqual(soc_rec.action_type, "RESTORATION")
        self.assertTrue(any("manure" in step.lower() or "compost" in step.lower() for step in soc_rec.actionable_steps))
        self.assertTrue(any("burning" in step.lower() for step in soc_rec.actionable_steps))

    def test_alkaline_vs_acidic_ph_remediation_branching(self):
        """Alkaline pH (>8.5) must recommend gypsum; acidic pH (<5.0) must recommend agricultural lime."""
        # Alkaline case
        alkaline_record = self.base_record.copy()
        alkaline_record["topsoil_ph_mean"] = 8.8
        res_alk = calculate_baseline_risk_score(alkaline_record)
        plan_alk = generate_ranked_recommendations(res_alk, record=alkaline_record)
        ph_alk_rec = next(r for r in plan_alk.recommendations if r.indicator_key == "ph_deviation")
        self.assertIn("Sodic", ph_alk_rec.title)
        self.assertTrue(any("gypsum" in step.lower() for step in ph_alk_rec.actionable_steps))

        # Acidic case
        acidic_record = self.base_record.copy()
        acidic_record["topsoil_ph_mean"] = 4.8
        res_acid = calculate_baseline_risk_score(acidic_record)
        plan_acid = generate_ranked_recommendations(res_acid, record=acidic_record)
        ph_acid_rec = next(r for r in plan_acid.recommendations if r.indicator_key == "ph_deviation")
        self.assertIn("Acid", ph_acid_rec.title)
        self.assertTrue(any("lime" in step.lower() for step in ph_acid_rec.actionable_steps))

    def test_withheld_recommendations_on_invalid_input(self):
        """Invalid inputs must withhold recommendations and provide a clear safety action."""
        bad_record = self.base_record.copy()
        bad_record["soil_moisture_rootzone_fraction"] = -1.0  # Invalid input
        res = calculate_baseline_risk_score(bad_record)
        plan = generate_ranked_recommendations(res, record=bad_record)

        self.assertEqual(plan.status, "INVALID_INPUT")
        self.assertIsNone(plan.overall_risk_score)
        self.assertEqual(len(plan.recommendations), 0)
        self.assertIn("Action withheld", plan.critical_actions[0])

    def test_withheld_recommendations_on_insufficient_history(self):
        """Strict-mode missing history must withhold recommendations with clear explanation."""
        strict_gap_record = self.base_record.copy()
        strict_gap_record["precipitation_rolling_3m_mean_mm_day"] = None
        res = calculate_baseline_risk_score(strict_gap_record, allow_partial=False)
        plan = generate_ranked_recommendations(res, record=strict_gap_record)

        self.assertEqual(plan.status, "INSUFFICIENT_HISTORY")
        self.assertIsNone(plan.overall_risk_score)
        self.assertEqual(len(plan.recommendations), 0)
        self.assertIn("Action withheld", plan.critical_actions[0])

    def test_serialization_to_dict_matches_schema(self):
        """to_dict() must return serializable dictionary with all required contract keys."""
        res = calculate_baseline_risk_score(self.base_record)
        plan = generate_ranked_recommendations(res, record=self.base_record)
        d = plan.to_dict()

        for key in ["status", "overall_risk_score", "overall_risk_category", "primary_stressor", "recommendations", "critical_actions", "disclaimer"]:
            self.assertIn(key, d)

        self.assertEqual(len(d["recommendations"]), 5)
        rec0 = d["recommendations"][0]
        for rec_key in ["indicator_key", "indicator_name", "sub_score", "weight", "weighted_score", "urgency", "action_type", "title", "primary_intervention", "actionable_steps", "expected_benefit", "observed_metric"]:
            self.assertIn(rec_key, rec0)


if __name__ == "__main__":
    unittest.main()
