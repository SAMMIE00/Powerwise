import json
import os
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# --- CONFIGURATION ---
DEFAULT_RATE_PER_KWH = 68.0
DAYS_IN_MONTH = 30
DATA_FILE = "user_appliances.json"


# --- 1. STORAGE ENGINE ---

def load_user_appliances() -> list:
    """Reads user-inserted appliances from a local JSON file."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, IOError):
        return []


def save_user_appliance(new_appliance: dict) -> None:
    """Appends a newly submitted appliance into the JSON store."""
    appliances = load_user_appliances()
    new_id = max((item.get("id", 0) for item in appliances), default=0) + 1
    new_appliance["id"] = new_id
    appliances.append(new_appliance)

    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(appliances, file, indent=4)


def delete_user_appliance(appliance_id: int) -> None:
    """Removes a specific appliance by ID."""
    appliances = load_user_appliances()
    updated = [item for item in appliances if item.get("id") != appliance_id]
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(updated, file, indent=4)


def clear_all_appliances() -> None:
    """Resets all user data back to an empty state."""
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)


# --- 2. PURE CALCULATION FUNCTIONS ---

def calculate_daily_kwh(wattage: float, quantity: int, hours_per_day: float) -> float:
    if wattage <= 0:
        raise ValueError("Wattage must be greater than 0 watts.")
    if quantity <= 0:
        raise ValueError("Quantity must be at least 1.")
    if hours_per_day <= 0 or hours_per_day > 24:
        raise ValueError("Usage hours must be between 0.1 and 24 hours per day.")

    return round((wattage * quantity * hours_per_day) / 1000.0, 3)


def calculate_monthly_kwh(wattage: float, quantity: int, hours_per_day: float, days: int = DAYS_IN_MONTH) -> float:
    daily_kwh = calculate_daily_kwh(wattage, quantity, hours_per_day)
    return round(daily_kwh * days, 2)


def calculate_monthly_cost(monthly_kwh: float, rate_per_kwh: float = DEFAULT_RATE_PER_KWH) -> float:
    if monthly_kwh < 0 or rate_per_kwh < 0:
        raise ValueError("Consumption and rate cannot be negative.")
    return round(monthly_kwh * rate_per_kwh, 2)


# --- 3. THE ANALYZER ENGINE ---

def analyze_appliances(raw_appliances: list, rate_per_kwh: float = DEFAULT_RATE_PER_KWH) -> dict:
    if not raw_appliances:
        return {
            "appliances": [],
            "summary": {
                "total_daily_kwh": 0.0,
                "total_monthly_kwh": 0.0,
                "total_monthly_cost": 0.0,
                "highest_consumer": None,
                "appliance_count": 0,
                "potential_20pct_savings": 0.0
            }
        }

    analyzed_list = []
    for item in raw_appliances:
        daily_kwh = calculate_daily_kwh(item["wattage"], item["quantity"], item["hours_per_day"])
        monthly_kwh = calculate_monthly_kwh(item["wattage"], item["quantity"], item["hours_per_day"])
        monthly_cost = calculate_monthly_cost(monthly_kwh, rate_per_kwh)

        analyzed_list.append({
            **item,
            "daily_kwh": daily_kwh,
            "monthly_kwh": monthly_kwh,
            "monthly_cost": monthly_cost
        })

    analyzed_list.sort(key=lambda x: x["monthly_kwh"], reverse=True)

    total_daily_kwh = round(sum(a["daily_kwh"] for a in analyzed_list), 2)
    total_monthly_kwh = round(sum(a["monthly_kwh"] for a in analyzed_list), 2)
    total_monthly_cost = round(sum(a["monthly_cost"] for a in analyzed_list), 2)

    for item in analyzed_list:
        if total_monthly_kwh > 0:
            item["percentage_share"] = round((item["monthly_kwh"] / total_monthly_kwh) * 100, 1)
        else:
            item["percentage_share"] = 0.0

        reduced_hours = max(0, item["hours_per_day"] - 1)
        reduced_kwh = round(((item["wattage"] * item["quantity"] * reduced_hours) / 1000.0) * DAYS_IN_MONTH, 2)
        item["save_one_hour_cost"] = round(item["monthly_cost"] - calculate_monthly_cost(reduced_kwh, rate_per_kwh), 2)

    highest_consumer = analyzed_list[0]

    summary = {
        "total_daily_kwh": total_daily_kwh,
        "total_monthly_kwh": total_monthly_kwh,
        "total_monthly_cost": total_monthly_cost,
        "highest_consumer": highest_consumer,
        "appliance_count": len(analyzed_list),
        "potential_20pct_savings": round(total_monthly_cost * 0.20, 2)
    }

    return {
        "appliances": analyzed_list,
        "summary": summary
    }


# --- 4. FLASK ROUTES ---

@app.route("/")
def dashboard():
    analysis = analyze_appliances(load_user_appliances())
    return render_template(
        "dashboard.html",
        summary=analysis["summary"],
        appliances=analysis["appliances"],
        active_page="dashboard"
    )


@app.route("/appliances")
def appliances():
    analysis = analyze_appliances(load_user_appliances())
    return render_template(
        "appliances.html",
        appliances=analysis["appliances"],
        summary=analysis["summary"],
        rate=DEFAULT_RATE_PER_KWH,
        active_page="appliances"
    )


@app.route("/calculator", methods=["GET", "POST"])
def calculator():
    result = None
    error = None

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "General").strip()
            wattage = float(request.form.get("wattage", 0))
            quantity = int(request.form.get("quantity", 1))
            hours_per_day = float(request.form.get("hours", 0))
            rate = float(request.form.get("rate", DEFAULT_RATE_PER_KWH))

            if not name:
                raise ValueError("Please provide an appliance name (e.g., Standing Fan).")

            daily_kwh = calculate_daily_kwh(wattage, quantity, hours_per_day)
            monthly_kwh = calculate_monthly_kwh(wattage, quantity, hours_per_day)
            monthly_cost = calculate_monthly_cost(monthly_kwh, rate)

            result = {
                "name": name,
                "category": category,
                "wattage": wattage,
                "quantity": quantity,
                "hours_per_day": hours_per_day,
                "daily_kwh": daily_kwh,
                "monthly_kwh": monthly_kwh,
                "monthly_cost": monthly_cost,
                "rate": rate
            }

            save_action = request.form.get("action", "save")
            if save_action == "save":
                save_user_appliance({
                    "name": name,
                    "category": category,
                    "wattage": wattage,
                    "quantity": quantity,
                    "hours_per_day": hours_per_day
                })

        except ValueError as e:
            error = str(e)

    return render_template(
        "calculator.html",
        result=result,
        error=error,
        default_rate=DEFAULT_RATE_PER_KWH,
        active_page="calculator"
    )


@app.route("/appliances/delete/<int:appliance_id>", methods=["POST"])
def remove_appliance(appliance_id):
    delete_user_appliance(appliance_id)
    return redirect(url_for("appliances"))


@app.route("/appliances/clear", methods=["POST"])
def reset_appliances():
    clear_all_appliances()
    return redirect(url_for("dashboard"))


@app.route("/savings")
def savings():
    analysis = analyze_appliances(load_user_appliances())
    return render_template(
        "savings.html",
        appliances=analysis["appliances"],
        summary=analysis["summary"],
        rate=DEFAULT_RATE_PER_KWH,
        active_page="savings"
    )


@app.route("/reports")
def reports():
    analysis = analyze_appliances(load_user_appliances())
    return render_template(
        "reports.html",
        appliances=analysis["appliances"],
        summary=analysis["summary"],
        rate=DEFAULT_RATE_PER_KWH,
        active_page="reports"
    )


if __name__ == "__main__":
    app.run(debug=True)
