import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter, fftconvolve
import json
import tempfile
import os

# ─────────────────────────────────────────────
# HIGH-SPEED VECTORIZED DSP ENGINE
# Optimized for fast CPU execution (<1-2 sec)
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

def _fast_reverb(y, sr, room_ms=80, decay=0.45):
    """Ultra-fast comb-filter reverb without convolution bottlenecks"""
    delay = max(int(sr * (room_ms / 1000.0)), 1)
    out = y.copy()
    for k in range(1, 4):
        d = delay * k
        if d < len(out):
            out[d:] += y[:-d] * (decay ** k)
    return _norm(out)

def _fast_chorus(y, sr, depth_ms=15, rate_hz=0.8, mix=0.45):
    """Vectorized modulated delay chorus (Instant - no STFT phase vocoder)"""
    n_samples = len(y)
    t = np.arange(n_samples) / sr
    max_delay = int(sr * 0.035)
    base_delay = int(sr * (depth_ms / 1000.0))
    
    # 2 modulated delay taps with LFO
    mod1 = (np.sin(2 * np.pi * rate_hz * t) * (base_delay * 0.4)).astype(np.int32) + base_delay
    mod2 = (np.cos(2 * np.pi * (rate_hz * 1.3) * t) * (base_delay * 0.5)).astype(np.int32) + int(base_delay * 1.2)
    
    indices = np.arange(n_samples)
    idx1 = np.clip(indices - mod1, 0, n_samples - 1)
    idx2 = np.clip(indices - mod2, 0, n_samples - 1)
    
    wet = (y[idx1] + y[idx2]) * 0.5
    return _norm(y * (1.0 - mix * 0.5) + wet * mix)

def _fast_delay(y, sr, delay_ms=350, feedback=0.35, mix=0.3):
    """Fast vectorized stereo-like feedback delay"""
    d_samples = max(int(sr * (delay_ms / 1000.0)), 1)
    out = y.copy()
    echo = y.copy()
    for _ in range(3):
        echo = np.pad(echo, (d_samples, 0))[:len(y)] * feedback
        out += echo * mix
    return _norm(out)

def _distort(y, gain=5.0, soft=True):
    """Fast saturation / distortion"""
    yg = y * gain
    if soft:
        return _norm(np.tanh(yg))
    else:
        return _norm(np.clip(yg, -0.85, 0.85))

def _bit_crush(y, bits=8):
    """Vectorized bit reduction"""
    levels = 2 ** bits
    step = 2.0 / levels
    return np.round(y / step) * step

def _fast_wah(y, sr, rate_hz=1.5):
    """Vectorized tremolo-wah envelope modulation (instant)"""
    t = np.arange(len(y)) / sr
    lfo = 0.5 * (1.0 + np.sin(2 * np.pi * rate_hz * t))
    # Mix bandpassed resonant signal with LFO intensity
    mid = _butter_filter(y, sr, [400, 2800], btype='bandpass', order=2)
    return _norm(y * 0.5 + (mid * (1.2 + 0.8 * lfo)))

