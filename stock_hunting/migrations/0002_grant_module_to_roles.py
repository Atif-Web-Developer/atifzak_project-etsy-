from django.db import migrations

ROLES = ['administrator', 'manager']


def grant(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(slug__in=ROLES):
        if 'stock' not in role.modules:
            role.modules = role.modules + ['stock']
            role.save(update_fields=['modules'])


def revoke(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(slug__in=ROLES):
        role.modules = [m for m in role.modules if m != 'stock']
        role.save(update_fields=['modules'])


class Migration(migrations.Migration):
    dependencies = [
        ('stock_hunting', '0001_initial'),
        ('accounts', '0002_default_roles'),
    ]

    operations = [migrations.RunPython(grant, revoke)]
