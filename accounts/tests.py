from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from keywords.models import User

from .models import ActivityLog, Notification, Role


class AccessTestBase(TestCase):
    def setUp(self):
        cache.clear()
        self.admin_role = Role.objects.get(slug='administrator')
        self.analyst_role = Role.objects.get(slug='analyst')
        self.admin = User.objects.create_user('boss', 'boss@example.com', 'S3cure-pass!', role=self.admin_role)
        self.analyst = User.objects.create_user('ana', 'ana@example.com', 'S3cure-pass!', role=self.analyst_role)


class AuthenticationTests(AccessTestBase):
    def test_login_with_username_and_email(self):
        for ident in ('ana', 'ana@example.com', 'ANA@example.com'):
            self.client.logout()
            r = self.client.post(reverse('login'), {'username': ident, 'password': 'S3cure-pass!', 'remember_me': 'on'})
            self.assertRedirects(r, reverse('overview'), fetch_redirect_response=False)
        self.assertTrue(ActivityLog.objects.filter(user=self.analyst, action='login').exists())

    def test_wrong_password_is_rejected_and_logged(self):
        r = self.client.post(reverse('login'), {'username': 'ana', 'password': 'nope'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Incorrect username/email or password')
        self.assertTrue(ActivityLog.objects.filter(action='login_failed').exists())

    def test_lockout_after_repeated_failures(self):
        for _ in range(5):
            self.client.post(reverse('login'), {'username': 'ana', 'password': 'nope'})
        r = self.client.post(reverse('login'), {'username': 'ana', 'password': 'S3cure-pass!'})
        self.assertContains(r, 'Too many failed attempts')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_user_cannot_login(self):
        self.analyst.is_active = False
        self.analyst.save()
        r = self.client.post(reverse('login'), {'username': 'ana', 'password': 'S3cure-pass!'})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(self.analyst)
        self.client.get(reverse('logout'))
        self.assertIn('_auth_user_id', self.client.session)
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_anonymous_is_redirected_to_login(self):
        r = self.client.get(reverse('overview'))
        self.assertRedirects(r, f"{reverse('login')}?next=/", fetch_redirect_response=False)

    def test_password_reset_flow_sends_email(self):
        r = self.client.post(reverse('password_reset'), {'email': 'ana@example.com'})
        self.assertRedirects(r, reverse('password_reset_done'), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/reset/', mail.outbox[0].body)


class RoleAccessTests(AccessTestBase):
    def test_module_access_follows_role(self):
        self.client.force_login(self.analyst)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('customer_detail:customer_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('accounts:user_list')).status_code, 403)

    def test_sidebar_only_lists_allowed_modules(self):
        self.client.force_login(self.analyst)
        html = self.client.get(reverse('overview')).content.decode()
        self.assertIn('CSV Analyzer', html)
        self.assertNotIn('Customer Hub', html)
        self.assertNotIn('Roles &amp; Permissions', html)

    def test_user_without_role_sees_no_modules(self):
        nobody = User.objects.create_user('nobody', 'n@example.com', 'S3cure-pass!')
        self.client.force_login(nobody)
        self.assertEqual(self.client.get(reverse('overview')).status_code, 403)
        self.assertEqual(self.client.get(reverse('accounts:profile')).status_code, 200)

    def test_superuser_bypasses_roles(self):
        root = User.objects.create_superuser('root', 'root@example.com', 'S3cure-pass!')
        self.client.force_login(root)
        self.assertEqual(self.client.get(reverse('customer_detail:customer_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('accounts:role_list')).status_code, 200)

    def test_role_change_takes_effect_immediately(self):
        self.client.force_login(self.analyst)
        self.assertEqual(self.client.get(reverse('customer_detail:customer_list')).status_code, 403)
        self.analyst_role.modules = self.analyst_role.modules + ['customers']
        self.analyst_role.save()
        self.assertEqual(self.client.get(reverse('customer_detail:customer_list')).status_code, 200)


class UserManagementTests(AccessTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_create_user_notifies_new_user(self):
        r = self.client.post(reverse('accounts:user_create'), {
            'username': 'newbie', 'email': 'newbie@example.com', 'first_name': 'New', 'last_name': 'Bie',
            'role': self.analyst_role.pk, 'is_active': 'on',
            'password1': 'An0ther-strong!', 'password2': 'An0ther-strong!',
        })
        self.assertRedirects(r, reverse('accounts:user_list'), fetch_redirect_response=False)
        newbie = User.objects.get(username='newbie')
        self.assertTrue(newbie.check_password('An0ther-strong!'))
        self.assertEqual(newbie.role, self.analyst_role)
        self.assertTrue(Notification.objects.filter(recipient=newbie, title='Welcome aboard!').exists())

    def test_duplicate_email_and_weak_password_rejected(self):
        r = self.client.post(reverse('accounts:user_create'), {
            'username': 'dup', 'email': 'ANA@example.com', 'role': self.analyst_role.pk,
            'password1': '123', 'password2': '123',
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username='dup').exists())
        self.assertContains(r, 'Another account already uses this email')

    def test_edit_role_notifies_user(self):
        data = {'username': 'ana', 'email': 'ana@example.com', 'role': self.admin_role.pk, 'is_active': 'on'}
        self.client.post(reverse('accounts:user_edit', args=[self.analyst.pk]), data)
        self.analyst.refresh_from_db()
        self.assertEqual(self.analyst.role, self.admin_role)
        self.assertTrue(self.analyst.check_password('S3cure-pass!'))  # blank password keeps the old one
        self.assertTrue(Notification.objects.filter(recipient=self.analyst, title='Your role changed').exists())

    def test_cannot_deactivate_or_delete_self(self):
        self.client.post(reverse('accounts:user_toggle_active', args=[self.admin.pk]))
        self.client.post(reverse('accounts:user_delete', args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_manager_cannot_touch_superuser(self):
        manager = User.objects.create_user('mgr', 'mgr@example.com', 'S3cure-pass!', role=Role.objects.get(slug='manager'))
        root = User.objects.create_superuser('root', 'root@example.com', 'S3cure-pass!')
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse('accounts:user_edit', args=[root.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('accounts:user_delete', args=[root.pk])).status_code, 403)
        self.assertTrue(User.objects.filter(pk=root.pk).exists())

    def test_toggle_and_delete(self):
        self.client.post(reverse('accounts:user_toggle_active', args=[self.analyst.pk]))
        self.analyst.refresh_from_db()
        self.assertFalse(self.analyst.is_active)
        self.client.post(reverse('accounts:user_delete', args=[self.analyst.pk]))
        self.assertFalse(User.objects.filter(pk=self.analyst.pk).exists())


class RoleManagementTests(AccessTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_create_role_with_modules(self):
        # An unknown module key rejects the whole form.
        r = self.client.post(reverse('accounts:role_create'), {
            'name': 'Designers', 'color': 'info', 'modules': ['mockups', 'not-a-module'],
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Role.objects.filter(name='Designers').exists())

        self.client.post(reverse('accounts:role_create'), {
            'name': 'Designers', 'description': 'Studio only', 'color': 'info', 'modules': ['mockups', 'profit'],
        })
        role = Role.objects.get(name='Designers')
        self.assertEqual(role.slug, 'designers')
        self.assertEqual(sorted(role.modules), ['mockups', 'profit'])

    def test_system_role_cannot_be_deleted(self):
        self.client.post(reverse('accounts:role_delete', args=[self.analyst_role.pk]))
        self.assertTrue(Role.objects.filter(pk=self.analyst_role.pk).exists())


class ProfileAndNotificationTests(AccessTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.analyst)

    def test_update_profile(self):
        self.client.post(reverse('accounts:profile'), {
            'action': 'profile', 'first_name': 'Ana', 'last_name': 'Lyst', 'email': 'ana@example.com',
            'phone': '123', 'job_title': 'Researcher',
        })
        self.analyst.refresh_from_db()
        self.assertEqual(self.analyst.display_name, 'Ana Lyst')

    def test_change_password_keeps_session(self):
        self.client.post(reverse('accounts:profile'), {
            'action': 'password', 'old_password': 'S3cure-pass!',
            'new_password1': 'Brand-new-pass9', 'new_password2': 'Brand-new-pass9',
        })
        self.analyst.refresh_from_db()
        self.assertTrue(self.analyst.check_password('Brand-new-pass9'))
        self.assertEqual(self.client.get(reverse('accounts:profile')).status_code, 200)

    def test_notifications_read_and_isolation(self):
        mine = Notification.objects.create(recipient=self.analyst, title='Hi', link='/saved/')
        theirs = Notification.objects.create(recipient=self.admin, title='Secret')
        r = self.client.get(reverse('accounts:notification_open', args=[mine.pk]))
        self.assertRedirects(r, '/saved/', fetch_redirect_response=False)
        mine.refresh_from_db()
        self.assertTrue(mine.is_read)
        self.assertEqual(self.client.get(reverse('accounts:notification_open', args=[theirs.pk])).status_code, 404)

    def test_mark_all_ignores_external_next(self):
        Notification.objects.create(recipient=self.analyst, title='A')
        r = self.client.post(reverse('accounts:notification_mark_all'), {'next': 'https://evil.example.com/'})
        self.assertRedirects(r, reverse('accounts:notifications'), fetch_redirect_response=False)
        self.assertFalse(self.analyst.notifications.filter(is_read=False).exists())
