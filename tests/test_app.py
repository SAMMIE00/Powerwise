"""
Comprehensive test suite for PowerWise.
Tests pure calculation functions, validation, database models,
authentication, session management, access control, and route behavior.
"""
import pytest
from app import (
    app as flask_app,
    calculate_daily_kwh,
    calculate_monthly_kwh,
    calculate_monthly_cost,
    analyze_appliances,
)
from models import db, User, Appliance, UserSettings, UsageHistory


@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key-powerwise",
        "SESSION_COOKIE_SECURE": False,
    })

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_user(app):
    with app.app_context():
        user = User(username="testuser", email="testuser@example.com")
        user.set_password("SecurePassword123!")
        db.session.add(user)
        db.session.flush()

        settings = UserSettings(
            user_id=user.id,
            tariff_band="Band A",
            custom_tariff_rate=209.50,
            preferred_theme="light"
        )
        db.session.add(settings)
        db.session.commit()
        return db.session.get(User, user.id)


@pytest.fixture
def other_user(app):
    with app.app_context():
        user = User(username="otheruser", email="otheruser@example.com")
        user.set_password("AnotherPassword123!")
        db.session.add(user)
        db.session.flush()

        settings = UserSettings(
            user_id=user.id,
            tariff_band="Band B",
            custom_tariff_rate=62.48,
            preferred_theme="dark"
        )
        db.session.add(settings)
        db.session.commit()
        return db.session.get(User, user.id)


def login_client(client, username="testuser", password="SecurePassword123!"):
    return client.post("/login", data={
        "identifier": username,
        "password": password,
    }, follow_redirects=True)


# =====================================================================
# 1. PURE CALCULATION & VALIDATION TESTS
# =====================================================================

def test_calculate_daily_kwh_valid():
    # 100W * 2 units * 5 hours = 1000 Wh = 1.0 kWh
    assert calculate_daily_kwh(100.0, 2, 5.0) == 1.0
    # 75W * 1 unit * 8 hours = 600 Wh = 0.6 kWh
    assert calculate_daily_kwh(75.0, 1, 8.0) == 0.6


def test_calculate_daily_kwh_zero_and_negative_inputs():
    with pytest.raises(ValueError, match="Wattage must be greater than 0"):
        calculate_daily_kwh(0, 1, 5)

    with pytest.raises(ValueError, match="Wattage must be greater than 0"):
        calculate_daily_kwh(-50, 1, 5)

    with pytest.raises(ValueError, match="Quantity must be at least 1"):
        calculate_daily_kwh(100, 0, 5)

    with pytest.raises(ValueError, match="Quantity must be at least 1"):
        calculate_daily_kwh(100, -2, 5)


def test_calculate_daily_kwh_usage_hours_boundaries():
    # Zero or negative hours
    with pytest.raises(ValueError, match="Usage hours must be between"):
        calculate_daily_kwh(100, 1, 0)

    with pytest.raises(ValueError, match="Usage hours must be between"):
        calculate_daily_kwh(100, 1, -1)

    # Exceeding 24 hours per day
    with pytest.raises(ValueError, match="Usage hours must be between"):
        calculate_daily_kwh(100, 1, 24.5)

    # Exactly 24 hours should succeed
    assert calculate_daily_kwh(100, 1, 24.0) == 2.4


def test_calculate_monthly_kwh():
    # 1.0 kWh daily * 30 days = 30.0 kWh
    assert calculate_monthly_kwh(100.0, 2, 5.0) == 30.0


def test_calculate_monthly_cost():
    # 100 kWh * ₦68.0 = ₦6800.0
    assert calculate_monthly_cost(100.0, 68.0) == 6800.0
    # 100 kWh * Band A ₦209.50 = ₦20950.0
    assert calculate_monthly_cost(100.0, 209.50) == 20950.0

    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_monthly_cost(-10, 68.0)

    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_monthly_cost(100, -5.0)


def test_analyze_appliances_empty():
    res = analyze_appliances([])
    assert res["appliances"] == []
    assert res["summary"]["total_monthly_kwh"] == 0.0
    assert res["summary"]["highest_consumer"] is None


