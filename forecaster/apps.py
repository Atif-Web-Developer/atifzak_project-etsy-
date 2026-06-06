from django.apps import AppConfig


class ForecasterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'forecaster'

    def ready(self):
        import os
        import glob
        from django.db import connection
        from django.core.management import call_command
        
        # Check if column 'month' exists in 'forecaster_forecastevent'
        needs_migration = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA table_info(forecaster_forecastevent);")
                columns = [row[1] for row in cursor.fetchall()]
                if 'month' in columns:
                    needs_migration = False
        except Exception:
            pass
            
        if needs_migration:
            try:
                # 1. Drop existing tables and clear migration history
                with connection.cursor() as cursor:
                    cursor.execute("DROP TABLE IF EXISTS forecaster_forecasttaskprogress;")
                    cursor.execute("DROP TABLE IF EXISTS forecaster_forecastevent;")
                    cursor.execute("DELETE FROM django_migrations WHERE app = 'forecaster';")
                
                # 2. Delete old migration files to start fresh
                migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
                for f in glob.glob(os.path.join(migrations_dir, '*.py')):
                    if not f.endswith('__init__.py'):
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                
                # 3. Generate new migrations and run them
                call_command('makemigrations', 'forecaster')
                call_command('migrate', 'forecaster')
                print("Programmatic migrations for forecaster completed successfully!")
            except Exception as e:
                print(f"Error running programmatic migrations for forecaster: {e}")

