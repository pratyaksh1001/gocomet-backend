from sqlalchemy.orm import DeclarativeBase,Session
from sqlalchemy import create_engine

db_uri="sqlite:///gocomet.db"
engine=create_engine(db_uri)
session=Session(engine)