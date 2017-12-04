import six
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase
from django.core import mail
from datetime import date
from django.utils.timezone import datetime
from hordak.models.core import StatementImport, Account, StatementLine
from pytz import UTC
from swiftwind.utilities.testing import DataProvider

from .cycles import Monthly
from .models import BillingCycle


class BillingCycleConstraintTestCase(TransactionTestCase):

    def test_constraint_non_overlapping(self):
        BillingCycle.objects.create(
            date_range=(date(2016, 1, 1), date(2016, 2, 1))
        )
        with self.assertRaises(IntegrityError):
            BillingCycle.objects.create(
                date_range=(date(2016, 1, 25), date(2016, 2, 25))
            )

    def test_constraint_adjacent(self):
        BillingCycle.objects.create(
            date_range=(date(2016, 1, 1), date(2016, 2, 1))
        )
        with self.assertRaises(IntegrityError):
            BillingCycle.objects.create(
                date_range=(date(2016, 2, 2), date(2016, 3, 1))
            )

    def test_constraint_ok(self):
        BillingCycle.objects.create(
            date_range=(date(2016, 1, 1), date(2016, 2, 1))
        )
        BillingCycle.objects.create(
            date_range=(date(2016, 2, 1), date(2016, 3, 1))
        )
        # No errors


class BillingCycleTestCase(DataProvider, TransactionTestCase):

    def test_populate_no_cycles(self):
        with self.settings(SWIFTWIND_BILLING_CYCLE_YEARS=2):
            BillingCycle._populate(as_of=date(2016, 6, 1), delete=False)

        self.assertEqual(BillingCycle.objects.count(), 25)

        first = BillingCycle.objects.first()
        last = BillingCycle.objects.last()
        self.assertEqual(first.date_range.lower, date(2016, 6, 1))
        self.assertEqual(last.date_range.lower, date(2018, 6, 1))

    def test_populate_update_only(self):
        cycle1 = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))  # keep
        cycle2 = BillingCycle.objects.create(date_range=(date(2016, 5, 1), date(2016, 6, 1)))  # keep
        cycle3 = BillingCycle.objects.create(date_range=(date(2016, 6, 1), date(2016, 7, 1)))  # keep
        cycle4 = BillingCycle.objects.create(date_range=(date(2016, 7, 1), date(2016, 8, 1)))  # keep

        with self.settings(SWIFTWIND_BILLING_CYCLE_YEARS=2):
            BillingCycle._populate(as_of=date(2016, 6, 1), delete=False)

        # 4 previous cycles kept, 1 not created, and 24 new ones created
        self.assertEqual(BillingCycle.objects.count(), 4 + 23)

        first = BillingCycle.objects.first()
        last = BillingCycle.objects.last()
        self.assertEqual(first.date_range.lower, date(2016, 4, 1))
        self.assertEqual(last.date_range.lower, date(2018, 6, 1))

        self.assertIn(cycle1, BillingCycle.objects.all())
        self.assertIn(cycle2, BillingCycle.objects.all())
        self.assertIn(cycle3, BillingCycle.objects.all())
        self.assertIn(cycle4, BillingCycle.objects.all())

    def test_populate_delete(self):
        """Check that future billing cycles get deleted and recreated"""
        cycle1 = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))  # keep
        cycle2 = BillingCycle.objects.create(date_range=(date(2016, 5, 1), date(2016, 6, 1)))  # keep
        cycle3 = BillingCycle.objects.create(date_range=(date(2016, 6, 1), date(2016, 7, 1)))  # keep
        cycle4 = BillingCycle.objects.create(date_range=(date(2016, 7, 1), date(2016, 8, 1)))  # delete

        with self.settings(SWIFTWIND_BILLING_CYCLE_YEARS=2):
            BillingCycle._populate(as_of=date(2016, 6, 15), delete=True)

        # 3 previous cycles kept, and 24 new ones created
        self.assertEqual(BillingCycle.objects.filter(start_date__gte=date(2016, 7, 1)).count(), 24)

        first = BillingCycle.objects.first()
        last = BillingCycle.objects.last()
        self.assertEqual(first.date_range.lower, date(2016, 4, 1))
        self.assertEqual(last.date_range.lower, date(2018, 6, 1))

        self.assertIn(cycle1, BillingCycle.objects.all())
        self.assertIn(cycle2, BillingCycle.objects.all())
        self.assertIn(cycle3, BillingCycle.objects.all())
        self.assertNotIn(cycle4, BillingCycle.objects.all())

    def test_is_reconciled_true(self):
        bank = self.account(name='Bank', type=Account.TYPES.asset)
        other_account = self.account()
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        statement_import = StatementImport.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            bank_account=bank
        )
        statement_line = StatementLine.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            date=date(2016, 4, 10),
            statement_import=statement_import,
            amount=10,
        )
        statement_line.create_transaction(to_account=other_account)

        self.assertTrue(billing_cycle.is_reconciled())

    def test_is_reconciled_no_statement_lines(self):
        bank = self.account(name='Bank', type=Account.TYPES.asset)
        other_account = self.account()
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        statement_import = StatementImport.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            bank_account=bank
        )

        self.assertTrue(billing_cycle.is_reconciled())

    def test_is_reconciled_no_transaction(self):
        bank = self.account(name='Bank', type=Account.TYPES.asset)
        other_account = self.account()
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        statement_import = StatementImport.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            bank_account=bank
        )
        statement_line = StatementLine.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            date=date(2016, 4, 10),
            statement_import=statement_import,
            amount=10,
        )
        # No transaction created

        self.assertFalse(billing_cycle.is_reconciled())

    def test_is_reconciled_old_import(self):
        bank = self.account(name='Bank', type=Account.TYPES.asset)
        other_account = self.account()
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        statement_import = StatementImport.objects.create(
            timestamp=datetime(2016, 4, 25, 9, 30, 00, tzinfo=UTC),
            bank_account=bank
        )
        statement_line = StatementLine.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            date=date(2016, 4, 10),
            statement_import=statement_import,
            amount=10,
        )
        # No transaction created

        self.assertFalse(billing_cycle.is_reconciled())

    def test_send_reconciliation_required(self):
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        self.housemate(user_kwargs=dict(email='user@example.com'))
        billing_cycle.send_reconciliation_required()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].recipients(), ['user@example.com'])
        content, mime = mail.outbox[0].alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('<html', content)

    def test_send_statements(self):
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        self.housemate(user_kwargs=dict(email='user@example.com'))
        billing_cycle.send_statements(force=True)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].recipients(), ['user@example.com'])
        content, mime = mail.outbox[0].alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('<html', content)


