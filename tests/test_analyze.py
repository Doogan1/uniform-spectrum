from py import analyze, driver


def test_print_summary_reports_counts(tmp_path, capsys):
    db_path = tmp_path / "order4.sqlite"
    driver.run(4, db_path)

    analyze.print_summary(db_path)

    out = capsys.readouterr().out
    assert "Order 4" in out
    assert "status: complete" in out
    assert "graphs_checked: 11" in out
    assert "violations: 0" in out
