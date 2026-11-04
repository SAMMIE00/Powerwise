"""
Data migration utility to safely import legacy records from user_appliances.json
into the SQLAlchemy database, associating them with a specified user account.
"""
import os
import sys
import json
from app import app
from models import db, User, Appliance, UserSettings


def migrate_json_data(target_username: str = "admin", json_path: str = "user_appliances.json") -> int:
    """Migrates appliances from json_path to the specified user."""
    if not os.path.exists(json_path):
        print(f"[!] Source JSON file '{json_path}' not found. Nothing to migrate.")
        return 0

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] Error reading '{json_path}': {e}")
        return 0

    if not isinstance(data, list) or len(data) == 0:
        print(f"[*] '{json_path}' is empty or contains no records. No action needed.")
        return 0

    with app.app_context():
        user = User.query.filter_by(username=target_username).first()
        if not user:
            print(f"[!] Target user '{target_username}' not found. Please create the user first.")
            return 0

        migrated_count = 0
        for item in data:
            name = str(item.get("name", "Unnamed Appliance")).strip()
            wattage = float(item.get("wattage", 0))
            quantity = int(item.get("quantity", 1))
            hours_per_day = float(item.get("hours_per_day", 0))
            category = str(item.get("category", "General")).strip()

            if wattage <= 0 or hours_per_day <= 0:
                print(f"[-] Skipping invalid record: {item}")
                continue

            # Check if user already has an identical appliance
            existing = Appliance.query.filter_by(
                user_id=user.id,
                name=name,
                wattage=wattage,
                hours_per_day=hours_per_day
            ).first()

            if existing:
                existing.quantity += quantity
            else:
                new_app = Appliance(
                    user_id=user.id,
                    name=name,
                    wattage=wattage,
                    quantity=quantity,
                    hours_per_day=hours_per_day,
                    category=category or "General"
                )
                db.session.add(new_app)
            migrated_count += 1

        db.session.commit()
        print(f"[+] Successfully migrated {migrated_count} appliance record(s) to user '{target_username}'.")
        return migrated_count


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "admin"
    migrate_json_data(target)
