"""
SQLAlchemy models for PowerWise.
Provides models for User, Appliance, UserSettings, and UsageHistory.
"""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    appliances = db.relationship("Appliance", backref="user", cascade="all, delete-orphan", lazy="select")
    settings = db.relationship("UserSettings", backref="user", uselist=False, cascade="all, delete-orphan", lazy="select")
    usage_history = db.relationship("UsageHistory", backref="user", cascade="all, delete-orphan", lazy="select")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class UserSettings(db.Model):
    __tablename__ = "user_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    tariff_band = db.Column(db.String(30), default="Band B", nullable=True)
    custom_tariff_rate = db.Column(db.Float, default=68.0, nullable=False)
    preferred_theme = db.Column(db.String(20), default="light", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    @property
    def rate(self) -> float:
        return float(self.custom_tariff_rate) if self.custom_tariff_rate is not None else 68.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tariff_band": self.tariff_band,
            "custom_tariff_rate": self.custom_tariff_rate,
            "preferred_theme": self.preferred_theme,
        }


class Appliance(db.Model):
    __tablename__ = "appliances"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    wattage = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    hours_per_day = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(60), default="General", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    @property
    def daily_kwh(self) -> float:
        return round((self.wattage * self.quantity * self.hours_per_day) / 1000.0, 3)

    @property
    def monthly_kwh(self) -> float:
        return round(self.daily_kwh * 30, 2)

    def to_dict(self, rate_per_kwh: float = 68.0) -> dict:
        d_kwh = self.daily_kwh
        m_kwh = self.monthly_kwh
        m_cost = round(m_kwh * rate_per_kwh, 2)
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "wattage": self.wattage,
            "quantity": self.quantity,
            "hours_per_day": self.hours_per_day,
            "category": self.category,
            "daily_kwh": d_kwh,
            "monthly_kwh": m_kwh,
            "monthly_cost": m_cost,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Appliance {self.name} ({self.wattage}W)>"


class UsageHistory(db.Model):
    __tablename__ = "usage_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    appliance_id = db.Column(db.Integer, db.ForeignKey("appliances.id", ondelete="SET NULL"), nullable=True)
    recorded_month = db.Column(db.String(7), nullable=False, index=True)  # YYYY-MM
    energy_consumption = db.Column(db.Float, nullable=False)  # kWh
    estimated_cost = db.Column(db.Float, nullable=False)      # ₦
    tariff_rate = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    # Optional relationship to appliance
    appliance = db.relationship("Appliance", backref="history_entries", lazy="select")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "appliance_id": self.appliance_id,
            "appliance_name": self.appliance.name if self.appliance else "Unknown Appliance",
            "recorded_month": self.recorded_month,
            "energy_consumption": self.energy_consumption,
            "estimated_cost": self.estimated_cost,
            "tariff_rate": self.tariff_rate,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
