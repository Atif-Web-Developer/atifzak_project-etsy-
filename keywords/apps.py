from django.apps import AppConfig

class KeywordsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'keywords'

    def ready(self):
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if not User.objects.filter(username='admin@gmail.com').exists():
                User.objects.create_superuser('admin@gmail.com', 'admin@gmail.com', '123123123')
                print("=========================================")
                print("Default admin account seeded successfully!")
                print("Username: admin@gmail.com")
                print("Password: 123123123")
                print("=========================================")
        except Exception as e:
            pass
