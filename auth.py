"""
Authentication and access control system for PowerWise.
Provides user session management, rate limiting, and route protection.
"""
import re
import time
from functools import wraps
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from models import db, User, UserSettings

auth_bp = Blueprint("auth", __name__)

# Basic in-memory rate limiting tracker: IP -> list of attempt timestamps
_LOGIN_ATTEMPTS = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 minutes


def is_safe_url(target: str) -> bool:
    """Ensures redirect targets are internal to prevent open redirect vulnerabilities."""
    if not target:
        return False
    # Avoid protocol-relative URLs (e.g. //evil.com)
    if target.startswith("//") or target.startswith("\\"):
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def check_rate_limit(ip: str) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    now = time.time()
    attempts = _LOGIN_ATTEMPTS.get(ip, [])
    # Filter attempts within lockout window
    recent = [t for t in attempts if now - t < LOCKOUT_SECONDS]
    _LOGIN_ATTEMPTS[ip] = recent
    return len(recent) < MAX_LOGIN_ATTEMPTS


def record_failed_login(ip: str) -> None:
    """Records a failed login attempt for rate limiting."""
    now = time.time()
    attempts = _LOGIN_ATTEMPTS.get(ip, [])
    attempts.append(now)
    _LOGIN_ATTEMPTS[ip] = attempts


def clear_failed_logins(ip: str) -> None:
    """Clears failed login attempts after successful authentication."""
    if ip in _LOGIN_ATTEMPTS:
        del _LOGIN_ATTEMPTS[ip]


def get_current_user():
    """Returns the currently authenticated User instance, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


def login_required(f):
    """Decorator ensuring that the endpoint requires an authenticated user session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user is None:
            # Clear invalid session state if user was deleted/deactivated
            session.pop("user_id", None)
            session.pop("username", None)

            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": "Authentication required", "status": 401}), 401

            target = request.full_path if request.query_string else request.path
            # Avoid sending /logout or /login as next target
            if target in [url_for("auth.login"), url_for("auth.logout")]:
                target = None

            flash("Please sign in to access PowerWise.", "warning")
            return redirect(url_for("auth.login", next=target))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user() is not None:
        return redirect(url_for("dashboard"))

    next_url = request.args.get("next") or request.form.get("next") or url_for("dashboard")
    if not is_safe_url(next_url):
        next_url = url_for("dashboard")

    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        if not check_rate_limit(ip):
            flash("Too many failed login attempts. Please wait 5 minutes before trying again.", "error")
            return render_template("login.html", next=next_url), 429

        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        if not identifier or not password:
            flash("Please enter both email/username and password.", "error")
            return render_template("login.html", next=next_url, identifier=identifier)

        user = User.query.filter(
            (db.func.lower(User.email) == identifier) | (db.func.lower(User.username) == identifier)
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash("This account has been deactivated. Please contact support.", "error")
                return render_template("login.html", next=next_url)

            # Successful login: clear and re-initialize session to prevent session fixation
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            if remember:
                session.permanent = True
            clear_failed_logins(ip)

            flash(f"Welcome back, {user.username}!", "success")
            return redirect(next_url)
        else:
            record_failed_login(ip)
            flash("Invalid email/username or password. Please try again.", "error")
            return render_template("login.html", next=next_url, identifier=identifier)

    return render_template("login.html", next=next_url)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if get_current_user() is not None:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Form validations
        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html", username=username, email=email)

        if len(username) < 3 or len(username) > 30 or not re.match(r"^[a-zA-Z0-9_]+$", username):
            flash("Username must be between 3 and 30 characters and contain only letters, numbers, and underscores.", "error")
            return render_template("register.html", username=username, email=email)

        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, email):
            flash("Please provide a valid email address.", "error")
            return render_template("register.html", username=username, email=email)

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("register.html", username=username, email=email)

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html", username=username, email=email)

        existing_user = User.query.filter(
            (db.func.lower(User.username) == username.lower()) | (db.func.lower(User.email) == email)
        ).first()

        if existing_user:
            if existing_user.email.lower() == email:
                flash("An account with this email already exists.", "error")
            else:
                flash("This username is already taken.", "error")
            return render_template("register.html", username=username, email=email)

        # Create user & default settings
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()

        default_settings = UserSettings(
            user_id=new_user.id,
            tariff_band="Band B",
            custom_tariff_rate=68.0,
            preferred_theme="light"
        )
        db.session.add(default_settings)
        db.session.commit()

        # Log user in
        session.clear()
        session["user_id"] = new_user.id
        session["username"] = new_user.username

        flash("Account created successfully! Welcome to PowerWise.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")
