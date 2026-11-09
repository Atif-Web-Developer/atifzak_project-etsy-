from django.db import migrations

from ebay_dropshipping.lists import TABLE_SOURCE_FIELDS, lists_from_flat


def fill(apps, schema_editor):
    """Existing products get their competitor / supplier tables from the single fields."""
    Product = apps.get_model('ebay_dropshipping', 'Product')
    for p in Product.objects.filter(competitors=[], suppliers=[]):
        comps, sups = lists_from_flat({f: getattr(p, f) for f in TABLE_SOURCE_FIELDS})
        if comps or sups:
            Product.objects.filter(pk=p.pk).update(competitors=comps, suppliers=sups)


class Migration(migrations.Migration):

    dependencies = [
        ('ebay_dropshipping', '0006_competitor_supplier_tables'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
