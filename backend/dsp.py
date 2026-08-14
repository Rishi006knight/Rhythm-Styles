import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter
import json
import tempfile
import os

# ─────────────────────────────────────────────
# HIGH-IMPACT VECTORIZED DSP ENGINE
# WITH SMART ANTI-NOISE / ANTI-FIZZ DE-NOISING
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

def _noise_gate(y, sr, threshold_db=-38.0, ratio=0.15):
    """
    Dynamic Noise Gate: Mutes / suppresses low-level background hiss,
    buzzing, and white noise during quiet passages.
    """
    threshold = 10.0 ** (threshold_db / 20.0)
    # Moving RMS envelope with 20ms window
    win_size = max(int(sr * 0.02), 1)
    squared = y ** 2
    env = np.sqrt(np.convolve(squared, np.ones(win_size) / win_size, mode='same'))
    
    # Gain reduction curve
    gain = np.ones_like(y)
    below_thresh = env < threshold
    gain[below_thresh] = (env[below_thresh] / threshold) ** (1.0 / ratio - 1.0)
    gain = np.clip(gain, 0.05, 1.0)
    return y * gain

def _distort_smooth(y, sr, gain=6.0, cab_cutoff=4600):
    """
    Analog Tube Overdrive with Cabinet Emulation & Anti-Fizz:
    Eliminates the harsh 'rrrrr' buzzing and white noise fuzz.
    """
    # 1. Pre-filter: Gentle roll-off of extreme highs before clipping to prevent aliasing
    y_pre = _butter_filter(y, sr, 5500, btype='low', order=2)
    
    # 2. Smooth Asymmetrical Tube Saturation (Warm compression, not harsh square clipping)
    yg = y_pre * gain
    sat = np.tanh(yg) + 0.08 * np.tanh(yg * 2.0)
    
    # 3. Cabinet Simulator (4th-order lowpass): Cuts out high-frequency buzzing/fuzz above 4.6kHz
    sat_clean = _butter_filter(sat, sr, cab_cutoff, btype='low', order=4)
    
    # 4. Apply Noise Gate to eliminate amplified noise floor
    sat_clean = _noise_gate(sat_clean, sr, threshold_db=-36.0)
    
    return _norm(sat_clean)

def _fast_reverb(y, sr, room_ms=90, decay=0.5):
    """Spacious comb-filter reverb"""
    delay = max(int(sr * (room_ms / 1000.0)), 1)
    out = y.copy()
    for k in range(1, 5):
        d = delay * k
        if d < len(out):
            out[d:] += y[:-d] * (decay ** k)
    # Filter reverb tails to avoid metallic hiss
    out = _butter_filter(out, sr, 5000, btype='low', order=2)
    return _norm(out)

def _fast_chorus(y, sr, depth_ms=18, rate_hz=0.9, mix=0.55):
    """Vectorized analog chorus / flanger with anti-hiss smoothing"""
    n_samples = len(y)
    t = np.arange(n_samples) / sr
    base_delay = int(sr * (depth_ms / 1000.0))
    
    mod1 = (np.sin(2 * np.pi * rate_hz * t) * (base_delay * 0.45)).astype(np.int32) + base_delay
    mod2 = (np.cos(2 * np.pi * (rate_hz * 1.4) * t) * (base_delay * 0.55)).astype(np.int32) + int(base_delay * 1.3)
    
    indices = np.arange(n_samples)
    idx1 = np.clip(indices - mod1, 0, n_samples - 1)
    idx2 = np.clip(indices - mod2, 0, n_samples - 1)
    
    wet = (y[idx1] + y[idx2]) * 0.5
    # Smooth wet signal to eliminate modulation hiss
    wet = _butter_filter(wet, sr, 6000, btype='low', order=2)
    return _norm(y * (1.0 - mix * 0.6) + wet * mix)

def _fast_delay(y, sr, delay_ms=350, feedback=0.45, mix=0.4):
    """Vectorized rhythmic delay with high-frequency damping (tape delay)"""
    d_samples = max(int(sr * (delay_ms / 1000.0)), 1)
    out = y.copy()
    echo = y.copy()
    for _ in range(4):
        echo = np.pad(echo, (d_samples, 0))[:len(y)] * feedback
        # Tape damping: roll off highs on each echo repeat
        echo = _butter_filter(echo, sr, 4000, btype='low', order=1)
        out += echo * mix
    return _norm(out)

def _bit_crush(y, bits=5):
    """Arcade / Chiptune quantization"""
    levels = 2 ** bits
    step = 2.0 / levels
    return np.round(y / step) * step