def test_analyze_appliances_aggregation():
    sample = [
        {"name": "Fan", "wattage": 75.0, "quantity": 2, "hours_per_day": 10.0},
        {"name": "Fridge", "wattage": 250.0, "quantity": 1, "hours_per_day": 24.0},
    ]
    res = analyze_appliances(sample, rate_per_kwh=200.0)
    assert len(res["appliances"]) == 2
    # Fridge consumes more, should be ranked #1
    assert res["appliances"][0]["name"] == "Fridge"
    assert res["summary"]["highest_consumer"]["name"] == "Fridge"
    assert res["summary"]["total_monthly_cost"] > 0
    assert res["summary"]["potential_20pct_savings"] == round(res["summary"]["total_monthly_cost"] * 0.20, 2)


# =====================================================================
# 2. DATABASE MODELS & RELATIONSHIPS
# =====================================================================

def test_user_password_hashing(app):
    with app.app_context():
        user = User(username="crypto", email="crypto@test.com")
        user.set_password("Secret123")
        assert user.password_hash != "Secret123"
        assert user.check_password("Secret123") is True
        assert user.check_password("WrongPassword") is False


def test_user_cascade_delete(app, test_user):
    with app.app_context():
        user = db.session.get(User, test_user.id)
        appliance = Appliance(
            user_id=user.id,
            name="Toaster",
            wattage=800,
            quantity=1,
            hours_per_day=0.5,
            category="Kitchen",
        )
        db.session.add(appliance)
        db.session.commit()
        app_id = appliance.id

        # Deleting user should cascade delete their appliances and settings
        db.session.delete(user)
        db.session.commit()

        assert db.session.get(Appliance, app_id) is None
        assert UserSettings.query.filter_by(user_id=test_user.id).first() is None


# =====================================================================
# 3. AUTHENTICATION & ACCESS CONTROL TESTS
# =====================================================================

