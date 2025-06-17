from sqlalchemy import create_engine, inspect, Column, Integer, String, Text, Boolean, DateTime, JSON, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from config.settings import settings
import logging


logging.basicConfig(level=logging.INFO)
Base = declarative_base()


def get_db_url():
    user = settings.db_user
    password = settings.db_password
    host = settings.db_host
    port = settings.db_port
    db_name = settings.db_name
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


engine = create_engine(get_db_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Discussion(Base):
    __tablename__ = 'discussion'

    # 添加唯一约束
    __table_args__ = (
        UniqueConstraint('source_id', name='uq_discussion_source_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Text, nullable=False, unique=True)
    title = Column(String(255), nullable=False)
    body = Column(Text)
    url = Column(String(512))
    clean_data = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    topic_summary = Column(Text)
    topic_closed = Column(Boolean, default=False)
    source_type = Column(String(50), nullable=False)
    history = Column(JSON)
    source_closed = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)


def check_and_create_tables():
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    required_tables = Base.metadata.tables.keys()

    missing_tables = [tbl for tbl in required_tables if tbl not in existing_tables]
    if missing_tables:
        Base.metadata.create_all(bind=engine)
        print(f"已自动创建缺失的数据表: {', '.join(missing_tables)}")
