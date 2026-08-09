from arcitek_core.build_validation import validate_repository


def test_validate_repository_reports_syntax_errors(tmp_path):
    repo_dir = tmp_path / "repo"
    core_dir = repo_dir / "arcitek_core"
    core_dir.mkdir(parents=True)
    (core_dir / "__init__.py").write_text("from .precision_builder import PrecisionBuilder\n", encoding="utf-8")
    (core_dir / "precision_builder.py").write_text("class PrecisionBuilder:\n    pass\n", encoding="utf-8")
    (core_dir / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    (repo_dir / "package.json").write_text('{"name": "demo", "version": "1.0.0"}\n', encoding="utf-8")

    report = validate_repository(repo_dir)

    assert not report.is_valid()
    assert any(finding.category == "syntax" for finding in report.findings)
    assert "Todo checklist:" in report.render()
    assert "Please address the following validation findings" in report.corrective_prompt()


def test_validate_repository_passes_for_clean_repo(tmp_path):
    repo_dir = tmp_path / "repo"
    core_dir = repo_dir / "arcitek_core"
    core_dir.mkdir(parents=True)
    (core_dir / "__init__.py").write_text("from .precision_builder import PrecisionBuilder\n", encoding="utf-8")
    (core_dir / "precision_builder.py").write_text("class PrecisionBuilder:\n    pass\n", encoding="utf-8")
    (repo_dir / "package.json").write_text('{"name": "demo", "version": "1.0.0"}\n', encoding="utf-8")

    report = validate_repository(repo_dir)

    assert report.is_valid()
    assert "No validation issues detected" in report.render()
