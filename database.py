from sqlalchemy.orm import DeclarativeBase, sessionmaker, scoped_session
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

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

class SafeSession:
    def __getattr__(self, name):
        attr = getattr(session, name)

        if callable(attr):
            def wrapper(*args, **kwargs):
                try:
                    return attr(*args, **kwargs)
                except SQLAlchemyError:
                    session.rollback()
                    raise
            return wrapper

        return attr


session = SafeSession()