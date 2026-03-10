from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime
from typing import List

from database import get_db, init_db
from models import Vehicle, Trip
from pipeline.ingest import ingest_and_normalize
from pipeline.signal import process_signals
from pipeline.features import compute_features
from pipeline.rules import apply_diagnostic_rules
from pipeline.trends import analyze_trends
from pipeline.llm_report import generate_report_stream, generate_report

app = FastAPI(title="Acty - Vehicle Preventive Maintenance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    os.makedirs("./uploads", exist_ok=True)
    os.makedirs("./data", exist_ok=True)
    init_db()

@app.get("/")
def root():
    return {"message": "Acty API is running", "version": "1.0.0"}

@app.post("/vehicles")
def create_vehicle(
    vehicle_id: str,
    vin: str,
    make: str,
    model: str,
    year: str,
    db: Session = Depends(get_db)
):
    existing = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vehicle already exists")

    vehicle = Vehicle(
        vehicle_id=vehicle_id,
        vin=vin,
        make=make,
        model=model,
        year=year,
        trend_history={}
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    return {
        "vehicle_id": vehicle.vehicle_id,
        "vin": vehicle.vin,
        "make": vehicle.make,
        "model": vehicle.model,
        "year": vehicle.year
    }

@app.get("/vehicles/{vehicle_id}/trips")
def get_vehicle_trips(vehicle_id: str, db: Session = Depends(get_db)):
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    trips = db.query(Trip).filter(Trip.vehicle_id == vehicle_id).order_by(Trip.uploaded_at.desc()).all()

    return {
        "vehicle": {
            "vehicle_id": vehicle.vehicle_id,
            "make": vehicle.make,
            "model": vehicle.model,
            "year": vehicle.year,
            "trend_history": vehicle.trend_history
        },
        "trips": [
            {
                "session_id": trip.session_id,
                "uploaded_at": trip.uploaded_at.isoformat(),
                "features": trip.features,
                "events": trip.events
            }
            for trip in trips
        ]
    }

@app.post("/trips/upload")
async def upload_trip(
    file: UploadFile = File(...),
    vehicle_id: str = "default",
    db: Session = Depends(get_db)
):
    session_id = str(uuid.uuid4())
    csv_path = f"./uploads/{session_id}.csv"

    with open(csv_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        normalized_df, ingest_meta = ingest_and_normalize(csv_path)

        processed_df, signal_meta = process_signals(normalized_df)

        features = compute_features(processed_df)

        events = apply_diagnostic_rules(processed_df, features)

        trends = analyze_trends(db, vehicle_id, features)

        report_text = await generate_report(events, features, trends)

        trip = Trip(
            session_id=session_id,
            vehicle_id=vehicle_id,
            uploaded_at=datetime.utcnow(),
            csv_path=csv_path,
            features=features,
            events=events,
            report_text=report_text
        )
        db.add(trip)
        db.commit()

        return {
            "session_id": session_id,
            "vehicle_id": vehicle_id,
            "features": features,
            "events": events,
            "trends": trends,
            "report_preview": report_text[:200] + "..."
        }

    except Exception as e:
        if os.path.exists(csv_path):
            os.remove(csv_path)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

@app.get("/trips/{session_id}")
def get_trip(session_id: str, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.session_id == session_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    return {
        "session_id": trip.session_id,
        "vehicle_id": trip.vehicle_id,
        "uploaded_at": trip.uploaded_at.isoformat(),
        "features": trip.features,
        "events": trip.events,
        "report_text": trip.report_text
    }

@app.get("/trips/{session_id}/stream-report")
async def stream_report(session_id: str, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.session_id == session_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == trip.vehicle_id).first()
    trends = {"trends": vehicle.trend_history} if vehicle and vehicle.trend_history else None

    async def event_generator():
        async for chunk in generate_report_stream(trip.events, trip.features, trends):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
