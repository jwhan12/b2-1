import json
import tempfile
import unittest
from pathlib import Path

from budget_app.errors import AppError
from budget_app.repositories import DEFAULT_CATEGORIES, Storage
from budget_app.services import BudgetService


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.data_dir = Path(self.folder.name) / "nested" / "data"
        self.storage = Storage(self.data_dir)
        self.service = BudgetService(self.storage)

    def test_three_files_created_and_data_survives_restart(self) -> None:
        self.assertEqual(
            sorted(path.name for path in self.data_dir.iterdir()),
            ["budgets.jsonl", "categories.jsonl", "transactions.jsonl"],
        )
        self.assertEqual(self.storage.categories.list_names(), list(DEFAULT_CATEGORIES))
        transaction = self.service.add_transaction("2024-01-15", "expense", "food", 15000)
        self.service.set_budget("2024-01", 500000)
        restarted = Storage(self.data_dir)
        self.assertEqual(next(restarted.transactions.iter_transactions())[1].id, transaction.id)
        self.assertEqual(restarted.budgets.list_budgets()["2024-01"], 500000)

    def test_generator_reads_one_record_at_a_time(self) -> None:
        first = self.service.add_transaction("2024-01-01", "expense", "food", 10)
        path = self.storage.transactions.path
        with path.open("a", encoding="utf-8") as destination:
            destination.write("{broken JSON\n")
        stream = self.storage.transactions.iter_transactions()
        self.assertEqual(next(stream)[1].id, first.id)
        with self.assertRaises(AppError):
            next(stream)

    def test_failed_rewrite_does_not_change_file(self) -> None:
        self.service.add_transaction("2024-01-01", "expense", "food", 10)
        original = self.storage.transactions.path.read_bytes()
        with self.assertRaises(AppError):
            self.service.delete_transaction("missing")
        self.assertEqual(self.storage.transactions.path.read_bytes(), original)

    def test_corrupt_budget_has_source_hint(self) -> None:
        self.storage.budgets.path.write_text(json.dumps({"month": "2024-13", "amount": 10}) + "\n", encoding="utf-8")
        with self.assertRaises(AppError) as raised:
            self.service.month_summary("2024-01")
        self.assertIn("1행", raised.exception.message)
        self.assertIn("해당 행", raised.exception.hint)

