import os
import ssl
from urllib.parse import urlparse, urlunparse, parse_qs
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

# PyMySQL tidak mengenali query param 'ssl-mode' (format ini khusus mysql-connector-python).
# Kalau ada di URL (misal dari Aiven), buang dari connection string dan terjemahkan
# jadi SSL context yang dikirim lewat connect_args, bukan lewat URL.
connect_args = {}
parsed = urlparse(SQLALCHEMY_DATABASE_URL)
query_params = parse_qs(parsed.query)

if "ssl-mode" in query_params or "ssl_mode" in query_params:
    ssl_context = ssl.create_default_context()
    # Aiven menyediakan CA cert valid di dashboard-nya (Service -> Overview -> CA Certificate).
    # Untuk verifikasi penuh, ganti dua baris di bawah dengan:
    #   ssl_context = ssl.create_default_context(cafile="/path/ke/ca.pem")
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context
    # Bersihkan query string supaya tidak ikut dikirim sebagai kwarg ke pymysql.connect()
    SQLALCHEMY_DATABASE_URL = urlunparse(parsed._replace(query=""))

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()