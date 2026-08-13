from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from database import Base

class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Transformation(Base):
    __tablename__ = "transformations"

    id = Column(Integer, primary_key=True, index=True)
    song_id = Column(Integer, index=True)
    genre = Column(String, index=True)
    intensity = Column(String)
    output_filename = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
