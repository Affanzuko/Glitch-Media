from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# User configured: port 3306, user root, no password, db glitch_media
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost:3306/glitch_media"

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
