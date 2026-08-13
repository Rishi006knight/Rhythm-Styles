# Rhythm-Styles 🎵

> **Transform your song in different style**

Rhythm-Styles is a modern, full-stack web application designed to transform uploaded audio tracks across **10 distinct musical genres**, featuring dynamic genre-specific effect controls, 8D 3D Surround audio spatialization, and customizable bass boosting.

---

## 🌟 Inspiration & Background

The core concept for **Rhythm-Styles** was inspired by the iconic **Neon Mixtape Tour** world in *Plants vs. Zombies 2*, where dynamic genre jams alter the tempo, energy, and atmosphere of the game. 

Additionally, the project celebrates the legendary pillars of retro music evolution: **Pop**, **Rap**, and **8-Bit Chiptunes**, which reigned supreme as the acoustic beasts of the 1980s. Rhythm-Styles reimagines these sonic profiles through modern digital signal processing (DSP).

---

## 🎛️ Features

- **10 Distinct Genre Transformations**:
  1. 🎸 **Rock** — Distortion, Overdrive, Reverb, Drum Impact
  2. 🎤 **Pop** — Reverb, Chorus, Delay, Compression
  3. 🪩 **Disco** — Groove, Bass Punch, Chorus, Reverb
  4. 🎮 **8-bit / Chiptune** — Bit Crush, Downsampling, 8-bit Synthesis, Retro Filter
  5. 🌌 **Synthwave / 1980s** — Chorus, Delay, Reverb, Retro Filter
  6. 🤘 **Metal** — Distortion, Compression, Drum Impact, Low-End
  7. 🎹 **Ballad** — Reverb, Delay, Warmth, Dynamics
  8. 🌴 **Reggae** — Bass, Offbeat Groove, Delay, Reverb
  9. 🕺 **Funk** — Bass Groove, Compression, Wah/Filter, Drum Groove
  10. 🎷 **Jazz** — Swing, Reverb, Warmth, Improvisation

- **Global Audio Enhancements**:
  - 🎧 **3D Surround (8D Audio)**: Sinusoidal equal-power auto-panning combined with Haas effect stereo widening for an immersive spatial headphone experience.
  - 🔊 **Custom Bass Boost (0–100%)**: Low-pass Butterworth filtering isolating sub-150Hz frequencies with adjustable gain multipliers.

- **Audio Playback & Download**: Immediate in-browser preview and one-click `.wav` download.

---

## 🏗️ Architecture & Tech Stack

| Layer | Technology |
| --- | --- |
| **Frontend** | React 18, Vite, Vanilla CSS (Glassmorphism design) |
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Database** | PostgreSQL (Neon Cloud DB), SQLAlchemy ORM |
| **Audio Processing** | Librosa, SciPy, SoundFile, NumPy |

---

## 🚀 Getting Started

### Prerequisites
- Node.js (v18+)
- Python 3.11+

### 1. Clone the Repository
```bash
git clone https://github.com/Rishi006knight/Rhythm-Styles.git
cd Rhythm-Styles
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate   # On Windows
source venv/bin/activate  # On macOS/Linux

python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0
```
Backend will run at: `http://127.0.0.1:8000`

### 3. Frontend Setup
```bash
cd ../frontend
npm install
npm run dev
```
Frontend will run at: `http://localhost:5173`

---

## 📜 License
MIT License. Built with passion for music & code!
