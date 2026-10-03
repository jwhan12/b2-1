import tempfile
import unittest
from pathlib import Path

from budget_app.errors import AppError
from budget_app.repositories import Storage
from budget_app.services import BudgetService


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.service = BudgetService(Storage(Path(self.folder.name)))

    def test_list_search_and_update_preserve_registration_order(self) -> None:
        older = self.service.add_transaction("2024-01-01", "expense", "food", 10, "점심", "meal")
        first_same_day = self.service.add_transaction("2024-01-15", "expense", "food", 20, "점심 A", "meal")
        second_same_day = self.service.add_transaction("2024-01-15", "expense", "food", 30, "점심 B", "meal")
        self.assertEqual(
            [tx.id for tx in self.service.list_transactions(2)],
            [second_same_day.id, first_same_day.id],
        )
        matches = list(
            self.service.search_transactions(
                date_from="2024-01-15",
                date_to="2024-01-15",
                category="food",
                transaction_type="expense",
                query="점심",
                tag="meal",
            )
        )
        self.assertEqual([tx.id for tx in matches], [second_same_day.id, first_same_day.id])
        self.service.update_transaction(first_same_day.id, memo="", tags="", amount="25")
        updated = self.service.list_transactions(3)
        self.assertEqual([tx.id for tx in updated], [second_same_day.id, first_same_day.id, older.id])
        self.assertEqual((updated[1].memo, updated[1].tags, updated[1].amount), ("", [], 25))
        self.service.delete_transaction(second_same_day.id)
        self.assertEqual([tx.id for tx in self.service.list_transactions()], [first_same_day.id, older.id])

    def test_search_beyond_one_batch(self) -> None:
        for number in range(260):
            self.service.add_transaction("2024-01-15", "expense", "food", number + 1)
        results = list(self.service.search_transactions(tag=None))
        self.assertEqual(len(results), 260)
        self.assertEqual(results[0].amount, 260)
        self.assertEqual(results[-1].amount, 1)

    def test_summary_budget_and_category_rules(self) -> None:
        self.service.add_transaction("2024-01-15", "income", "salary", 300)
        self.service.add_transaction("2024-01-16", "expense", "food", 50)
        self.service.add_transaction("2024-01-17", "expense", "transport", 50)
        self.service.set_budget("2024-01", 100)
        summary = self.service.month_summary("2024-01", top=2)
        self.assertEqual((summary.income, summary.expense, summary.balance), (300, 100, 200))
        self.assertEqual(summary.category_expenses, [("food", 50), ("transport", 50)])
        self.assertEqual(summary.budget, 100)
        self.assertEqual(self.service.month_summary("2024-02").count, 0)
        with self.assertRaises(AppError):
            self.service.remove_category("food")
        self.assertEqual(self.service.add_category("gift"), "gift")
        with self.assertRaises(AppError):
            self.service.add_category("gift")
        self.assertEqual(self.service.remove_category("gift"), "gift")

    def test_validation_rejects_invalid_input(self) -> None:
        cases = (
            ("2024-02-30", "expense", "food", 10),
            ("2024-01-01", "other", "food", 10),
            ("2024-01-01", "expense", "missing", 10),
            ("2024-01-01", "expense", "food", 0),
            ("2024-01-01", "expense", "food", -1),
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(AppError):
                self.service.add_transaction(*values)
        with self.assertRaises(AppError):
            list(self.service.search_transactions(date_from="2024-02-01", date_to="2024-01-01"))
        with self.assertRaises(AppError):
            self.service.update_transaction("missing")

