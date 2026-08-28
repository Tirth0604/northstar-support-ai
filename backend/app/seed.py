"""Create the full synthetic Northstar demonstration dataset."""

from app.db.session import SessionLocal, init_db
from app.services.seed import seed_demo_data

if __name__ == "__main__":
    init_db()
    with SessionLocal() as session:
        print(seed_demo_data(session))
