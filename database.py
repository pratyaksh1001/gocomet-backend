from sqlalchemy.orm import DeclarativeBase, sessionmaker, scoped_session
from sqlalchemy import create_engine

db_uri = "postgresql+psycopg2://qqqecejyqknddoebyvpa:mdxrifdespgvqjfekxnugzmqwhkyve@9qasp5v56q8ckkf5dc.leapcellpool.com:6438/kyfywbbcfwpfevczjkkh?sslmode=require"

engine = create_engine(
    db_uri,
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

session = scoped_session(SessionLocal)