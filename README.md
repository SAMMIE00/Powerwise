# PowerWise

PowerWise is a production-ready, multi-user Flask web application designed for Nigerian prepaid-meter households and energy-conscious users to monitor electricity consumption, compare appliance costs, simulate Nigerian electricity tariff bands, and receive tailored energy-saving insights.

---

## Features

- **Multi-User Account Architecture**: Complete user authentication, secure session handling, and strict per-user data isolation.
- **Transparent Glassmorphic Interface**: High-fidelity frosted-glass login and registration interface fully compatible with light and dark themes.
- **Accurate Tariff Band Modeling**: Full persistence for Nigerian NERC electricity tariff bands:
  - Band A: ₦209.50 / kWh
  - Band B: ₦62.48 / kWh
  - Band C: ₦50.00 / kWh
  - Band D: ₦43.00 / kWh
  - Band E: ₦40.00 / kWh
  - Custom user rates
- **Dynamic Dashboard**: Monthly and daily kWh estimates, bill projection, top energy user rankings, and interactive consumption share visualization.
- **Complete Appliance CRUD**: Add, edit, rank, and delete appliances, with duplicate merging and batch clearing.
- **Personalized Savings Engine**: Automatically calculates actionable monthly cost reductions from cutting runtime on your highest-consuming appliances.
- **Usage Reports & Chart.js Visualizations**: Historical consumption logging, printable reports, and dynamic charts.
- **Serverless & Vercel Ready**: Ready for serverless deployment with external PostgreSQL (e.g. Neon) and SQLite for local development.

---

## Tech Stack

- **Backend**: Python 3.12+, Flask 3.1
- **Database / ORM**: SQLAlchemy & Flask-SQLAlchemy (PostgreSQL in production, SQLite in development)
- **Authentication**: Werkzeug secure password hashing (`scrypt`/`pbkdf2`), signed HTTP-only sessions, and brute-force rate limiting
- **Frontend**: Jinja2 templates, CSS custom properties, vanilla JS, Chart.js
- **Testing**: pytest (comprehensive test coverage across calculations, models, and routes)
- **Deployment**: Vercel Serverless Python (`@vercel/python`)

---

## Project Structure

```text
Powerwise/
├── api/
│   └── index.py            # Vercel serverless entrypoint
├── app.py                  # Main Flask application and calculation engine
├── auth.py                 # Authentication blueprint & access control
├── models.py               # SQLAlchemy models (User, Appliance, Settings, History)
├── manage.py               # CLI management utility (init-db, create-admin, etc.)
├── migrate_json.py         # Migration utility for legacy JSON data
├── vercel.json             # Vercel deployment and routing configuration
├── requirements.txt        # Production dependencies
├── .env.example            # Environment variables template
├── .gitignore              # Repository exclusions
├── Templates/              # Jinja2 HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── appliances.html
│   ├── calculator.html
│   ├── edit_appliance.html
│   ├── login.html
│   ├── register.html
│   ├── reports.html
│   └── savings.html
├── static/                 # CSS stylesheets, SVG assets, and reports.js
└── tests/
    └── test_app.py         # Automated pytest test suite
```

---

## Local Development Setup

### 1. Clone & activate virtual environment

```bash
git clone https://github.com/SAMMIE00/Powerwise.git
cd Powerwise
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` as needed:
```ini
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secure-random-secret-key
DATABASE_URL=sqlite:///powerwise.db
SESSION_COOKIE_SECURE=False
```

### 4. Initialize database and provision admin

```bash
python manage.py init-db
python manage.py create-admin --username admin --email admin@powerwise.ng --password "YourAdminPassword123!"
```

*(Optional)* If you have legacy data in `user_appliances.json`:
```bash
python manage.py migrate-json --username admin --file user_appliances.json
```

### 5. Run tests

```bash
pytest tests/ -v
```

### 6. Start the development server

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) and sign in.

---

## Vercel Deployment Instructions

PowerWise is configured for zero-config or `vercel.json` deployment with external PostgreSQL (such as Neon, Supabase, or AWS RDS).

### Step 1: Provision a PostgreSQL Database (e.g., Neon)
1. Create a free PostgreSQL database on [Neon](https://neon.tech).
2. Copy your PostgreSQL connection string (`postgresql://user:password@ep-sample.neon.tech/powerwise?sslmode=require`).

### Step 2: Initialize the Production Database
Run the initialization against your production database before deployment:
```bash
DATABASE_URL="your-production-database-url" python manage.py init-db
DATABASE_URL="your-production-database-url" python manage.py create-admin --username admin --email admin@powerwise.ng --password "StrongProductionPassword123!"
```

### Step 3: Deploy to Vercel
1. Push your clean code to GitHub.
2. In Vercel, click **Add New Project** and import the `Powerwise` repository.
3. In the project **Environment Variables** settings, configure:
   - `DATABASE_URL`: Your PostgreSQL connection string.
   - `SECRET_KEY`: A strong cryptographically secure secret key.
   - `FLASK_ENV`: `production`
   - `SESSION_COOKIE_SECURE`: `True`
4. Deploy the project.
