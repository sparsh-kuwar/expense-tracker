# Expense Tracker

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/sparsh-kuwar/expense-tracker)
Live: https://expense-tracker-1fwc.onrender.com
A Python (Django) web app for recording, categorising and analysing personal expenses.
It shows monthly spending trends, a category and payment-mode breakdown, and short
plain-language insights such as "Entertainment is up 170% this month compared with your
3-month average."

**Try it:** open the deployed app and click **Try the demo**. The demo account has 12 months
of sample data, so every chart has something to show.

## Features

- **Record expenses**: date, amount (₹), category, payment mode and description. You can add, edit and delete them.
- **Categorise**: 10 fixed categories (Food & Dining, Transport, Rent, Utilities, …) and 4 payment modes (Cash, UPI, Card, Net banking).
- **Search and filter**: by description, category and month, with pagination.
- **Export**: download the current filtered list as CSV.
- **Analysis** (`tracker/analytics.py`):
  - this month vs last month, with the percentage change
  - daily average and all-time total
  - 12-month spending trend, with empty months shown as zero
  - category share over the last 3 months
  - the category that grew most against its 3-month average
  - the largest single expense
- **Visualisation**: Chart.js bar charts for the monthly trend and payment modes, plus ranked category bars.
- **Accounts**: Django authentication with hashed passwords. Each user sees only their own data.

## Run locally

Requires Python 3.10 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo         # optional: creates the demo account
python manage.py runserver
```

Open http://127.0.0.1:8000.

## Tests

```sh
python manage.py test
```

There are 24 tests. They cover the analysis functions, input validation, per-user data isolation (one user cannot edit, delete or export another user's expenses), filters, CSV export, sign-up and the demo account.

## Deploy to Render

The repo includes a Render Blueprint (`render.yaml`) and a build script (`build.sh`).

1. Push this repo to GitHub.
2. In Render, choose **New → Blueprint** and select the repo.
3. Render installs dependencies, collects static files, runs migrations and creates the demo account. It also generates `SECRET_KEY` automatically.

**About storage:** by default the app uses SQLite. On Render's free plan the disk is reset when the service restarts or redeploys. Accounts you create disappear when that happens, but the demo account is recreated every time. For permanent data, create a PostgreSQL database and set its connection string as the `DATABASE_URL` environment variable. The app detects it automatically.

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Django secret key (required when `DEBUG` is off) | dev key when `DEBUG=True` |
| `DEBUG` | `True` for development | `True` |
| `DATABASE_URL` | PostgreSQL connection string | local SQLite file |

## Project layout

```
config/            Django settings and root URLs
tracker/
  models.py        Expense model (categories, payment modes)
  analytics.py     Spending analysis and insights
  views.py         Dashboard, CRUD, filters, CSV export, sign-up, demo login
  demo.py          Sample-data generator for the demo account
  templates/       Server-rendered pages
  static/          CSS
  tests.py         Test suite
build.sh           Render build step
render.yaml        Render Blueprint
```

## Tech stack

Python 3, Django 5.2, SQLite or PostgreSQL, Chart.js, WhiteNoise and Gunicorn.
