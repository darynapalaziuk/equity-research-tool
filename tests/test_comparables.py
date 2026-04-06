"""
Tests for the Comparables valuation engine.
Verifies peer median calculation and blended price logic.
"""
import pandas as pd
import pytest

from src.valuation.comparables import ComparablesValuation


def make_peer_df(
    ev_ebitda=(16.0, 23.0, 14.0),
    pe=(23.0, 27.0, 24.0),
    ps=(9.0, 8.8, 7.2),
    pb=(7.1, 8.6, 6.7),
):
    """Helper to create a peer multiples DataFrame."""
    return pd.DataFrame(
        {
            "name": ["Microsoft", "Alphabet", "Meta"],
            "EV/EBITDA": list(ev_ebitda),
            "P/E": list(pe),
            "P/S": list(ps),
            "P/B": list(pb),
        },
        index=["MSFT", "GOOGL", "META"],
    )


class TestCalculatePeerMedians:
    """Tests for peer median calculation."""

    def test_basic_median(self):
        """Median should be middle value of sorted peers."""
        comps = ComparablesValuation()
        peers = make_peer_df(ev_ebitda=(10.0, 20.0, 30.0))
        medians = comps.calculate_peer_medians(peers)
        assert medians["EV/EBITDA"] == pytest.approx(20.0, abs=0.1)

    def test_median_not_mean(self):
        """Median should not be affected by outliers like mean would be."""
        comps = ComparablesValuation()
        # Outlier of 100 should not skew median
        peers = make_peer_df(ev_ebitda=(10.0, 15.0, 100.0))
        medians = comps.calculate_peer_medians(peers)
        assert medians["EV/EBITDA"] == pytest.approx(15.0, abs=0.1)

    def test_all_multiples_calculated(self):
        """All four multiples should have medians."""
        comps = ComparablesValuation()
        peers = make_peer_df()
        medians = comps.calculate_peer_medians(peers)
        assert "EV/EBITDA" in medians
        assert "P/E" in medians
        assert "P/S" in medians
        assert "P/B" in medians


class TestCalculateImpliedPrices:
    """Tests for implied price calculation."""

    def test_pe_implied_price(self):
        """P/E implied price = peer median P/E x target EPS."""
        comps = ComparablesValuation()
        target = {"trailing_eps": 6.43}
        peer_medians = {"P/E": 24.45}
        implied = comps.calculate_implied_prices(target, peer_medians)
        assert implied["P/E"] == pytest.approx(157.21, abs=0.1)

    def test_ps_implied_price(self):
        """P/S implied price = peer median P/S x target revenue per share."""
        comps = ComparablesValuation()
        target = {"revenue_per_share": 25.0}
        peer_medians = {"P/S": 8.88}
        implied = comps.calculate_implied_prices(target, peer_medians)
        assert implied["P/S"] == pytest.approx(222.0, abs=0.1)

    def test_missing_target_data_returns_none(self):
        """Missing target data should return None for that multiple."""
        comps = ComparablesValuation()
        target = {}  # no data
        peer_medians = {"P/E": 24.45, "P/S": 8.88}
        implied = comps.calculate_implied_prices(target, peer_medians)
        assert implied.get("P/E") is None
        assert implied.get("P/S") is None


class TestCalculateBlendedPrice:
    """Tests for blended price calculation."""

    def test_all_multiples_available(self):
        """Blended price should be weighted average of all multiples."""
        comps = ComparablesValuation()
        implied = {
            "EV/EBITDA": 165.0,
            "P/E": 193.0,
            "P/S": 222.0,
            "P/B": 43.0,
        }
        blended, weights = comps.calculate_blended_price(implied)
        assert blended > 0
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_weights_sum_to_one(self):
        """Weights should always sum to 1.0."""
        comps = ComparablesValuation()
        # Only P/E available
        implied = {"P/E": 193.0}
        blended, weights = comps.calculate_blended_price(implied)
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)
        assert blended == pytest.approx(193.0, abs=0.1)

    def test_empty_implied_raises(self):
        """Empty implied prices should raise ValueError."""
        comps = ComparablesValuation()
        with pytest.raises(ValueError):
            comps.calculate_blended_price({})


class TestBlendValuation:
    """Tests for the blended valuation logic in output.py."""

    def test_dcf_only(self):
        """Without comps or DDM, blended should equal DCF."""
        from src.reporting.output import _blend_valuation

        dcf_result = {"dcf_price_target": 179.0}
        comps_result = {"comps_price_target": None}
        blended, weights, upside, rec = _blend_valuation(
            current_price=255.92,
            dcf_result=dcf_result,
            comps_result=comps_result,
            ddm_result=None,
        )
        assert blended == pytest.approx(179.0, abs=0.1)
        assert weights == {"DCF": 1.0}
        assert rec == "SELL"

    def test_dcf_and_comps(self):
        """With DCF and comps, should be 50/50 blend."""
        from src.reporting.output import _blend_valuation

        dcf_result = {"dcf_price_target": 180.0}
        comps_result = {"comps_price_target": 160.0}
        blended, weights, upside, rec = _blend_valuation(
            current_price=255.92,
            dcf_result=dcf_result,
            comps_result=comps_result,
            ddm_result=None,
        )
        assert blended == pytest.approx(170.0, abs=0.1)
        assert weights["DCF"] == 0.50
        assert weights["Comps"] == 0.50

    def test_buy_recommendation(self):
        """Upside > 10% should give BUY."""
        from src.reporting.output import _blend_valuation

        dcf_result = {"dcf_price_target": 300.0}
        comps_result = {"comps_price_target": None}
        _, _, _, rec = _blend_valuation(
            current_price=255.92,
            dcf_result=dcf_result,
            comps_result=comps_result,
        )
        assert rec == "BUY"

    def test_hold_recommendation(self):
        """Upside between -10% and 10% should give HOLD."""
        from src.reporting.output import _blend_valuation

        dcf_result = {"dcf_price_target": 260.0}
        comps_result = {"comps_price_target": None}
        _, _, _, rec = _blend_valuation(
            current_price=255.92,
            dcf_result=dcf_result,
            comps_result=comps_result,
        )
        assert rec == "HOLD"
