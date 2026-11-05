"""
PowerWise - Energy Usage Analyzer for Nigerian Households
Flask application with SQLAlchemy multi-user persistence, authentication,
and Nigerian tariff band modeling.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
from models import db, User, Appliance, UserSettings, UsageHistory
from auth import auth_bp, login_required, get_current_user

# Load environment variables (.env and .env.local)
load_dotenv()
load_dotenv(".env.local", override=True)

app = Flask(__name__, template_folder="Templates")

# --- CONFIGURATION ---
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "powerwise-secret-dev-key-change-in-production")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "False").lower() in ("true", "1")

# Database URL handling: Use direct/unpooled connection for schema migrations/CLI,
# and pooled connection for web application traffic.
if any("manage.py" in arg for arg in sys.argv):
    database_url = os.getenv("DATABASE_URL_UNPOOLED") or os.getenv("DATABASE_URL", "sqlite:///powerwise.db")
else:
    database_url = os.getenv("DATABASE_URL", "sqlite:///powerwise.db")

# Convert legacy postgres:// or postgresql:// to postgresql+psycopg2:// for SQLAlchemy
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif database_url.startswith("postgresql://") and not database_url.startswith("postgresql+"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# Initialize extensions
db.init_app(app)
app.register_blueprint(auth_bp)

DEFAULT_RATE_PER_KWH = 68.0
DAYS_IN_MONTH = 30


# --- CONTEXT PROCESSOR ---
@app.context_processor
def inject_globals():
    """Injects current_user and utility constants into all Jinja2 templates."""
    user = get_current_user()
    user_rate = user.settings.rate if user and user.settings else DEFAULT_RATE_PER_KWH
    user_band = user.settings.tariff_band if user and user.settings else "Band B"
    return {
        "current_user": user,
        "active_user_rate": user_rate,
        "active_user_band": user_band,
    }


def get_user_rate(user: User) -> float:
    """Helper to retrieve active tariff rate for a given user."""
    if user and user.settings and user.settings.custom_tariff_rate:
        return float(user.settings.custom_tariff_rate)
    return DEFAULT_RATE_PER_KWH


# --- PURE CALCULATION FUNCTIONS ---

def calculate_daily_kwh(wattage: float, quantity: int, hours_per_day: float) -> float:
    """Calculates daily consumption in kWh."""
    if wattage <= 0:
        raise ValueError("Wattage must be greater than 0 watts.")
    if quantity <= 0:
        raise ValueError("Quantity must be at least 1.")
    if hours_per_day <= 0 or hours_per_day > 24:
        raise ValueError("Usage hours must be between 0.1 and 24 hours per day.")

    return round((wattage * quantity * hours_per_day) / 1000.0, 3)


def calculate_monthly_kwh(
    wattage: float, quantity: int, hours_per_day: float, days: int = DAYS_IN_MONTH
) -> float:
    """Calculates monthly consumption in kWh based on a given number of days."""
    daily_kwh = calculate_daily_kwh(wattage, quantity, hours_per_day)
    return round(daily_kwh * days, 2)


def calculate_monthly_cost(
    monthly_kwh: float, rate_per_kwh: float = DEFAULT_RATE_PER_KWH
) -> float:
    """Calculates cost based on monthly kWh and tariff rate in ₦/kWh."""
    if monthly_kwh < 0 or rate_per_kwh < 0:
        raise ValueError("Consumption and rate cannot be negative.")
    return round(monthly_kwh * rate_per_kwh, 2)


def analyze_appliances(
    raw_appliances: list, rate_per_kwh: float = DEFAULT_RATE_PER_KWH
) -> dict:
    """
    Computes aggregates, shares, and reduction insights for a list of appliance dicts.
    """
    if not raw_appliances:
        return {
            "appliances": [],
            "summary": {
                "total_daily_kwh": 0.0,
                "total_monthly_kwh": 0.0,
                "total_monthly_cost": 0.0,
                "highest_consumer": None,
                "appliance_count": 0,
                "potential_20pct_savings": 0.0,
            },
        }

    analyzed_list = []
    for item in raw_appliances:
        daily_kwh = calculate_daily_kwh(
            item["wattage"], item["quantity"], item["hours_per_day"]
        )
        monthly_kwh = calculate_monthly_kwh(
            item["wattage"], item["quantity"], item["hours_per_day"]
        )
        monthly_cost = calculate_monthly_cost(monthly_kwh, rate_per_kwh)

        analyzed_list.append(
            {
                **item,
                "daily_kwh": daily_kwh,
                "monthly_kwh": monthly_kwh,
                "monthly_cost": monthly_cost,
            }
        )

    analyzed_list.sort(key=lambda x: x["monthly_kwh"], reverse=True)

    total_daily_kwh = round(sum(a["daily_kwh"] for a in analyzed_list), 2)
    total_monthly_kwh = round(sum(a["monthly_kwh"] for a in analyzed_list), 2)
    total_monthly_cost = round(sum(a["monthly_cost"] for a in analyzed_list), 2)

    for item in analyzed_list:
        if total_monthly_kwh > 0:
            item["percentage_share"] = round(
                (item["monthly_kwh"] / total_monthly_kwh) * 100, 1
            )
        else:
            item["percentage_share"] = 0.0

        reduced_hours = max(0, item["hours_per_day"] - 1)
        reduced_kwh = round(
            ((item["wattage"] * item["quantity"] * reduced_hours) / 1000.0)
            * DAYS_IN_MONTH,
            2,
        )
        item["save_one_hour_cost"] = round(
            item["monthly_cost"] - calculate_monthly_cost(reduced_kwh, rate_per_kwh),
            2,
        )

    highest_consumer = analyzed_list[0] if analyzed_list else None

    summary = {
        "total_daily_kwh": total_daily_kwh,
        "total_monthly_kwh": total_monthly_kwh,
        "total_monthly_cost": total_monthly_cost,
        "highest_consumer": highest_consumer,
        "appliance_count": len(analyzed_list),
        "potential_20pct_savings": round(total_monthly_cost * 0.20, 2),
    }

    return {"appliances": analyzed_list, "summary": summary}


# --- APPLICATION ROUTES (ALL PROTECTED) ---

@app.route("/")
@login_required
def dashboard():
    user = get_current_user()
    rate = get_user_rate(user)
    raw = [a.to_dict(rate) for a in user.appliances]
    analysis = analyze_appliances(raw, rate)

    # Record monthly snapshot in UsageHistory if appliances exist
    if raw:
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        existing_snapshot = UsageHistory.query.filter_by(
            user_id=user.id, recorded_month=current_month
        ).first()

        if existing_snapshot:
            existing_snapshot.energy_consumption = analysis["summary"]["total_monthly_kwh"]
            existing_snapshot.estimated_cost = analysis["summary"]["total_monthly_cost"]
            existing_snapshot.tariff_rate = rate
        else:
            snapshot = UsageHistory(
                user_id=user.id,
                recorded_month=current_month,
                energy_consumption=analysis["summary"]["total_monthly_kwh"],
                estimated_cost=analysis["summary"]["total_monthly_cost"],
                tariff_rate=rate,
            )
            db.session.add(snapshot)
        db.session.commit()

    return render_template(
        "dashboard.html",
        summary=analysis["summary"],
        appliances=analysis["appliances"],
        rate=rate,
        active_page="dashboard",
    )


@app.route("/appliances")
@login_required
def appliances():
    user = get_current_user()
    rate = get_user_rate(user)
    raw = [a.to_dict(rate) for a in user.appliances]
    analysis = analyze_appliances(raw, rate)

    return render_template(
        "appliances.html",
        appliances=analysis["appliances"],
        summary=analysis["summary"],
        rate=rate,
        active_page="appliances",
    )


@app.route("/calculator", methods=["GET", "POST"])
@login_required
def calculator():
    user = get_current_user()
    user_rate = get_user_rate(user)
    result = None
    error = None

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "General").strip()
            wattage = float(request.form.get("wattage", 0))
            quantity = int(request.form.get("quantity", 1))
            hours_per_day = float(request.form.get("hours", 0))
            rate = float(request.form.get("rate", user_rate))
            tariff_band = request.form.get("tariff-band", "").strip()

            if not name:
                raise ValueError("Please provide an appliance name (e.g., Standing Fan).")

            daily_kwh = calculate_daily_kwh(wattage, quantity, hours_per_day)
            daily_cost = calculate_monthly_cost(daily_kwh, rate)
            monthly_kwh = calculate_monthly_kwh(wattage, quantity, hours_per_day)
            monthly_cost = calculate_monthly_cost(monthly_kwh, rate)

            result = {
                "name": name,
                "category": category,
                "wattage": wattage,
                "quantity": quantity,
                "hours": hours_per_day,
                "hours_per_day": hours_per_day,
                "daily_kwh": daily_kwh,
                "daily_cost": daily_cost,
                "monthly_kwh": monthly_kwh,
                "monthly_cost": monthly_cost,
                "yearly_kwh": round(monthly_kwh * 12, 2),
                "yearly_cost": round(monthly_cost * 12, 2),
                "rate": rate,
            }

            save_action = request.form.get("action", "save")
            if save_action == "save":
                # Check for existing identical appliance for this user
                existing = Appliance.query.filter_by(
                    user_id=user.id,
                    name=name,
                    wattage=wattage,
                    hours_per_day=hours_per_day,
                ).first()

                if existing:
                    existing.quantity += quantity
                    msg = f"Updated quantity for existing appliance '{name}'."
                else:
                    new_app = Appliance(
                        user_id=user.id,
                        name=name,
                        category=category or "General",
                        wattage=wattage,
                        quantity=quantity,
                        hours_per_day=hours_per_day,
                    )
                    db.session.add(new_app)
                    msg = f"Appliance '{name}' successfully saved."

                # Persist user's selected tariff rate & band
                if user.settings:
                    user.settings.custom_tariff_rate = rate
                    if tariff_band:
                        user.settings.tariff_band = tariff_band
                db.session.commit()

                flash(msg, "success")
                return redirect(url_for("appliances"))

        except ValueError as e:
            error = str(e)

    return render_template(
        "calculator.html",
        result=result,
        error=error,
        default_rate=user_rate,
        active_page="calculator",
    )


@app.route("/appliances/edit/<int:appliance_id>", methods=["GET", "POST"])
@login_required
def edit_appliance(appliance_id):
    """Allows an authenticated user to edit one of their saved appliances."""
    user = get_current_user()
    appliance = Appliance.query.filter_by(id=appliance_id, user_id=user.id).first_or_404()

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "General").strip()
            wattage = float(request.form.get("wattage", 0))
            quantity = int(request.form.get("quantity", 1))
            hours_per_day = float(request.form.get("hours", 0))

            if not name:
                raise ValueError("Appliance name cannot be blank.")
            if wattage <= 0:
                raise ValueError("Wattage must be greater than 0.")
            if quantity < 1:
                raise ValueError("Quantity must be at least 1.")
            if hours_per_day <= 0 or hours_per_day > 24:
                raise ValueError("Usage hours must be between 0.1 and 24 hours per day.")

            appliance.name = name
            appliance.category = category or "General"
            appliance.wattage = wattage
            appliance.quantity = quantity
            appliance.hours_per_day = hours_per_day

            db.session.commit()
            flash(f"Successfully updated '{appliance.name}'.", "success")
            return redirect(url_for("appliances"))

        except ValueError as e:
            flash(str(e), "error")

    return render_template("edit_appliance.html", appliance=appliance, active_page="appliances")


@app.route("/appliances/delete/<int:appliance_id>", methods=["POST"])
@login_required
def remove_appliance(appliance_id):
    user = get_current_user()
    appliance = Appliance.query.filter_by(id=appliance_id, user_id=user.id).first()
    if appliance:
        name = appliance.name
        db.session.delete(appliance)
        db.session.commit()
        flash(f"Deleted appliance '{name}'.", "info")
    else:
        flash("Appliance not found or already deleted.", "warning")
    return redirect(url_for("appliances"))


@app.route("/appliances/clear", methods=["POST"])
@login_required
def reset_appliances():
    user = get_current_user()
    count = Appliance.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    flash(f"Cleared all {count} appliance(s) from your account.", "info")
    return redirect(url_for("appliances"))


@app.route("/savings")
@login_required
def savings():
    user = get_current_user()
    rate = get_user_rate(user)
    raw = [a.to_dict(rate) for a in user.appliances]
    analysis = analyze_appliances(raw, rate)

    # Dynamic savings opportunities calculated from user's actual high-consumption appliances
    opportunities = []
    for item in analysis["appliances"][:3]:  # Top 3 energy consumers
        one_hour_savings = item.get("save_one_hour_cost", 0.0)
        two_hour_savings = round(one_hour_savings * 2, 2)
        opportunities.append({
            "name": item["name"],
            "wattage": item["wattage"],
            "hours": item["hours_per_day"],
            "monthly_cost": item["monthly_cost"],
            "one_hour_savings": one_hour_savings,
            "two_hour_savings": two_hour_savings,
        })

    return render_template(
        "savings.html",
        appliances=analysis["appliances"],
        summary=analysis["summary"],
        opportunities=opportunities,
        rate=rate,
        active_page="savings",
    )


@app.route("/reports")
@login_required
def reports():
    user = get_current_user()
    rate = get_user_rate(user)
    raw = [a.to_dict(rate) for a in user.appliances]
    analysis = analyze_appliances(raw, rate)

    # Fetch available historical months for this user
    history_records = UsageHistory.query.filter_by(user_id=user.id).order_by(
        UsageHistory.recorded_month.desc()
    ).all()

    available_months = [h.to_dict() for h in history_records]

    return render_template(
        "reports.html",
        appliances=analysis["appliances"],
        summary=analysis["summary"],
        history_records=available_months,
        rate=rate,
        active_page="reports",
    )


@app.route("/settings/tariff", methods=["POST"])
@login_required
def update_tariff():
    """Allows user to update their global tariff preference."""
    user = get_current_user()
    try:
        new_rate = float(request.form.get("tariff_rate", 68.0))
        new_band = request.form.get("tariff_band", "").strip()
        if new_rate < 0:
            raise ValueError("Tariff rate cannot be negative.")

        if user.settings:
            user.settings.custom_tariff_rate = new_rate
            if new_band:
                user.settings.tariff_band = new_band
        else:
            settings = UserSettings(
                user_id=user.id,
                custom_tariff_rate=new_rate,
                tariff_band=new_band or "Custom",
            )
            db.session.add(settings)
        db.session.commit()
        flash(f"Tariff rate updated to ₦{new_rate:.2f}/kWh ({new_band}).", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(request.referrer or url_for("dashboard"))



if __name__ == "__main__":
    app.run(debug=True)