def test_unauthenticated_redirect_to_login(client):
    protected_urls = ["/", "/appliances", "/calculator", "/savings", "/reports"]
    for url in protected_urls:
        resp = client.get(url, follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


def test_login_invalid_credentials(client, test_user):
    resp = client.post("/login", data={
        "identifier": "testuser",
        "password": "WrongPassword!",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Invalid email/username or password" in resp.data


def test_login_success_and_session(client, test_user):
    resp = login_client(client, "testuser", "SecurePassword123!")
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_id") == test_user.id
        assert sess.get("username") == "testuser"


def test_logout(client, test_user):
    login_client(client)
    resp = client.get("/logout", follow_redirects=True)
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_register_new_user(client):
    resp = client.post("/register", data={
        "username": "newhousehold",
        "email": "household@powerwise.ng",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Account created successfully" in resp.data

    with flask_app.app_context():
        created = User.query.filter_by(username="newhousehold").first()
        assert created is not None
        assert created.settings is not None


# =====================================================================
# 4. MULTI-USER DATA ISOLATION & APPLIANCE CRUD
# =====================================================================

def test_appliance_creation_and_prg_redirect(client, test_user):
    login_client(client, "testuser", "SecurePassword123!")

    # Calculator POST "save"
    resp = client.post("/calculator", data={
        "name": "Standing Fan",
        "category": "Cooling",
        "wattage": "75",
        "quantity": "2",
        "hours": "8",
        "rate": "209.50",
        "tariff-band": "Band A",
        "action": "save",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Standing Fan" in resp.data
    assert b"Cooling" in resp.data

    with flask_app.app_context():
        appliance = Appliance.query.filter_by(user_id=test_user.id, name="Standing Fan").first()
        assert appliance is not None
        assert appliance.wattage == 75.0
        assert appliance.quantity == 2


def test_duplicate_appliance_merging(client, test_user):
    login_client(client, "testuser", "SecurePassword123!")

    # Add appliance twice
    client.post("/calculator", data={
        "name": "Ceiling Fan",
        "category": "Cooling",
        "wattage": "70",
        "quantity": "1",
        "hours": "10",
        "action": "save",
    }, follow_redirects=True)

    client.post("/calculator", data={
        "name": "Ceiling Fan",
        "category": "Cooling",
        "wattage": "70",
        "quantity": "2",
        "hours": "10",
        "action": "save",
    }, follow_redirects=True)

    with flask_app.app_context():
        fans = Appliance.query.filter_by(user_id=test_user.id, name="Ceiling Fan").all()
        assert len(fans) == 1
        assert fans[0].quantity == 3  # 1 + 2


def test_user_cannot_access_or_modify_other_users_appliances(client, test_user, other_user):
    with flask_app.app_context():
        # Add appliance owned by other_user
        secret_app = Appliance(
            user_id=other_user.id,
            name="Other User TV",
            wattage=120,
            quantity=1,
            hours_per_day=4,
            category="Entertainment",
        )
        db.session.add(secret_app)
        db.session.commit()
        secret_app_id = secret_app.id

    # Log in as test_user
    login_client(client, "testuser", "SecurePassword123!")

    # Ensure test_user cannot see other_user's appliance in list
    resp = client.get("/appliances")
    assert b"Other User TV" not in resp.data

    # Ensure test_user cannot edit other_user's appliance (404)
    edit_resp = client.get(f"/appliances/edit/{secret_app_id}")
    assert edit_resp.status_code == 404

    # Ensure test_user cannot delete other_user's appliance
    del_resp = client.post(f"/appliances/delete/{secret_app_id}", follow_redirects=True)
    assert del_resp.status_code == 200

    # Verify appliance was NOT deleted from other_user
    with flask_app.app_context():
        still_exists = db.session.get(Appliance, secret_app_id)
        assert still_exists is not None


def test_appliance_editing(client, test_user):
    login_client(client, "testuser", "SecurePassword123!")

    with flask_app.app_context():
        app_obj = Appliance(
            user_id=test_user.id,
            name="Old Fridge",
            wattage=300,
            quantity=1,
            hours_per_day=12,
            category="Kitchen",
        )
        db.session.add(app_obj)
        db.session.commit()
        app_id = app_obj.id

    resp = client.post(f"/appliances/edit/{app_id}", data={
        "name": "Upgraded Inverter Fridge",
        "category": "Kitchen",
        "wattage": "150",
        "quantity": "1",
        "hours": "24",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Upgraded Inverter Fridge" in resp.data

    with flask_app.app_context():
        updated = db.session.get(Appliance, app_id)
        assert updated.name == "Upgraded Inverter Fridge"
        assert updated.wattage == 150.0


def test_clear_all_appliances(client, test_user, other_user):
    with flask_app.app_context():
        db.session.add(Appliance(user_id=test_user.id, name="Test Device", wattage=100, quantity=1, hours_per_day=5))
        db.session.add(Appliance(user_id=other_user.id, name="Other Device", wattage=100, quantity=1, hours_per_day=5))
        db.session.commit()

    login_client(client, "testuser", "SecurePassword123!")
    resp = client.post("/appliances/clear", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Cleared all 1 appliance(s)" in resp.data

    with flask_app.app_context():
        # test_user's appliances cleared
        assert Appliance.query.filter_by(user_id=test_user.id).count() == 0
        # other_user's appliance preserved
        assert Appliance.query.filter_by(user_id=other_user.id).count() == 1


# =====================================================================
# 5. TARIFF CONSISTENCY & TARIFF SETTINGS
# =====================================================================

def test_tariff_persistence_across_pages(client, test_user):
    login_client(client, "testuser", "SecurePassword123!")

    # Set tariff to Band A (₦209.50) via calculator save
    client.post("/calculator", data={
        "name": "AC Unit",
        "category": "Cooling",
        "wattage": "1500",
        "quantity": "1",
        "hours": "6",
        "rate": "209.50",
        "tariff-band": "Band A",
        "action": "save",
    }, follow_redirects=True)

    # Check that dashboard shows ₦209.50
    dash_resp = client.get("/")
    assert b"209.50" in dash_resp.data

    # Check that appliances page shows ₦209.50
    app_resp = client.get("/appliances")
    assert b"209.50" in app_resp.data
