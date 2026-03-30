import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal
from app.models import Base, User
from app.routers.auth import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()

existing = db.query(User).filter(User.username == "admin").first()
if existing:
    db.delete(existing)
    db.commit()

admin = User(
    username="admin",
    full_name="Administrator",
    email="admin@studylink.com",
    hashed_password=hash_password("admin123"),
    staff_name="Admin",
    is_admin=True,
)
db.add(admin)
db.commit()
print("Admin user created!")
db.close()