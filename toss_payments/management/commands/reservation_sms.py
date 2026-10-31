from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from toss_payments.models import PaymentOrder
from toss_payments.sms import send_paid_order_sms, sync_sms_status


class Command(BaseCommand):
    help = "Explicitly retry a failed/disabled reservation SMS, or query an accepted message."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=("retry", "sync"))
        parser.add_argument("order_number")
        parser.add_argument("--dry-run", action="store_true", help="Check eligibility without API calls or database updates.")

    def handle(self, *args, **options):
        try:
            order = PaymentOrder.objects.get(order_number=options["order_number"])
        except PaymentOrder.DoesNotExist:
            raise CommandError("Order not found.")
        if options["action"] == "retry":
            if order.status != PaymentOrder.Status.PAID:
                raise CommandError("Only paid orders can be retried. No request sent.")
            if order.sms_status not in (PaymentOrder.SMSStatus.DISABLED, PaymentOrder.SMSStatus.FAILED):
                raise CommandError(f"SMS status {order.sms_status} cannot be retried. No request sent.")
            if not (order.payment_key and order.payment_completed_at and order.customer_phone
                    and order.consulting_date and order.consulting_time):
                raise CommandError("Required payment or reservation data is missing. No request sent.")
            if not settings.SOLAPI_SMS_ENABLED:
                raise CommandError("SOLAPI_SMS_ENABLED is false in this process. No request sent.")
            if options["dry_run"]:
                self.stdout.write("Retry eligible; dry run only. No API call or database update performed.")
                return
            send_paid_order_sms(order, retry=True)
        else:
            if options["dry_run"]:
                self.stdout.write(f"SMS status: {order.sms_status}; dry run only. No API call performed.")
                return
            sync_sms_status(order)
        order.refresh_from_db()
        self.stdout.write(f"SMS status: {order.sms_status}")