def apply_bass_boost(y_mono, sr, boost_percent):
    if boost_percent <= 0:
        return y_mono
    low = _butter_filter(y_mono, sr, 140.0, btype='low', order=2)
    boost_factor = (boost_percent / 100.0) * 3.5
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
                  effects_json: str, surround_3d: bool = False, bass_boost: int = 0) -> bytes:
    try:
        bass_boost = int(bass_boost)
    except (ValueError, TypeError):
        bass_boost = 0

    if isinstance(surround_3d, str):
        surround_3d = surround_3d.lower() in ('true', '1', 'yes')

    ext = os.path.splitext(filename)[1] or '.wav'

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(file_bytes)
        tmp_in = tmp.name

    out_path = tmp_in + '_out.wav'

    try:
        # Load at 24000 Hz for high quality + 4x faster processing speed
        target_sr = 24000
        y, sr = librosa.load(tmp_in, sr=target_sr, mono=True)

        try:
            effects = json.loads(effects_json)
        except Exception:
            effects = {}

        # ── INTENSITY MAPPINGS ──
        reverb_ms = _scale(intensity, 40, 75, 120)
        reverb_decay = _scale(intensity, 0.3, 0.45, 0.6)

        # ════════════════════════════════════════════════
        # ULTRA-FAST GENRE CHAINS (Zero slow STFT loops)
        # ════════════════════════════════════════════════

        if genre == 'Rock':
            dist_level = _effect_level(effects, 'Distortion', intensity)
            gain = _scale(dist_level, 3.5, 7.0, 14.0)
            y = _distort(y, gain=gain, soft=True)
            low = _butter_filter(y, sr, 100, btype='low')
            y = _norm(y + low * _scale(intensity, 0.4, 0.7, 1.2))
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay * 0.7)

        elif genre == 'Pop':
            y = _fast_chorus(y, sr, depth_ms=10, rate_hz=0.7, mix=_scale(intensity, 0.3, 0.45, 0.6))
            y = _fast_delay(y, sr, delay_ms=250, feedback=0.25, mix=0.2)
            high = _butter_filter(y, sr, 4500, btype='high')
            y = _norm(y + high * _scale(intensity, 0.3, 0.5, 0.8))

        elif genre == 'Disco':
            low = _butter_filter(y, sr, 130, btype='low')
            y = _norm(y + low * _scale(intensity, 0.6, 1.1, 1.7))
            y = _fast_chorus(y, sr, depth_ms=16, rate_hz=1.1, mix=_scale(intensity, 0.35, 0.55, 0.75))
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay)

        elif genre == '8-bit':
            bit_level = _effect_level(effects, 'Bit Crush', intensity)
            bits = _scale(bit_level, 10, 6, 4)
            y = _bit_crush(y, bits=int(bits))
            # Fast downsample via decimation step
            step_factor = _scale(intensity, 2, 3, 4)
            y = np.repeat(y[::step_factor], step_factor)[:len(y)]
            mid = _butter_filter(y, sr, [800, 3000], btype='bandpass')
            y = _norm(y + mid * 0.8)

        elif genre == 'Synthwave':
            filter_level = _effect_level(effects, 'Retro Filter', intensity)
            cutoff = _scale(filter_level, 4500, 3200, 1800)
            y = _butter_filter(y, sr, cutoff, btype='low')
            y = _fast_chorus(y, sr, depth_ms=20, rate_hz=0.5, mix=_scale(intensity, 0.4, 0.6, 0.8))
            y = _fast_delay(y, sr, delay_ms=400, feedback=_scale(intensity, 0.3, 0.45, 0.6), mix=0.35)
            y = _fast_reverb(y, sr, room_ms=reverb_ms * 1.4, decay=reverb_decay)

        elif genre == 'Metal':
            dist_level = _effect_level(effects, 'Distortion', intensity)
            gain = _scale(dist_level, 8.0, 18.0, 32.0)
            y = _distort(y, gain=gain, soft=False)
            mid = _butter_filter(y, sr, [300, 2200], btype='bandpass')
            low = _butter_filter(y, sr, 110, btype='low')
            y = _norm((y - mid * 0.45) + low * 0.9)

        elif genre == 'Ballad':
            warm = _butter_filter(y, sr, [180, 900], btype='bandpass')
            y = _norm(y + warm * _scale(intensity, 0.3, 0.5, 0.8))
            y = _fast_reverb(y, sr, room_ms=reverb_ms * 1.8, decay=reverb_decay * 1.2)

        elif genre == 'Reggae':
            y = _fast_delay(y, sr, delay_ms=_scale(intensity, 260, 350, 480),
                            feedback=_scale(intensity, 0.3, 0.45, 0.6), mix=0.4)
            low = _butter_filter(y, sr, 110, btype='low')
            y = _norm(y + low * _scale(intensity, 0.7, 1.3, 2.0))
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay * 0.7)

        elif genre == 'Funk':
            y = _fast_wah(y, sr, rate_hz=_scale(intensity, 1.2, 1.8, 2.6))
            low = _butter_filter(y, sr, 130, btype='low')
            y = _norm(y + low * _scale(intensity, 0.5, 0.9, 1.5))

        elif genre == 'Jazz':
            y = _butter_filter(y, sr, _scale(intensity, 7000, 5000, 3500), btype='low')
            warm = _butter_filter(y, sr, [140, 750], btype='bandpass')
            y = _norm(y + warm * _scale(intensity, 0.3, 0.6, 0.9))
            y = _fast_reverb(y, sr, room_ms=reverb_ms * 1.3, decay=reverb_decay)

        else:
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay)

        # ── GLOBAL ENHANCEMENTS ──
        if bass_boost > 0:
            y = apply_bass_boost(y, sr, bass_boost)

        if surround_3d:
            y = apply_3d_surround(y, sr)

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
