from django.core.management.base import BaseCommand
from product_group.models import Product_Services, ProductGroup, Quote
from finances.models import Invoice


class Command(BaseCommand):
    help = 'Check product group memberships and quote items'

    def handle(self, *args, **options):
        # Check all product groups and their services
        self.stdout.write("=== PRODUCT GROUPS ===")
        for pg in ProductGroup.objects.all():
            services = Product_Services.objects.filter(product_group=pg)
            self.stdout.write(f"Group {pg.id}: {pg.product_group_name}")
            for svc in services:
                self.stdout.write(f"  - Service {svc.id}: {svc.product_service_name}")

        # Check specific quote (47)
        self.stdout.write("\n=== QUOTE 47 ITEMS ===")
        try:
            quote = Quote.objects.get(quote_no=47)
            items = quote.items.all()
            for item in items:
                pg_id = item.product_service.product_group_id if item.product_service.product_group else 'None'
                pg_name = item.product_service.product_group.product_group_name if item.product_service.product_group else 'None'
                self.stdout.write(
                    f"Item {item.id}: Service {item.product_service_id} ({item.product_service.product_service_name}) -> Group {pg_id} ({pg_name})"
                )
        except Quote.DoesNotExist:
            self.stdout.write("Quote 47 not found")

        # Check invoices for quote 47
        self.stdout.write("\n=== INVOICES FOR QUOTE 47 ===")
        invoices = Invoice.objects.filter(quote__quote_no=47)
        for inv in invoices:
            self.stdout.write(f"Invoice {inv.invoice_no} (id={inv.id}):")
            for item in inv.items.all():
                pg_id = item.product_service.product_group_id if item.product_service.product_group else 'None'
                self.stdout.write(
                    f"  - Service {item.product_service_id}: {item.product_service.product_service_name} (Group {pg_id})"
                )
