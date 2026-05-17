# Etsy Keyword Research SaaS MVP

This is a professional, production-ready MVP for an Etsy Keyword Research tool built with Django.

## Features
- **Real-time Scraping**: Fetches autocomplete suggestions and competition listing counts directly from Etsy.
- **Advanced Scoring**: Calculates an "Opportunity Score" based on estimated demand and competition.
- **Concurrent Execution**: Uses `ThreadPoolExecutor` to scrape multiple keywords simultaneously for fast results.
- **Professional Dashboard**: Built with Bootstrap 5, featuring a sidebar, real-time AJAX updates, and DataTables for sorting/filtering.
- **Caching**: Results are cached in the database (SQLite/PostgreSQL) to reduce scraping frequency.
- **Authentication**: Full user registration, login, and logout system.
- **Export**: Export research results to CSV for offline analysis.

## Tech Stack
- **Backend**: Django 4.2+
- **Frontend**: Bootstrap 5, jQuery, DataTables.js
- **Data Analysis**: Pandas
- **Scraping**: Requests, BeautifulSoup4

## Setup Instructions

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Migrations**:
   ```bash
   python manage.py makemigrations keywords
   python manage.py migrate
   ```

3. **Create Superuser (Optional)**:
   ```bash
   python manage.py createsuperuser
   ```

4. **Run the Server**:
   ```bash
   python manage.py runserver
   ```

5. **Access the App**:
   Navigate to `http://127.0.0.1:8000/`. Register a new account to access the dashboard.

## Opportunity Score Formula
`Opportunity Score = (Demand Score / Competition) * 100,000`

- **High Opportunity (Green)**: Score > 1,500
- **Moderate (Yellow)**: Score 500 - 1,500
- **Saturated (Red)**: Score < 500
