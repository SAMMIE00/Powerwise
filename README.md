# PowerWise

PowerWise is a lightweight Flask web app that helps households estimate electricity use, compare appliance consumption, and identify ways to reduce power costs. Users can input appliance wattage, quantity, and daily runtime, then receive a breakdown of estimated daily and monthly kWh usage and cost.

## Overview

The app is designed for prepaid-meter households and everyday energy-conscious users who want a quick way to:

- estimate electricity consumption for appliances
- track saved appliance entries in a local JSON store
- compare which devices consume the most energy
- see estimated monthly costs based on a tariff rate
- review practical energy-saving tips
- generate a printable report of appliance usage

## Features

- Dashboard with total monthly consumption, cost, and top energy users
- Appliance overview table with delete support
- Electricity calculator for wattage, quantity, and daily hours
- Tariff-based cost estimation in ₦/kWh
- Savings tips page with keyword-based appliance suggestions
- Printable/Downloadable report page with charts and summary data
- Local JSON persistence for user-entered appliances

## Tech Stack

- Python 3
- Flask
- Jinja2 templates
- HTML, CSS, and JavaScript
- JSON file storage for appliance data

## Project Structure

```text
Powerwise/
├── app.py                 # Flask application and energy calculation logic
├── Templates/            # HTML templates for dashboard, calculator, reports, etc.
├── static/               # CSS and JS assets
├── user_appliances.json  # Local appliance storage
├── requirements.txt      # Python dependencies
├── README.md             # Project documentation
└── tests/                # Test directory (if added later)
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/SAMMIE00/Powerwise.git
cd Powerwise
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
python app.py
```

Then open the app in a browser at:

```text
http://127.0.0.1:5000/
```

## How It Works

1. Add an appliance via the Energy Calculator page.
2. Enter the appliance name, wattage, quantity, and usage hours per day.
3. The app calculates:
   - daily kWh consumption
   - monthly kWh consumption
   - estimated monthly cost
4. Saved appliances are aggregated in the dashboard and appliance pages.
5. The reports page summarizes appliance performance and supports printing.

## Calculation Logic

PowerWise uses the standard electrical consumption formula:

```text
kWh = (wattage × quantity × hours_per_day) / 1000
```

Monthly estimates are based on a 30-day month and a configurable electricity tariff rate.

## Key Routes

- `/` - Dashboard
- `/calculator` - Appliance energy calculator
- `/appliances` - Stored appliance list
- `/savings` - Energy-saving recommendations
- `/reports` - Printable usage and cost analysis

## Notes

- Appliance data persists locally in `user_appliances.json`.
- The app currently stores a simple per-user local dataset rather than a database.
- This project is intended as a practical energy-monitoring tool and not a replacement for your utility bill or meter readings.