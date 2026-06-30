from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import pandas as pd

import Technic as tc
from Technic import DumVar


SEGMENT_ID = "home_price_GR1"
TARGET = "home_price_GR1"
TARGET_BASE = "home_price_index"
DEFAULT_DRIVER_POOL = ["USMORT30Y", "USPRIME", "USCORPBBB10Y"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _demo_data_path(filename: str) -> Path:
    return _repo_root() / "Demo Data" / filename


def add_demo_features(df_mev: pd.DataFrame, df_in: pd.DataFrame):
    df_mev["USYC10_2"] = df_mev["USGOV10Y"] - df_mev["USGOV2Y"]
    df_mev["USYC10_1"] = df_mev["USGOV10Y"] - df_mev["USGOV1Y"]
    df_mev["USYC10_6M"] = df_mev["USGOV10Y"] - df_mev["USGOV6M"]
    df_mev["USYC30_10"] = df_mev["USGOV30Y"] - df_mev["USGOV10Y"]
    df_mev["USYC5_2"] = df_mev["USGOV5Y"] - df_mev["USGOV2Y"]
    df_mev["USREAL_TERM_PREM_PROXY"] = df_mev["USGOV10Y"] - df_mev["USGOVR10Y"]

    df_mev["USCORP_SPRD_BAA_AAA"] = df_mev["USCORPBBB10Y"] - df_mev["USCORPAA10Y"]
    df_mev["USCORP_SPRD_BAA_T10"] = df_mev["USCORPBBB10Y"] - df_mev["USGOV10Y"]
    df_mev["USCORP_SPRD_AAA_T10"] = df_mev["USCORPAA10Y"] - df_mev["USGOV10Y"]
    df_mev["USCP_FF_SPRD"] = df_mev["USCPF"] - df_mev["USFF"]
    df_mev["USPRIME_FF_SPRD"] = df_mev["USPRIME"] - df_mev["USFF"]
    df_mev["USIORB_FF_SPRD"] = df_mev["USIORB"] - df_mev["USFF"]
    df_mev["USSOFR_FF_SPRD"] = df_mev["USSOFR"] - df_mev["USFF"]

    df_mev["USMORT30_T10_SPRD"] = df_mev["USMORT30Y"] - df_mev["USGOV10Y"]
    df_mev["USMORT15_T10_SPRD"] = df_mev["USMORT15Y"] - df_mev["USGOV10Y"]
    df_mev["USARM_T2_SPRD"] = df_mev["USAM51"] - df_mev["USGOV2Y"]
    df_mev["USMORT30_15_SPRD"] = df_mev["USMORT30Y"] - df_mev["USMORT15Y"]

    df_mev["USLIQ_M2_GDP"] = df_mev["USM2"] / df_mev["USNGDP"]
    df_mev["USLIQ_M1_M2"] = df_mev["USM1"] / df_mev["USM2"]
    df_mev["USCREDIT_CC_INC"] = df_mev["USCC"] / df_mev["USDI"]
    df_mev["USCREDIT_CC_GDP"] = df_mev["USCC"] / df_mev["USNGDP"]
    df_mev["USCONS_PCE_INC"] = df_mev["USNC"] / df_mev["USDI"]
    df_mev["USSAV_DLR"] = df_mev["USDI"] - df_mev["USNC"]

    df_mev["USPCE_IMPLICIT_DEF"] = df_mev["USNC"] / df_mev["USRC"]
    df_mev["USDPI_IMPLICIT_DEF"] = df_mev["USDI"] / df_mev["USRPDI"]
    df_mev["USRISKON_SPX_VIX"] = df_mev["USSP500"] / df_mev["USVIXA"]
    df_mev["USCRE_HOUS_REL"] = df_mev["USNCREIF"] / df_mev["USCSH"]
    df_mev["USCP_GDP_SHARE"] = df_mev["USCP"] / df_mev["USNGDP"]

    return df_mev, df_in


def demo_var_map_update() -> Dict[str, Dict[str, str]]:
    return {
        "USYC10_2": {"type": "rate", "category": "yield slope"},
        "USYC10_1": {"type": "rate", "category": "yield slope"},
        "USYC10_6M": {"type": "rate", "category": "yield slope"},
        "USYC30_10": {"type": "rate", "category": "yield slope"},
        "USYC5_2": {"type": "rate", "category": "yield slope"},
        "USREAL_TERM_PREM_PROXY": {"type": "rate", "category": "real rate spread"},
        "USCORP_SPRD_BAA_AAA": {"type": "rate", "category": "credit spread"},
        "USCORP_SPRD_BAA_T10": {"type": "rate", "category": "credit spread"},
        "USCORP_SPRD_AAA_T10": {"type": "rate", "category": "credit spread"},
        "USCP_FF_SPRD": {"type": "rate", "category": "funding spread"},
        "USPRIME_FF_SPRD": {"type": "rate", "category": "bank pricing spread"},
        "USIORB_FF_SPRD": {"type": "rate", "category": "policy spread"},
        "USSOFR_FF_SPRD": {"type": "rate", "category": "funding spread"},
        "USMORT30_T10_SPRD": {"type": "rate", "category": "mortgage spread"},
        "USMORT15_T10_SPRD": {"type": "rate", "category": "mortgage spread"},
        "USARM_T2_SPRD": {"type": "rate", "category": "mortgage spread"},
        "USMORT30_15_SPRD": {"type": "rate", "category": "mortgage spread"},
        "USLIQ_M2_GDP": {"type": "level", "category": "liquidity ratio"},
        "USLIQ_M1_M2": {"type": "level", "category": "liquidity ratio"},
        "USCREDIT_CC_INC": {"type": "level", "category": "leverage ratio"},
        "USCREDIT_CC_GDP": {"type": "level", "category": "leverage ratio"},
        "USCONS_PCE_INC": {"type": "level", "category": "consumption ratio"},
        "USSAV_DLR": {"type": "level", "category": "savings level"},
        "USPCE_IMPLICIT_DEF": {"type": "level", "category": "price level"},
        "USDPI_IMPLICIT_DEF": {"type": "level", "category": "price level"},
        "USRISKON_SPX_VIX": {"type": "level", "category": "risk appetite"},
        "USCRE_HOUS_REL": {"type": "level", "category": "relative valuation"},
        "USCP_GDP_SHARE": {"type": "level", "category": "income share"},
    }


def build_demo_segment():
    df_internal = pd.read_csv(_demo_data_path("housing_market.csv"))
    df_internal["home_price_GR1"] = df_internal["home_price_index"].pct_change().shift(-1)
    df_internal["home_price_GR3"] = df_internal["home_price_index"].pct_change(3).shift(-1)

    int_ldr = tc.TimeSeriesLoader(
        in_sample_start="2006-01-31",
        in_sample_end="2023-09-30",
        full_sample_end="2025-09-30",
        scen_p0="2023-09-30",
    )
    int_ldr.load(df_internal, date_col="date")

    df_mev_qtr = pd.read_csv(_demo_data_path("macro_quarterly.csv"))
    df_mev_mth = pd.read_csv(_demo_data_path("macro_monthly.csv"))
    df_mev_mth.ffill(inplace=True)

    df_scen_mev_qtr_base = pd.read_excel(_demo_data_path("macro_scenarios_quarterly.xlsx"), sheet_name="baseline").set_index("observation_date").ffill()
    df_scen_mev_qtr_adv = pd.read_excel(_demo_data_path("macro_scenarios_quarterly.xlsx"), sheet_name="adverse").set_index("observation_date").ffill()
    df_scen_mev_qtr_sev = pd.read_excel(_demo_data_path("macro_scenarios_quarterly.xlsx"), sheet_name="severely_adverse").set_index("observation_date").ffill()
    df_scen_mev_mth_base = pd.read_excel(_demo_data_path("macro_scenarios_monthly.xlsx"), sheet_name="baseline").set_index("observation_date").ffill()
    df_scen_mev_mth_adv = pd.read_excel(_demo_data_path("macro_scenarios_monthly.xlsx"), sheet_name="adverse").set_index("observation_date").ffill()
    df_scen_mev_mth_sev = pd.read_excel(_demo_data_path("macro_scenarios_monthly.xlsx"), sheet_name="severely_adverse").set_index("observation_date").ffill()

    mev_ldr = tc.MEVLoader()
    mev_ldr.load(source=df_mev_qtr, date_col="observation_date")
    mev_ldr.load(source=df_mev_mth, date_col="observation_date")
    mev_ldr.load_scens({"Base": df_scen_mev_qtr_base, "Adv": df_scen_mev_qtr_adv, "Sev": df_scen_mev_qtr_sev}, set_name="Scenario")
    mev_ldr.load_scens({"Base": df_scen_mev_mth_base, "Adv": df_scen_mev_mth_adv, "Sev": df_scen_mev_mth_sev}, set_name="Scenario")

    dm = tc.DataManager(int_ldr, mev_ldr)
    dm.apply_to_all(add_demo_features)
    dm.update_var_map(demo_var_map_update())

    return tc.Segment(
        segment_id=SEGMENT_ID,
        target=TARGET,
        model_type=tc.Growth,
        target_base=TARGET_BASE,
        data_manager=dm,
        model_cls=tc.OLS,
    )


def default_forced_in(use_seasonality: bool) -> List[Any]:
    if not use_seasonality:
        return []
    return [DumVar("M", categories=[2, 3, 4, 5, 10, 11, 12])]


def serialize_specs(specs: Sequence[Any]) -> List[str]:
    return [str(spec) for spec in specs]


def cm_summary(cm: Any) -> Dict[str, Any]:
    model = getattr(cm, "model_in", None) or getattr(cm, "model_full", None)
    metrics = {}
    if model is not None:
        for name in ("rsquared", "rsquared_adj", "aic", "bic"):
            value = getattr(model, name, None)
            if value is not None:
                metrics[name] = float(value)

    try:
        formula = cm.formula
    except Exception:
        formula = repr(cm)

    return {
        "model_id": getattr(cm, "model_id", None),
        "formula": formula,
        "specs": serialize_specs(getattr(cm, "specs", [])),
        "metrics": metrics,
    }


def run_fit_single(*, specs: Sequence[str], sample: str = "in") -> Dict[str, Any]:
    seg = build_demo_segment()
    cm = seg.build_cm("cm1", list(specs), sample=sample)
    return {
        "segment_id": seg.segment_id,
        "target": seg.target,
        "selected_models": [cm_summary(cm)],
    }


def run_search(
    *,
    desired_pool: Optional[Sequence[str]] = None,
    forced_in: Optional[List[Any]] = None,
    top_n: int = 5,
    max_var_num: int = 2,
    max_lag: int = 1,
    periods: Optional[Sequence[int]] = None,
    search_id: Optional[str] = None,
    modeltest_update_func: Optional[Callable[..., Dict[str, Any]]] = None,
    pilot_smoke: bool = False,
) -> Dict[str, Any]:
    seg = build_demo_segment()
    seg.working_dir = _repo_root()
    pool = list(desired_pool or DEFAULT_DRIVER_POOL)
    forced = forced_in or []
    seg.search_cms(
        desired_pool=pool,
        forced_in=forced,
        top_n=top_n,
        max_var_num=max_var_num,
        max_lag=max_lag,
        periods=periods,
        modeltest_update_func=modeltest_update_func,
        overwrite=True,
        search_id=search_id,
    )
    selected = [cm_summary(cm) for cm in seg.cms.values()]
    effective_search_id = seg.last_search_id
    artifacts_dir = _repo_root() / "Segment" / seg.segment_id / "cms" / effective_search_id
    return {
        "segment_id": seg.segment_id,
        "target": seg.target,
        "search_id": effective_search_id,
        "selected_models": selected,
        "selected_count": len(selected),
        "zero_selected_is_valid": True,
        "pilot_smoke": pilot_smoke,
        "artifacts_dir": str(artifacts_dir),
    }


def smoke_search_test_overrides() -> Dict[str, Any]:
    """Relax demo filters for a fast search-plumbing smoke test."""
    return {
        "Coefficient Significance": {"filter_on": False},
        "In-Sample R-sq": {"filter_on": False},
        "Multicollinearity": {"filter_on": False},
        "Residual Stationarity": {"filter_on": False},
        "Sign Check": {"filter_on": False},
    }


def run_search_smoke(*, search_id: Optional[str] = None) -> Dict[str, Any]:
    return run_search(
        desired_pool=["USMORT30Y"],
        forced_in=[],
        top_n=1,
        max_var_num=1,
        max_lag=0,
        periods=[1],
        search_id=search_id,
        modeltest_update_func=smoke_search_test_overrides,
        pilot_smoke=True,
    )
