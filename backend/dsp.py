import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter
import json
import tempfile
import os

# ─────────────────────────────────────────────
# HIGH-IMPACT VECTORIZED DSP ENGINE
# Fast, audible, character-rich genre styling
# ─────────────────────────────────────────────

def _norm(y, headroom=0.92):
    peak = np.max(np.abs(y))
    if peak > 1e-6:
        y = (y / peak) * headroom
    return y

def _butter_filter(y, sr, cutoff, btype='low', order=2):
    nyq = 0.5 * sr
    if isinstance(cutoff, (list, tuple)):
        norm = [np.clip(c / nyq, 1e-4, 0.99) for c in cutoff]
    else:
        norm = np.clip(cutoff / nyq, 1e-4, 0.99)
    b, a = butter(order, norm, btype=btype)
    return lfilter(b, a, y)

def _fast_reverb(y, sr, room_ms=90, decay=0.5):
    """Spacious comb-filter reverb"""
    delay = max(int(sr * (room_ms / 1000.0)), 1)
    out = y.copy()
    for k in range(1, 5):
        d = delay * k
        if d < len(out):
            out[d:] += y[:-d] * (decay ** k)
    return _norm(out)

def _fast_chorus(y, sr, depth_ms=18, rate_hz=0.9, mix=0.55):
    """Vectorized analog chorus / flanger"""
    n_samples = len(y)
    t = np.arange(n_samples) / sr
    base_delay = int(sr * (depth_ms / 1000.0))
    
    mod1 = (np.sin(2 * np.pi * rate_hz * t) * (base_delay * 0.45)).astype(np.int32) + base_delay
    mod2 = (np.cos(2 * np.pi * (rate_hz * 1.4) * t) * (base_delay * 0.55)).astype(np.int32) + int(base_delay * 1.3)
    
    indices = np.arange(n_samples)
    idx1 = np.clip(indices - mod1, 0, n_samples - 1)
    idx2 = np.clip(indices - mod2, 0, n_samples - 1)
    
    wet = (y[idx1] + y[idx2]) * 0.5
    return _norm(y * (1.0 - mix * 0.6) + wet * mix)

def _fast_delay(y, sr, delay_ms=350, feedback=0.45, mix=0.4):
    """Vectorized rhythmic delay with feedback"""
    d_samples = max(int(sr * (delay_ms / 1000.0)), 1)
    out = y.copy()
    echo = y.copy()
    for _ in range(4):
        echo = np.pad(echo, (d_samples, 0))[:len(y)] * feedback
        out += echo * mix
    return _norm(out)

def _distort(y, gain=8.0, soft=True):
    """Heavy saturation and distortion"""
    yg = y * gain
    if soft:
        return _norm(np.tanh(yg * 1.5))
    else:
        return _norm(np.clip(yg, -0.7, 0.7))

def _bit_crush(y, bits=5):
    """Arcade / Chiptune quantization"""
    levels = 2 ** bits
    step = 2.0 / levels
    return np.round(y / step) * step

def _fast_wah(y, sr, rate_hz=1.8):
    """Vectorized Funk Wah-Wah LFO Modulation"""
    t = np.arange(len(y)) / sr
    lfo = 0.5 * (1.0 + np.sin(2 * np.pi * rate_hz * t))
    mid = _butter_filter(y, sr, [350, 2600], btype='bandpass', order=2)
    return _norm(y * 0.35 + (mid * (1.5 + 1.2 * lfo)))

def apply_bass_boost(y_mono, sr, boost_percent):
    if boost_percent <= 0:
        return y_mono
    low = _butter_filter(y_mono, sr, 150.0, btype='low', order=2)
    boost_factor = (boost_percent / 100.0) * 4.0
    return _norm(y_mono + low * boost_factor)

def apply_3d_surround(y_mono, sr):
    length = len(y_mono)
    time = np.arange(length) / sr
    lfo = np.sin(2 * np.pi * 0.15 * time)
    angle = (lfo + 1) * (np.pi / 4)
    
    y_stereo = np.zeros((length, 2), dtype=np.float32)
    y_stereo[:, 0] = y_mono * np.cos(angle)
    y_stereo[:, 1] = y_mono * np.sin(angle)
    
    delay_samples = int(0.018 * sr)
    if delay_samples < length:
        y_stereo[delay_samples:, 1] += y_stereo[:-delay_samples, 0] * 0.35
        y_stereo[delay_samples:, 0] += y_stereo[:-delay_samples, 1] * 0.35
        
    return _norm(y_stereo)

def _scale(intensity, low, med, high):
    return {'Low': low, 'Medium': med, 'High': high}.get(intensity, med)

def _effect_level(effects, key, intensity):
    return effects.get(key, intensity)