def _fast_wah(y, sr, rate_hz=1.8):
    """Vectorized Funk Wah-Wah LFO Modulation"""
    t = np.arange(len(y)) / sr
    lfo = 0.5 * (1.0 + np.sin(2 * np.pi * rate_hz * t))
    mid = _butter_filter(y, sr, [350, 2400], btype='bandpass', order=2)
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
                  effects_json: str, surround_3d: bool = False, bass_boost: int = 0, volume: int = 100, denoise: bool = True) -> bytes:
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

    if isinstance(denoise, str):
        denoise = denoise.lower() in ('true', '1', 'yes')

    ext = os.path.splitext(filename)[1] or '.wav'

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(file_bytes)
        tmp_in = tmp.name

    out_path = tmp_in + '_out.wav'

    try:
        target_sr = 24000
        y, sr = librosa.load(tmp_in, sr=target_sr, mono=True)

        # 0. Initial DC Offset removal & Input Noise Gate
        y = y - np.mean(y)
        if denoise:
            y = _noise_gate(y, sr, threshold_db=-40.0)

        try:
            effects = json.loads(effects_json)
        except Exception:
            effects = {}

        reverb_ms = _scale(intensity, 50, 85, 130)
        reverb_decay = _scale(intensity, 0.35, 0.5, 0.65)

        # ════════════════════════════════════════════════
        # CLEAN & POLISHED GENRE PROCESSING (NO BUZZ/WHITE NOISE)
        # ════════════════════════════════════════════════

        if genre == 'Rock':
            dist_level = _effect_level(effects, 'Distortion', intensity)
            gain = _scale(dist_level, 4.0, 7.5, 12.0)
            # Tube saturation + 4.8kHz cabinet anti-fizz filter
            y = _distort_smooth(y, sr, gain=gain, cab_cutoff=4800)
            low = _butter_filter(y, sr, 120, btype='low')
            y = _norm(y + low * _scale(intensity, 0.5, 0.9, 1.3))
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay * 0.7)

        elif genre == 'Pop':
            y = _fast_chorus(y, sr, depth_ms=12, rate_hz=0.8, mix=_scale(intensity, 0.35, 0.5, 0.7))
            y = _fast_delay(y, sr, delay_ms=260, feedback=0.3, mix=0.25)
            high = _butter_filter(y, sr, 4200, btype='high')
            y = _norm(y + high * _scale(intensity, 0.4, 0.7, 1.0))

        elif genre == 'Disco':
            low = _butter_filter(y, sr, 140, btype='low')
            high = _butter_filter(y, sr, 3800, btype='high')
            y = _norm(y + low * _scale(intensity, 0.7, 1.2, 1.8) + high * 0.6)
            y = _fast_chorus(y, sr, depth_ms=16, rate_hz=1.2, mix=_scale(intensity, 0.4, 0.6, 0.8))
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay)

        elif genre == '8-bit':
            bit_level = _effect_level(effects, 'Bit Crush', intensity)
            bits = _scale(bit_level, 6, 5, 4)
            y = _bit_crush(y, bits=int(bits))
            step_factor = _scale(intensity, 2, 3, 4)
            y = np.repeat(y[::step_factor], step_factor)[:len(y)]
            # Cabinet smooth to keep retro tone without piercing noise
            y = _butter_filter(y, sr, 4200, btype='low', order=2)
            mid = _butter_filter(y, sr, [700, 2400], btype='bandpass')
            y = _norm(y * 0.5 + mid * 0.9)

        elif genre == 'Synthwave':
            filter_level = _effect_level(effects, 'Retro Filter', intensity)
            cutoff = _scale(filter_level, 3500, 2400, 1500)
            y = _butter_filter(y, sr, cutoff, btype='low')
            y = _fast_chorus(y, sr, depth_ms=22, rate_hz=0.6, mix=_scale(intensity, 0.45, 0.65, 0.85))
            y = _fast_delay(y, sr, delay_ms=400, feedback=_scale(intensity, 0.35, 0.48, 0.6), mix=0.35)
            y = _fast_reverb(y, sr, room_ms=reverb_ms * 1.4, decay=reverb_decay)

        elif genre == 'Metal':
            dist_level = _effect_level(effects, 'Distortion', intensity)
            gain = _scale(dist_level, 8.0, 14.0, 22.0)
            # High-gain tube saturation with steep 4.4kHz cabinet filter to kill white noise fizz
            y = _distort_smooth(y, sr, gain=gain, cab_cutoff=4400)
            mid = _butter_filter(y, sr, [350, 1800], btype='bandpass')
            low = _butter_filter(y, sr, 120, btype='low')
            y = _norm((y - mid * 0.5) + low * 1.1)

        elif genre == 'Ballad':
            warm = _butter_filter(y, sr, [160, 850], btype='bandpass')
            y = _norm(y + warm * _scale(intensity, 0.5, 0.8, 1.2))
            y = _fast_reverb(y, sr, room_ms=reverb_ms * 1.8, decay=reverb_decay * 1.2)

        elif genre == 'Reggae':
            y = _fast_delay(y, sr, delay_ms=_scale(intensity, 280, 360, 480),
                            feedback=_scale(intensity, 0.4, 0.5, 0.65), mix=0.4)
            low = _butter_filter(y, sr, 110, btype='low')
            y = _norm(y + low * _scale(intensity, 0.9, 1.6, 2.4))
            y = _fast_reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay * 0.7)

        elif genre == 'Funk':
            y = _fast_wah(y, sr, rate_hz=_scale(intensity, 1.4, 2.0, 2.8))
            low = _butter_filter(y, sr, 130, btype='low')
            y = _norm(y + low * _scale(intensity, 0.6, 1.1, 1.6))

        elif genre == 'Jazz':
            y = _butter_filter(y, sr, _scale(intensity, 5200, 3800, 2600), btype='low')
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

        # Final De-Noise / Anti-Fizz Smoothing Pass
        if denoise:
            if isinstance(y, np.ndarray) and y.ndim == 2:
                y[:, 0] = _noise_gate(y[:, 0], sr, threshold_db=-38.0)
                y[:, 1] = _noise_gate(y[:, 1], sr, threshold_db=-38.0)
            else:
                y = _noise_gate(y, sr, threshold_db=-38.0)

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
