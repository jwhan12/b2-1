import csv
import tempfile
import unittest
from pathlib import Path

from budget_app.errors import AppError
from budget_app.repositories import Storage
from budget_app.services import BudgetService, CSV_COLUMNS


class CsvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.service = BudgetService(Storage(self.root / "data"))

    def test_import_partial_success_and_csv_round_trip(self) -> None:
        source = self.root / "input.csv"
        with source.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.writer(destination)
            writer.writerow(CSV_COLUMNS)
            writer.writerow(("2024-01-15", "expense", "food", "15000", '점심, "특식"\n다음 줄', "meal,work"))
            writer.writerow(("2024-02-30", "expense", "food", "10", "오류", ""))
            writer.writerow(("2024-01-16", "income", "salary", "30000", "", ""))
        errors: list[tuple[int, AppError]] = []
        result = self.service.import_csv(source, lambda line, error: errors.append((line, error)))
        self.assertEqual((result.imported, result.skipped), (2, 1))
        self.assertEqual(errors[0][0], 4)
        output = self.root / "output.csv"
        self.assertEqual(self.service.export_csv(output, month="2024-01"), 2)
        with output.open("r", encoding="utf-8", newline="") as exported:
            rows = list(csv.DictReader(exported))
        self.assertEqual(rows[0]["memo"], '점심, "특식"\n다음 줄')
        self.assertEqual(rows[0]["tags"], "meal,work")
        self.assertEqual(rows[1]["type"], "income")

    def test_minimal_columns_and_bad_header(self) -> None:
        source = self.root / "minimal.csv"
        source.write_text("date,type,category,amount\n2024-01-01,expense,food,7\n", encoding="utf-8")
        result = self.service.import_csv(source, lambda *_: self.fail("unexpected invalid row"))
        self.assertEqual(result.imported, 1)
        self.assertEqual(self.service.list_transactions()[0].memo, "")
        source.write_text("date,type,amount\n2024-01-01,expense,7\n", encoding="utf-8")
        with self.assertRaises(AppError) as raised:
            self.service.import_csv(source, lambda *_: None)
        self.assertIn("헤더", raised.exception.message)

    def test_fatal_csv_structure_keeps_imported_rows_and_reports_counts(self) -> None:
        source = self.root / "broken.csv"
        source.write_text(
            'date,type,category,amount\n2024-01-01,expense,food,7\n"unclosed,expense,food,8\n',
            encoding="utf-8",
        )
        with self.assertRaises(AppError) as raised:
            self.service.import_csv(source, lambda *_: None)
        self.assertIn("imported=1, skipped=0", raised.exception.message)
        self.assertEqual(len(self.service.list_transactions()), 1)

    def test_export_requires_one_complete_filter(self) -> None:
        output = self.root / "output.csv"
        for kwargs in ({}, {"date_from": "2024-01-01"}, {"month": "2024-01", "date_to": "2024-01-31"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(AppError):
                self.service.export_csv(output, **kwargs)
        self.assertEqual(self.service.export_csv(output, date_from="2024-01-01", date_to="2024-01-31"), 0)
        self.assertEqual(output.read_text(encoding="utf-8").strip(), ",".join(CSV_COLUMNS))
