import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Load .env dari root project
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Ambil URL dari .env, fallback ke localhost jika tidak ada
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "mysql+pymysql://root:@localhost:3306/glitch_media"
)

# Handle Aiven MySQL connection string (convert mysql:// to mysql+pymysql://)
if SQLALCHEMY_DATABASE_URL.startswith("mysql://") and "+pymysql" not in SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
