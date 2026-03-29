import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal
from app.models import Base, User

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

existing = db.query(User).filter(User.username == "admin").first()
if not existing:
    # Pre-hashed version of "changeme123"
    admin = User(
        username="admin",
        full_name="Administrator",
        email="admin@studylink.com",
        hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        staff_name="Admin",
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    print("Admin user created!")
else:
    print("Admin user already exists.")

db.close()