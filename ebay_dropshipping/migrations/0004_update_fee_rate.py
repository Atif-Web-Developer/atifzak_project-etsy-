from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def bump_rate(apps, schema_editor):
    """eBay's rate for most categories went from 13.25% to 13.6% (Feb 2025). Only the untouched default changes."""
    DropshipSettings = apps.get_model('ebay_dropshipping', 'DropshipSettings')
    for conf in DropshipSettings.objects.filter(ebay_fee_pct=Decimal('13.25')):
        conf.ebay_fee_pct = Decimal('13.60')
        conf.fees_updated_at = timezone.now()  # newer than the sheet → next sync sends it there
        conf.save(update_fields=['ebay_fee_pct', 'fees_updated_at'])


class Migration(migrations.Migration):
    dependencies = [('ebay_dropshipping', '0003_fee_rules_and_my_shipping')]

    operations = [migrations.RunPython(bump_rate, migrations.RunPython.noop)]