# ─────────────────────────────────────────────
# MAIN PROCESSING ENTRYPOINT
# ─────────────────────────────────────────────
def process_audio(file_bytes: bytes, filename: str, genre: str, intensity: str,
                  effects_json: str, surround_3d: bool = False, bass_boost: int = 0, volume: int = 100) -> bytes:
    try:
        bass_boost = int(bass_boost)
    except (ValueError, TypeError):
        bass_boost = 0

    try:
        volume = int(volume)
    except (ValueError, TypeError):
        volume = 100

    if isinstance(surround_3d, str):
        surround_3d = surround_3d.lower() in ('true', '1', 'yes')

    ext = os.path.splitext(filename)[1] or '.wav'

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(file_bytes)
        tmp_in = tmp.name

    out_path = tmp_in + '_out.wav'

    try:
        target_sr = 24000
        y, sr = librosa.load(tmp_in, sr=target_sr, mono=True)

        try:
            effects = json.loads(effects_json)
        except Exception:
            effects = {}

        reverb_ms = _scale(intensity, 50, 85, 130)
        reverb_decay = _scale(intensity, 0.35, 0.5, 0.65)

        # ════════════════════════════════════════════════
        # DRAMATIC GENRE PROCESSING
        # ════════════════════════════════════════════════

        if genre == 'Rock':
            dist_level = _effect_level(effects, 'Distortion', intensity)
            gain = _scale(dist_level, 6.0, 12.0, 20.0)
            y = _distort(y, gain=gain, soft=True)
            low = _butter_filter(y, sr, 120, btype='low')
            y = _norm(y + low * _scale(intensity, 0.6, 1.0, 1.5))
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay * 0.8)

        elif genre == 'Pop':
            y = _fast_chorus(y, sr, depth_ms=12, rate_hz=0.8, mix=_scale(intensity, 0.4, 0.6, 0.8))
            y = _fast_delay(y, sr, delay_ms=260, feedback=0.3, mix=0.25)
            high = _butter_filter(y, sr, 4000, btype='high')
            y = _norm(y + high * _scale(intensity, 0.5, 0.8, 1.2))

        elif genre == 'Disco':
            low = _butter_filter(y, sr, 140, btype='low')
            high = _butter_filter(y, sr, 3500, btype='high')
            y = _norm(y + low * _scale(intensity, 0.8, 1.3, 2.0) + high * 0.7)
            y = _fast_chorus(y, sr, depth_ms=18, rate_hz=1.2, mix=_scale(intensity, 0.45, 0.65, 0.85))
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay)

        elif genre == '8-bit':
            # Severe bit reduction + downsample decimation
            bit_level = _effect_level(effects, 'Bit Crush', intensity)
            bits = _scale(bit_level, 6, 4, 3)
            y = _bit_crush(y, bits=int(bits))
            step_factor = _scale(intensity, 3, 4, 6)
            y = np.repeat(y[::step_factor], step_factor)[:len(y)]
            mid = _butter_filter(y, sr, [700, 2800], btype='bandpass')
            y = _norm(y * 0.4 + mid * 1.1)

        elif genre == 'Synthwave':
            filter_level = _effect_level(effects, 'Retro Filter', intensity)
            cutoff = _scale(filter_level, 3800, 2600, 1600)
            y = _butter_filter(y, sr, cutoff, btype='low')
            y = _fast_chorus(y, sr, depth_ms=24, rate_hz=0.6, mix=_scale(intensity, 0.5, 0.7, 0.9))
            y = _fast_delay(y, sr, delay_ms=420, feedback=_scale(intensity, 0.35, 0.5, 0.65), mix=0.4)
            y = _fast_reverb(y, sr, room_ms=reverb_ms * 1.5, decay=reverb_decay)

        elif genre == 'Metal':
            dist_level = _effect_level(effects, 'Distortion', intensity)
            gain = _scale(dist_level, 15.0, 28.0, 45.0)
            y = _distort(y, gain=gain, soft=False)
            mid = _butter_filter(y, sr, [350, 2000], btype='bandpass')
            low = _butter_filter(y, sr, 120, btype='low')
            y = _norm((y - mid * 0.6) + low * 1.2)

        elif genre == 'Ballad':
            warm = _butter_filter(y, sr, [160, 850], btype='bandpass')
            y = _norm(y + warm * _scale(intensity, 0.5, 0.8, 1.2))
            y = _fast_reverb(y, sr, room_ms=reverb_ms * 2.0, decay=reverb_decay * 1.3)

        elif genre == 'Reggae':
            y = _fast_delay(y, sr, delay_ms=_scale(intensity, 280, 360, 480),
                            feedback=_scale(intensity, 0.4, 0.55, 0.7), mix=0.45)
            low = _butter_filter(y, sr, 110, btype='low')
            y = _norm(y + low * _scale(intensity, 1.0, 1.8, 2.6))
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay * 0.7)

        elif genre == 'Funk':
            y = _fast_wah(y, sr, rate_hz=_scale(intensity, 1.4, 2.0, 2.8))
            low = _butter_filter(y, sr, 130, btype='low')
            y = _norm(y + low * _scale(intensity, 0.7, 1.2, 1.8))

        elif genre == 'Jazz':
            y = _butter_filter(y, sr, _scale(intensity, 5500, 4000, 2800), btype='low')
            warm = _butter_filter(y, sr, [130, 700], btype='bandpass')
            y = _norm(y + warm * _scale(intensity, 0.4, 0.8, 1.2))
            y = _fast_reverb(y, sr, room_ms=reverb_ms * 1.4, decay=reverb_decay)

        else:
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay)

        # ── GLOBAL ENHANCEMENTS ──
        if bass_boost > 0:
            y = apply_bass_boost(y, sr, bass_boost)

        if surround_3d:
            y = apply_3d_surround(y, sr)

        # Master Output Volume Scaling
        vol_factor = max(volume / 100.0, 0.0)
        y = np.clip(y * vol_factor, -1.0, 1.0)

        sf.write(out_path, y, sr, format='WAV')

        with open(out_path, 'rb') as f:
            return f.read()

    except Exception as e:
        print(f"DSP Error: {e}")
        import traceback
        traceback.print_exc()
        return file_bytes

    finally:
        for p in (tmp_in, out_path):
            if os.path.exists(p):
                os.remove(p)