class CycleTestCase(TestCase):

    def test_monthly_get_previous_cycle_start_date(self):
        cycle = Monthly()

        self.assertEqual(
            cycle.get_previous_cycle_start_date(date(2016, 6, 15), inclusive=True),
            date(2016, 6, 1)
        )
        self.assertEqual(
            cycle.get_previous_cycle_start_date(date(2016, 6, 1), inclusive=True),
            date(2016, 6, 1)
        )

    def test_monthly_get_next_cycle_start_date(self):
        cycle = Monthly()

        self.assertEqual(
            cycle.get_next_cycle_start_date(date(2016, 6, 15), inclusive=True),
            date(2016, 7, 1)
        )
        self.assertEqual(
            cycle.get_next_cycle_start_date(date(2016, 6, 1), inclusive=True),
            date(2016, 6, 1)
        )

    def test_monthly_get_cycle_end_date(self):
        cycle = Monthly()

        self.assertEqual(
            cycle.get_cycle_end_date(date(2016, 6, 15)),
            date(2016, 7, 1)
        )
        self.assertEqual(
            cycle.get_cycle_end_date(date(2016, 6, 1)),
            date(2016, 7, 1)
        )

    def test_monthly_generate_date_ranges(self):
        cycle = Monthly()

        ranges = cycle.generate_date_ranges(date(2016, 10, 15))
        self.assertEqual(six.next(ranges), (date(2016, 10, 1), date(2016, 11, 1)))  # starts in Oct
        self.assertEqual(six.next(ranges), (date(2016, 11, 1), date(2016, 12, 1)))
        self.assertEqual(six.next(ranges), (date(2016, 12, 1), date(2017, 1, 1)))

    def test_monthly_generate_date_ranges_omit_current(self):
        cycle = Monthly()

        ranges = cycle.generate_date_ranges(date(2016, 10, 15), omit_current=True)
        self.assertEqual(six.next(ranges), (date(2016, 11, 1), date(2016, 12, 1)))  # starts in Nov
        self.assertEqual(six.next(ranges), (date(2016, 12, 1), date(2017, 1, 1)))
        self.assertEqual(six.next(ranges), (date(2017, 1, 1), date(2017, 2, 1)))
