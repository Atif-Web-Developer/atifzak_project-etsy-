from django.db import migrations

RESEARCH = ['overview', 'analyzer', 'history', 'saved', 'rank_optimizer', 'keyword_bank',
            'competitors', 'forecaster', 'pinterest', 'profit', 'mockups']
OPERATIONS = ['overview', 'customers', 'suppliers', 'profit']
ALL = RESEARCH + ['customers', 'suppliers']

DEFAULT_ROLES = [
    {
        'name': 'Administrator', 'slug': 'administrator', 'color': 'danger', 'is_system': True,
        'description': 'Full access to every module, users, roles and the activity log.',
        'modules': ALL, 'can_manage_users': True, 'can_manage_roles': True, 'can_view_activity': True,
    },
    {
        'name': 'Manager', 'slug': 'manager', 'color': 'warning', 'is_system': True,
        'description': 'Every business module plus user management and activity log.',
        'modules': ALL, 'can_manage_users': True, 'can_manage_roles': False, 'can_view_activity': True,
    },
    {
        'name': 'Analyst', 'slug': 'analyst', 'color': 'info', 'is_system': True,
        'description': 'Keyword research, market intelligence and studio tools.',
        'modules': RESEARCH, 'can_manage_users': False, 'can_manage_roles': False, 'can_view_activity': False,
    },
    {
        'name': 'Operations', 'slug': 'operations', 'color': 'secondary', 'is_system': False,
        'description': 'Customers, suppliers and the profit calculator.',
        'modules': OPERATIONS, 'can_manage_users': False, 'can_manage_roles': False, 'can_view_activity': False,
    },
]


def create_roles(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    User = apps.get_model('keywords', 'User')
    roles = {}
    for data in DEFAULT_ROLES:
        role, _ = Role.objects.update_or_create(slug=data['slug'], defaults=data)
        roles[data['slug']] = role
    User.objects.filter(role__isnull=True, is_superuser=True).update(role=roles['administrator'])
    User.objects.filter(role__isnull=True, is_superuser=False).update(role=roles['analyst'])


def remove_roles(apps, schema_editor):
    apps.get_model('accounts', 'Role').objects.filter(slug__in=[r['slug'] for r in DEFAULT_ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
        ('keywords', '0006_user_avatar_user_job_title_user_phone_user_role_and_more'),
    ]

    operations = [migrations.RunPython(create_roles, remove_roles)]
