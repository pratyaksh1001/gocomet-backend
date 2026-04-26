from sqlalchemy.orm import sessionmaker, scoped_session
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

_real_session = scoped_session(SessionLocal)


class SafeSession:
    def __getattr__(self, name):
        attr = getattr(_real_session, name)

        if callable(attr):
            def wrapper(*args, **kwargs):
                try:
                    return attr(*args, **kwargs)
                except SQLAlchemyError:
                    _real_session.rollback()
                    raise
            return wrapper

        return attr


session = SafeSession()