import os
import django
from django.db import connection

# Initialize Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'etsy_researcher.settings')
django.setup()

with connection.cursor() as cursor:
    # Disable foreign key constraints temporarily
    cursor.execute("PRAGMA foreign_keys = OFF;")
    
    # Delete all users
    cursor.execute("DELETE FROM keywords_user;")
    
    # Re-enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON;")

print("Successfully deleted all users using RAW SQL and bypassed constraints!")
