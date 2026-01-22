from sqlmodel import SQLModel, create_engine, Session
import os

# 1. IMPORT EVERYTHING
# This registers the tables in SQLModel's metadata registry
from app.models.location import Location
from app.models.evse import EVSE
from app.models.connector import Connector

# 2. SETUP ENGINE
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:////Users/ericpalonsky/IdeaProjects/emspProjectv1/app/{sqlite_file_name}"

# echo=True prints the SQL to your terminal so you can see the tables being created
engine = create_engine(sqlite_url, echo=False)

def create_db_and_tables():
    print("Creating database and tables...")
    # 3. GENERATE
    if os.path.exists(sqlite_file_name):
        os.remove(sqlite_file_name)
        print(f"Deleted old {sqlite_file_name}")

    print("Creating fresh tables...")
    SQLModel.metadata.create_all(engine)
    print("Done!")

def get_session():
    with Session(engine) as session:
        yield session

if __name__ == "__main__":
    create_db_and_tables()