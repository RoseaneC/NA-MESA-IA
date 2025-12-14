"""
Optional seed data for development and demonstration.
Run this to populate the database with sample organizations.

Usage:
    cd /path/to/project
    python app/db/seed.py
"""

import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Organization, User


def seed_sample_data():
    """Seed the database with sample organizations for testing."""
    db = SessionLocal()

    try:
        # Check if data already exists
        existing_orgs = db.query(Organization).count()
        if existing_orgs > 0:
            print("Database already has data, skipping seed.")
            return

        # Sample organizations
        sample_orgs = [
            {
                "name": "Banco de Alimentos São Paulo",
                "phone": "+5511999990001",
                "coverage_area": "Centro, Sé, Liberdade, Bela Vista",
                "can_pickup": True,
                "hours": "Segunda a sexta, 8h às 17h",
                "active": True
            },
            {
                "name": "ONG Alimenta Vida",
                "phone": "+5511999990002",
                "coverage_area": "Vila Mariana, Saúde, Paraíso",
                "can_pickup": False,
                "hours": "Terça a sábado, 9h às 16h",
                "active": True
            },
            {
                "name": "Projeto Fome Zero",
                "phone": "+5511999990003",
                "coverage_area": "Pinheiros, Vila Madalena, Perdizes",
                "can_pickup": True,
                "hours": "Segunda a sexta, 10h às 18h",
                "active": True
            },
            {
                "name": "Casa do Pão São Paulo",
                "phone": "+5511999990004",
                "coverage_area": "Mooca, Brás, Pari",
                "can_pickup": False,
                "hours": "Segunda a sábado, 8h às 20h",
                "active": True
            },
            {
                "name": "Instituto Compartilhar",
                "phone": "+5511999990005",
                "coverage_area": "Itaquera, São Miguel, Vila Jacuí",
                "can_pickup": True,
                "hours": "Terça a domingo, 9h às 17h",
                "active": True
            }
        ]

        created_count = 0
        for org_data in sample_orgs:
            # Create user for organization
            user = User(
                phone=org_data["phone"],
                role="org"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # Create organization
            org = Organization(
                user_id=user.id,
                **org_data
            )
            db.add(org)
            created_count += 1

        db.commit()
        print(f"✅ Successfully seeded {created_count} sample organizations")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding data: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_sample_data()
