from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Vehicle(Base):
    __tablename__ = "vehicles"

    vehicle_id = Column(String, primary_key=True, index=True)
    vin = Column(String, nullable=False)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(String, nullable=False)
    trend_history = Column(JSON, default=dict)

    trips = relationship("Trip", back_populates="vehicle")

class Trip(Base):
    __tablename__ = "trips"

    session_id = Column(String, primary_key=True, index=True)
    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    csv_path = Column(String, nullable=False)
    features = Column(JSON, default=dict)
    events = Column(JSON, default=list)
    report_text = Column(String, default="")

    vehicle = relationship("Vehicle", back_populates="trips")
