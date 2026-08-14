from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
import models
from database import engine, get_db
import io
import dsp
import re
import traceback

try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Database table sync warning at startup: {e}")

app = FastAPI(title="Rhythm-Styles API")

# Configure CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

@app.get("/")
def read_root():
    return {"message": "Music Style Transformer API is running", "status": "online"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/upload")
@app.post("/upload/")
async def upload_song(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return {"filename": file.filename, "status": "Uploaded"}

@app.post("/transform")
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
    try:
        # Read file bytes
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file uploaded")
        
        # Process the audio with DSP
        processed_bytes = dsp.process_audio(file_bytes, file.filename or "audio.wav", genre, intensity, effects, surround_3d, bass_boost)
        
        # Sanitize output filename to ASCII
        raw_name = (file.filename or "audio").rsplit('.', 1)[0]
        safe_basename = re.sub(r'[^\w\s\.-]', '', raw_name).strip()
        if not safe_basename:
            safe_basename = "audio"
        out_name = f"transformed_{safe_basename}.wav"
        
        # Save a record to DB (non-blocking if DB is unreachable)
        try:
            new_song = models.Song(filename=file.filename or "audio.wav")
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
            print(f"DB log warning (safe to ignore): {db_err}")
            db.rollback()
        
        # Return the processed bytes as a downloadable file
        return StreamingResponse(
            io.BytesIO(processed_bytes), 
            media_type="audio/wav", 
            headers={"Content-Disposition": f'attachment; filename="{out_name}"'}
        )
    except Exception as e:
        print(f"Transform endpoint error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Audio processing error: {str(e)}")
