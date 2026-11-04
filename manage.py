"""
Management CLI script for PowerWise.
Provides commands for database initialization, administrator provisioning,
and legacy JSON data migration.
"""
import sys
import argparse
from app import app
from models import db, User, UserSettings
from migrate_json import migrate_json_data


def init_db():
    """Initializes the database schema."""
    with app.app_context():
        db.create_all()
        print("[+] Database tables created successfully.")


def create_admin(username, email, password):
    """Creates or updates an administrator user."""
    with app.app_context():
        db.create_all()
        user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if user:
            print(f"[*] User '{username}' / '{email}' already exists. Updating password...")
            user.set_password(password)
            user.is_active = True
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            settings = UserSettings(
                user_id=user.id,
                tariff_band="Band B",
                custom_tariff_rate=68.0,
                preferred_theme="light"
            )
            db.session.add(settings)
            print(f"[+] Administrator account '{username}' created successfully.")

        db.session.commit()


def main():
    parser = argparse.ArgumentParser(description="PowerWise Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-db
    subparsers.add_parser("init-db", help="Create database tables")

    # create-admin
    admin_parser = subparsers.add_parser("create-admin", help="Create an administrator account")
    admin_parser.add_argument("--username", "-u", default="admin", help="Admin username")
    admin_parser.add_argument("--email", "-e", default="admin@powerwise.ng", help="Admin email")
    admin_parser.add_argument("--password", "-p", required=True, help="Admin password")

    # migrate-json
    migrate_parser = subparsers.add_parser("migrate-json", help="Migrate user_appliances.json into database")
    migrate_parser.add_argument("--username", "-u", default="admin", help="Target user for migrated appliances")
    migrate_parser.add_argument("--file", "-f", default="user_appliances.json", help="Source JSON file")

    args = parser.parse_args()

    if args.command == "init-db":
        init_db()
    elif args.command == "create-admin":
        create_admin(args.username, args.email, args.password)
    elif args.command == "migrate-json":
        migrate_json_data(args.username, args.file)


if __name__ == "__main__":
    main()
