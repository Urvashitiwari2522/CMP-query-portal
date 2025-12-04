"""Initialize the database and create a default admin user.

Default admin credentials:
- username: admin
- password: admin123

Run: python -m backend.init_db
"""
from __future__ import annotations

from .models import init_db, create_admin


def main() -> None:
    init_db()
    try:
        create_admin("admin", "admin123", "admin@example.com")
        print("Default admin created: username='admin', password='admin123'")
    except Exception as e:
        # Likely already exists due to UNIQUE constraint
        print(f"Admin creation skipped or failed: {e}")
    print("Database initialized successfully.")


if __name__ == "__main__":
    main()
