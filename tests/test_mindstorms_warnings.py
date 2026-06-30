from Mindstorms.warnings import summarize_warning_text


def test_summarize_warning_text_deduplicates_known_scenario_warnings():
    text = """
    apply_to_all(): No scenario internal data for Scenario/Sev; using main internal data as context.
    apply_to_all(): Scenario internal data for Scenario/Sev is unavailable; returned internal updates were ignored.
    apply_to_all(): No scenario internal data for Scenario/Base; using main internal data as context.
    apply_to_all(): Scenario internal data for Scenario/Base is unavailable; returned internal updates were ignored.
    """

    summaries = summarize_warning_text(text)

    by_code = {item["code"]: item for item in summaries}
    assert by_code["SCENARIO_INTERNAL_DATA_FALLBACK"]["count"] == 2
    assert by_code["SCENARIO_INTERNAL_DATA_FALLBACK"]["fatal"] is False
    assert by_code["SCENARIO_INTERNAL_DATA_FALLBACK"]["severity"] == "info"
    assert by_code["SCENARIO_INTERNAL_DATA_FALLBACK"]["scenarios"] == ["Base", "Sev"]
    assert by_code["SCENARIO_INTERNAL_UPDATES_SKIPPED"]["count"] == 2
