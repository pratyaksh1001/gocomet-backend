from sqlalchemy.orm import DeclarativeBase,Session
from sqlalchemy import create_engine

#db_uri="postgresql://avnadmin:AVNS_TTmgJqSs46sRCS2hQi8@pratyaksh-db-pratyakshkarmahe-gocomet.c.aivencloud.com:13421/defaultdb?sslmode=require"
db_uri="sqlite:///gocomet.db"
engine=create_engine(db_uri)
session=Session(engine)