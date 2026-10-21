from scripts.waivers_job import publish_waiver_report


def test_publish_waiver_report_writes_latest_and_archive(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    source = reports / "waivers_2026-10-21.md"
    source.write_text("# Waivers\n", encoding="utf-8")

    latest = publish_waiver_report(tmp_path, "2026-10-21")

    assert latest.read_text(encoding="utf-8") == "# Waivers\n"
    assert (
        reports / "waivers/waivers_2026-10-21.md"
    ).read_text(encoding="utf-8") == "# Waivers\n"
