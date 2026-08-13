from fastapi import FastAPI, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
import models
from database import engine, get_db
import io
import dsp

import re

try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Database connection warning at startup: {e}")

app = FastAPI(title="Rhythm-Styles API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Music Style Transformer API is running"}

@app.post("/upload/")
async def upload_song(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Basic upload structure
    # TODO: Save file to disk/storage
    return {"filename": file.filename, "status": "Uploaded"}

@app.post("/transform/")
async def transform_song(
    file: UploadFile = File(...),
    genre: str = Form(...),
    intensity: str = Form(...),
    effects: str = Form(default="{}"),
    surround_3d: bool = Form(default=False),
    bass_boost: int = Form(default=0),
    db: Session = Depends(get_db)
):
    # Read file bytes
    file_bytes = await file.read()
    
    # Process the audio with DSP
    processed_bytes = dsp.process_audio(file_bytes, file.filename, genre, intensity, effects, surround_3d, bass_boost)
    
    # Sanitize output filename to ASCII to prevent HTTP header encoding errors with special/unicode characters
    raw_name = file.filename.rsplit('.', 1)[0]
    safe_basename = re.sub(r'[^\w\s\.-]', '', raw_name).strip()
    if not safe_basename:
        safe_basename = "audio"
    out_name = f"transformed_{safe_basename}.wav"
    
    # Save a record to DB (non-blocking if DB is unreachable)
    try:
        new_song = models.Song(filename=file.filename)
        db.add(new_song)
        db.commit()
        db.refresh(new_song)
        
        new_transform = models.Transformation(
            song_id=new_song.id,
            genre=genre,
            intensity=intensity,
            output_filename=out_name
        )
        db.add(new_transform)
        db.commit()
    except Exception as db_err:
        print(f"DB log warning: {db_err}")
        db.rollback()
    
    # Return the processed bytes as a downloadable file
    return StreamingResponse(
        io.BytesIO(processed_bytes), 
        media_type="audio/wav", 
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'}
    )
