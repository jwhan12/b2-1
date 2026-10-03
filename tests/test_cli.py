import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from budget_app.cli import build_parser, run_cli


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.data_dir = self.root / "data"

    def invoke(self, *arguments: str, answers: list[str] | None = None) -> tuple[int, str, str]:
        output = io.StringIO()
        errors = io.StringIO()
        with (
            patch("builtins.input", side_effect=answers or []),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
        ):
            status = run_cli([*arguments, "--data-dir", str(self.data_dir)])
        return status, output.getvalue(), errors.getvalue()

    def test_add_reprompts_and_persists(self) -> None:
        status, output, errors = self.invoke(
            "add",
            answers=["2024-13-40", "2024-01-15", "expense", "food", "0", "15000", "점심", "meal"],
        )
        self.assertEqual(status, 0)
        self.assertIn("[저장 완료] id=TX-", output)
        self.assertIn("[오류]", errors)
        self.assertIn("[힌트]", errors)
        status, output, _ = self.invoke("list", "--limit", "1")
        self.assertEqual(status, 0)
        self.assertIn("점심", output)

    def test_budget_summary_and_error_status(self) -> None:
        status, _, _ = self.invoke("budget", "set", "--month", "2024-01", "--amount", "100")
        self.assertEqual(status, 0)
        self.invoke("add", answers=["2024-01-15", "expense", "food", "120", "점심", ""])
        status, output, _ = self.invoke("summary", "--month", "2024-01")
        self.assertEqual(status, 0)
        self.assertIn("사용률 120.0%", output)
        self.assertIn("[경고]", output)
        status, _, errors = self.invoke("delete", "--id", "missing")
        self.assertEqual(status, 1)
        self.assertIn("[힌트]", errors)
        self.assertNotIn("Traceback", errors)

    def test_budget_boundary_and_empty_month(self) -> None:
        self.invoke("budget", "set", "--month", "2024-02", "--amount", "100")
        status, output, _ = self.invoke("summary", "--month", "2024-02")
        self.assertEqual(status, 0)
        self.assertIn("데이터 없음", output)
        self.assertIn("사용률 0.0%", output)
        self.invoke("add", answers=["2024-02-01", "expense", "food", "50", "", ""])
        status, output, _ = self.invoke("summary", "--month", "2024-02")
        self.assertEqual(status, 0)
        self.assertIn("사용률 50.0%", output)
        self.assertNotIn("[경고]", output)
        self.invoke("add", answers=["2024-02-02", "expense", "food", "50", "", ""])
        status, output, _ = self.invoke("summary", "--month", "2024-02")
        self.assertEqual(status, 0)
        self.assertIn("사용률 100.0%", output)
        self.assertNotIn("[경고]", output)

    def test_import_skipped_row_returns_one(self) -> None:
        source = self.root / "input.csv"
        source.write_text(
            "date,type,category,amount\n2024-01-01,expense,food,10\n2024-02-30,expense,food,9\n",
            encoding="utf-8",
        )
        status, output, errors = self.invoke("import", "--from", str(source))
        self.assertEqual(status, 1)
        self.assertIn("imported=1, skipped=1", output)
        self.assertIn("CSV 3행", errors)
        self.assertNotIn("Traceback", errors)

    def test_all_help_paths_and_argument_error(self) -> None:
        parser = build_parser()
        paths = (
            (), ("add",), ("list",), ("search",), ("update",), ("delete",),
            ("summary",), ("budget",), ("budget", "set"), ("budget", "show"),
            ("category",), ("category", "add"), ("category", "list"),
            ("category", "remove"), ("import",), ("export",),
        )
        for path in paths:
            with self.subTest(path=path), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    parser.parse_args([*path, "--help"])
                self.assertEqual(raised.exception.code, 0)
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as raised:
                run_cli(["delete"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("[힌트]", errors.getvalue())

    def test_corrupt_jsonl_reports_error_without_traceback(self) -> None:
        self.data_dir.mkdir()
        (self.data_dir / "transactions.jsonl").write_text("{broken\n", encoding="utf-8")
        status, _, errors = self.invoke("list")
        self.assertEqual(status, 1)
        self.assertIn("transactions.jsonl 1행", errors)
        self.assertIn("[힌트]", errors)
        self.assertNotIn("Traceback", errors)
