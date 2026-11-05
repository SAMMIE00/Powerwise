"""
Management CLI script for PowerWise.
Provides commands for database initialization, administrator provisioning,
and legacy JSON data migration.
"""
import sys
import argparse
from getpass import getpass
from sqlalchemy import inspect, text
from app import app
from models import db, User, UserSettings
from migrate_json import migrate_json_data


def ensure_role_column():
    """Safely add the role column to existing users tables."""
    inspector = inspect(db.engine)

    if not inspector.has_table("users"):
        raise RuntimeError("Users table does not exist.")

    columns = {column["name"] for column in inspector.get_columns("users")}

    if "role" not in columns:
        with db.engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"
                )
            )
        print("[+] Added missing users.role column.")
    else:
        print("[+] users.role column already exists.")


def init_db():
    """Initializes the database schema."""
    with app.app_context():
        db.create_all()
        ensure_role_column()
        print("[+] Database tables created successfully.")


def create_admin(username, email, password):
    """Creates or promotes an administrator account."""
    with app.app_context():
        db.create_all()
        ensure_role_column()

        username_match = User.query.filter_by(username=username).first()
        email_match = User.query.filter_by(email=email).first()

        # Never promote an ambiguous or conflicting account.
        if (
            username_match is not None
            and email_match is not None
            and username_match.id != email_match.id
        ):
            raise ValueError(
                "The username and email belong to different accounts. "
                "Resolve the conflict before creating an administrator."
            )

        user = username_match or email_match

        if user:
            print(f"[*] Existing account '{user.username}' found. Promoting to administrator.")
            user.role = "admin"
            user.is_active = True
            user.set_password(password)
        else:
            user = User(
                username=username,
                email=email,
                role="admin",
                is_active=True
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            print(f"[+] Administrator account '{username}' created.")

        # Ensure the administrator has default settings.
        if user.settings is None:
            settings = UserSettings(
                user_id=user.id,
                tariff_band="Band B",
                custom_tariff_rate=68.0,
                preferred_theme="light"
            )
            db.session.add(settings)

        db.session.commit()
        print(f"[+] '{user.username}' now has administrator privileges.")



def main():
    parser = argparse.ArgumentParser(description="PowerWise Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-db
    subparsers.add_parser("init-db", help="Create database tables")

    # create-admin
    admin_parser = subparsers.add_parser("create-admin", help="Create an administrator account")
    admin_parser.add_argument("--username", "-u", default="admin", help="Admin username")
    admin_parser.add_argument("--email", "-e", default="admin@powerwise.ng", help="Admin email")

    # migrate-json
    migrate_parser = subparsers.add_parser("migrate-json", help="Migrate user_appliances.json into database")
    migrate_parser.add_argument("--username", "-u", default="admin", help="Target user for migrated appliances")
    migrate_parser.add_argument("--file", "-f", default="user_appliances.json", help="Source JSON file")

    args = parser.parse_args()

    if args.command == "init-db":
        init_db()
    elif args.command == "create-admin":
        password = getpass("Enter administrator password: ")
        confirmation = getpass("Confirm administrator password: ")

        if password != confirmation:
            raise SystemExit("[-] Passwords do not match.")

        if len(password) < 12:
            raise SystemExit("[-] Password must contain at least 12 characters.")

        create_admin(args.username, args.email, password)
    elif args.command == "migrate-json":
        migrate_json_data(args.username, args.file)


if __name__ == "__main__":
    main()
