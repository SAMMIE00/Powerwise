from flask import Flask, render_template, request

# Create the Flask application
app = Flask(__name__, template_folder="Templates")

# Define the calculator route below
@app.route("/calculator", methods=["GET", "POST"])
def calculator():
    result = None
    error = None

    if request.method == "POST":
        try:
            # Get the values from the form
            appliance = request.form["appliance"].strip()
            wattage = float(request.form["wattage"])
            quantity = int(request.form["quantity"])
            hours = float(request.form["hours"])
            tariff = float(request.form["tariff"])

            if not appliance:
                raise ValueError("Enter an appliance name.")

            if wattage <= 0 or quantity < 1:
                raise ValueError("Wattage and quantity must be positive.")

            if not 0 <= hours <=24 or tariff < 0:
                raise ValueError("Check your hours and tariff.")

            daily_kwh = wattage * quantity * hours / 1000

            monthly_kwh = daily_kwh * 30

            monthly_cost = monthly_kwh * tariff

            result = {
                "appliance": appliance,
                "daily_kwh": daily_kwh,
                "monthly_kwh": monthly_kwh,
                "monthly_cost": monthly_cost
            }

        except (ValueError, TypeError):

            error = "Please check the values you entered."

    return render_template(
        "calculator.html",
        result=result,
        error=error
    )