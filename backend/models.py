from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base
import datetime

class PublishHistory(Base):
    __tablename__ = "publish_history"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    payload_title = Column(String(255))
    target_platform = Column(String(50)) # e.g. "Platform X", "Instagram"
    status = Column(String(20)) # "SUCCESS" or "FAILED"
    diagnostics = Column(Text)

class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String(50), primary_key=True, index=True)
    value = Column(Text)
