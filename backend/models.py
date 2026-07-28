from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base
import datetime

class PublishHistory(Base):
    __tablename__ = "publish_history"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    payload_title = Column(String(255))
    target_platform = Column(String(50)) # e.g. "Platform X", "Instagram"
    status = Column(String(20)) # "SUCCESS" or "FAILED" or "UNPUBLISHED"
    diagnostics = Column(Text)
    caption_x = Column(Text, nullable=True)
    caption_ig = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    news_title = Column(String(255), nullable=True)

class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String(50), primary_key=True, index=True)
    value = Column(Text)
