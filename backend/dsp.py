import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter, sosfilt, butter as sos_butter
import json
import tempfile
import os


# ─────────────────────────────────────────────
# HELPER: Normalise to prevent clipping
# ─────────────────────────────────────────────
def _norm(y, headroom=0.95):
    peak = np.max(np.abs(y))
    if peak > 0:
        y = y / peak * headroom
    return y


# ─────────────────────────────────────────────
# HELPER: Butterworth filter (low / high / bandpass)
# ─────────────────────────────────────────────
def _butter_filter(y, sr, cutoff, btype='low', order=2):
    nyq = 0.5 * sr
    if isinstance(cutoff, (list, tuple)):
        norm = [c / nyq for c in cutoff]
    else:
        norm = cutoff / nyq
    norm = np.clip(norm, 1e-4, 0.9999)
    b, a = butter(order, norm, btype=btype)
    return lfilter(b, a, y)


# ─────────────────────────────────────────────
# HELPER: Simple comb-filter reverb
# ─────────────────────────────────────────────
def _reverb(y, sr, room_ms=80, decay=0.45):
    delay = int(sr * room_ms / 1000)
    out = y.copy()
    for k in range(1, 5):
        d = delay * k
        if d < len(out):
            out[d:] += y[:-d] * (decay ** k)
    return _norm(out)


# ─────────────────────────────────────────────
# HELPER: Tremolo (amplitude LFO)
# ─────────────────────────────────────────────
def _tremolo(y, sr, rate_hz=5.0, depth=0.4):
    t = np.arange(len(y)) / sr
    lfo = 1.0 - depth * 0.5 * (1 + np.sin(2 * np.pi * rate_hz * t))
    return y * lfo


# ─────────────────────────────────────────────
# HELPER: Chorus (multiple detuned copies summed)
# ─────────────────────────────────────────────
def _chorus(y, sr, voices=3, depth_ms=12, rate_hz=0.8, mix=0.4):
    out = y.copy()
    for i in range(1, voices + 1):
        detune = (-1 if i % 2 == 0 else 1) * i * 0.15
        shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=detune)
        # Slight time wobble via delay modulation
        delay_samples = int(sr * depth_ms / 1000 * i)
        padded = np.pad(shifted, (delay_samples, 0))[:len(y)]
        out += padded * (mix / voices)
    return _norm(out)


# ─────────────────────────────────────────────
# HELPER: Delay / Echo
# ─────────────────────────────────────────────
def _delay(y, sr, delay_ms=375, feedback=0.4, mix=0.35):
    delay_samples = int(sr * delay_ms / 1000)
    out = y.copy()
    echo = y.copy()
    for _ in range(4):
        echo = np.pad(echo, (delay_samples, 0))[:len(y)] * feedback
        out += echo * mix
    return _norm(out)


# ─────────────────────────────────────────────
# HELPER: Hard / soft clipping distortion
# ─────────────────────────────────────────────
def _distort(y, gain=6.0, clip=1.0, soft=False):
    y = y * gain
    if soft:
        y = np.tanh(y)  # smooth saturation
    else:
        y = np.clip(y, -clip, clip)
    return _norm(y)


# ─────────────────────────────────────────────
# HELPER: Bit crush quantisation
# ─────────────────────────────────────────────
def _bit_crush(y, bits=8):
    step = 2.0 / (2 ** bits)
    return np.round(y / step) * step


# ─────────────────────────────────────────────
# HELPER: Wah / resonant band filter sweep
# ─────────────────────────────────────────────
def _wah(y, sr, rate_hz=1.5, low_hz=400, high_hz=3000):
    t = np.arange(len(y)) / sr
    freq_sweep = low_hz + (high_hz - low_hz) * 0.5 * (1 + np.sin(2 * np.pi * rate_hz * t))
    out = np.zeros_like(y)
    chunk = max(int(sr * 0.02), 1)
    for i in range(0, len(y), chunk):
        seg = y[i:i + chunk]
        fc = float(np.mean(freq_sweep[i:i + chunk]))
        fc = np.clip(fc / (0.5 * sr), 1e-4, 0.98)
        b, a = butter(2, fc, btype='bandpass' if fc < 0.9 else 'low')
        out[i:i + len(seg)] = lfilter(b, a, seg)
    return _norm(out * 1.4 + y * 0.6)


# ─────────────────────────────────────────────
# BASS BOOST
# ─────────────────────────────────────────────
def apply_bass_boost(y_mono, sr, boost_percent):
    if boost_percent <= 0:
        return y_mono
    low = _butter_filter(y_mono, sr, 150.0, btype='low', order=2)
    boost_factor = (boost_percent / 100.0) * 4.0
    y = y_mono + low * boost_factor
    return _norm(y)


# ─────────────────────────────────────────────
# 3D SURROUND (8D)
# ─────────────────────────────────────────────
def apply_3d_surround(y_mono, sr):
    length = len(y_mono)
    time = np.arange(length) / sr
    lfo = np.sin(2 * np.pi * 0.125 * time)
    angle = (lfo + 1) * (np.pi / 4)
    gain_l = np.cos(angle)
    gain_r = np.sin(angle)
    y_stereo = np.zeros((length, 2))
    y_stereo[:, 0] = y_mono * gain_l
    y_stereo[:, 1] = y_mono * gain_r
    delay_samples = int(0.015 * sr)
    if delay_samples < length:
        y_stereo[delay_samples:, 1] += y_stereo[:-delay_samples, 0] * 0.4
        y_stereo[delay_samples:, 0] += y_stereo[:-delay_samples, 1] * 0.4
    peak = np.max(np.abs(y_stereo))
    if peak > 0:
        y_stereo = y_stereo / peak * 0.95
    return y_stereo


# ─────────────────────────────────────────────
# INTENSITY SCALING HELPERS
# ─────────────────────────────────────────────
def _scale(intensity, low, med, high):
    return {'Low': low, 'Medium': med, 'High': high}.get(intensity, med)


def _effect_level(effects, key, intensity):
    """Get level from effects dict, fallback to intensity."""
    return effects.get(key, intensity)


# ─────────────────────────────────────────────
# MAIN PROCESS FUNCTION
# ─────────────────────────────────────────────
def process_audio(file_bytes: bytes, filename: str, genre: str, intensity: str,
                  effects_json: str, surround_3d: bool = False, bass_boost: int = 0) -> bytes:
    """
    Applies real DSP effects to audio bytes based on genre/intensity/effects.
    Genre strings must match exactly what the frontend sends.
    """
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
        y, sr = librosa.load(tmp_in, sr=None, mono=True)

        try:
            effects = json.loads(effects_json)
        except Exception:
            effects = {}

        # ── INTENSITY MAPPED PARAMETERS ─────────────────
        # pitch shift steps (semitones)
        pitch_steps = _scale(intensity, 1, 2, 4)
        # reverb room size ms
        reverb_ms = _scale(intensity, 40, 80, 140)
        reverb_decay = _scale(intensity, 0.3, 0.45, 0.6)

        # ════════════════════════════════════════════════
        # GENRE DSP CHAINS (matching frontend genre names)
        # ════════════════════════════════════════════════

        if genre == 'Rock':
            # Overdrive + Distortion + Reverb + Drum Impact (low-end punch)
            dist_level = _effect_level(effects, 'Distortion', intensity)
            gain = _scale(dist_level, 3.0, 6.0, 12.0)
            y = _distort(y, gain=gain, soft=True)            # soft overdrive
            # Add low-end punch
            low = _butter_filter(y, sr, 80, btype='low')
            y = y + low * _scale(intensity, 0.3, 0.6, 1.0)
            # Room reverb
            y = _reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay * 0.7)
            y = _norm(y)

        elif genre == 'Pop':
            # Compression (loudness), Chorus brightness, subtle Delay
            y = _chorus(y, sr, voices=2, depth_ms=8, rate_hz=0.6, mix=0.3)
            y = _delay(y, sr, delay_ms=280, feedback=0.25, mix=0.2)
            # High-shelf brightness
            high = _butter_filter(y, sr, 5000, btype='high')
            y = y + high * _scale(intensity, 0.1, 0.25, 0.45)
            # Light pitch up for pop brightness
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=_scale(intensity, 0.5, 1.0, 1.5))
            y = _norm(y)

        elif genre == 'Disco':
            # Punchy bass + groove chorus + lush reverb
            low = _butter_filter(y, sr, 120, btype='low')
            y = y + low * _scale(intensity, 0.5, 1.0, 1.8)
            y = _chorus(y, sr, voices=3, depth_ms=15, rate_hz=1.0, mix=_scale(intensity, 0.3, 0.5, 0.7))
            y = _reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay)
            y = _norm(y)

        elif genre == '8-bit':
            # Bit crush + downsample + retro resonant filter
            bit_level = _effect_level(effects, 'Bit Crush', intensity)
            bits = _scale(bit_level, 12, 8, 4)
            y = _bit_crush(y, bits=int(bits))
            # Downsample
            ds_level = _effect_level(effects, 'Downsampling', intensity)
            factor = _scale(ds_level, 2, 3, 5)
            target_sr = max(sr // int(factor), 4000)
            y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
            sr = target_sr
            # Chiptune resonant tone — add a thin high mid boost
            mid = _butter_filter(y, sr, [900, min(3500, sr // 3)], btype='bandpass')
            y = y + mid * _scale(intensity, 0.3, 0.6, 1.0)
            y = _norm(y)

        elif genre == 'Synthwave':
            # Retro lowpass + deep chorus + stereo delay + subtle pitch
            filter_level = _effect_level(effects, 'Retro Filter', intensity)
            cutoff = _scale(filter_level, 5000, 3500, 2000)
            y = _butter_filter(y, sr, cutoff, btype='low')
            y = _chorus(y, sr, voices=4, depth_ms=18, rate_hz=0.5, mix=_scale(intensity, 0.4, 0.6, 0.8))
            y = _delay(y, sr, delay_ms=430, feedback=_scale(intensity, 0.3, 0.45, 0.6), mix=0.35)
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=-_scale(intensity, 0.5, 1.0, 1.5))  # slight detune down for retro feel
            y = _reverb(y, sr, room_ms=reverb_ms * 1.5, decay=reverb_decay)
            y = _norm(y)

        elif genre == 'Metal':
            # Heavy distortion + compression + aggressive low-end
            dist_level = _effect_level(effects, 'Distortion', intensity)
            gain = _scale(dist_level, 8.0, 18.0, 30.0)
            y = _distort(y, gain=gain, soft=False, clip=0.85)  # hard clip
            # Scoop the mids (metal EQ: boost bass + treble, cut mids)
            mid = _butter_filter(y, sr, [250, 2500], btype='bandpass')
            y = y - mid * _scale(intensity, 0.2, 0.4, 0.6)
            low = _butter_filter(y, sr, 100, btype='low')
            y = y + low * _scale(intensity, 0.5, 1.0, 1.5)
            y = _norm(y)

        elif genre == 'Ballad':
            # Warm reverb + subtle pitch + compression (reduce dynamics)
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=_scale(intensity, 0.5, 1.0, 1.5))
            y = _reverb(y, sr, room_ms=reverb_ms * 2, decay=reverb_decay * 1.3)
            # Warmth: boost low-mids
            warm = _butter_filter(y, sr, [200, 800], btype='bandpass')
            y = y + warm * _scale(intensity, 0.2, 0.4, 0.6)
            y = _norm(y)

        elif genre == 'Reggae':
            # Offbeat emphasis: slight delay for skank feel + bass punch + reverb
            y = _delay(y, sr, delay_ms=_scale(intensity, 250, 375, 500),
                       feedback=_scale(intensity, 0.3, 0.5, 0.65), mix=0.4)
            # Bass boost
            low = _butter_filter(y, sr, 100, btype='low')
            y = y + low * _scale(intensity, 0.6, 1.2, 2.0)
            y = _reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay * 0.8)
            # Slight pitch down for roots feel
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=-_scale(intensity, 0.5, 1.0, 2.0))
            y = _norm(y)

        elif genre == 'Funk':
            # Wah filter + groove compression + bass punch
            y = _wah(y, sr, rate_hz=_scale(intensity, 1.0, 1.8, 2.5),
                     low_hz=300, high_hz=3000)
            low = _butter_filter(y, sr, 120, btype='low')
            y = y + low * _scale(intensity, 0.4, 0.8, 1.4)
            # Snap transient (slight pitch shift up)
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=_scale(intensity, 0.0, 0.5, 1.0))
            y = _norm(y)

        elif genre == 'Jazz':
            # Warm low-pass + room reverb + swing feel (slight time-stretch)
            y = _butter_filter(y, sr, _scale(intensity, 8000, 6000, 4500), btype='low')
            y = _reverb(y, sr, room_ms=reverb_ms * 1.2, decay=reverb_decay * 1.1)
            # Warm low-mid boost
            warm = _butter_filter(y, sr, [150, 700], btype='bandpass')
            y = y + warm * _scale(intensity, 0.25, 0.5, 0.8)
            # Slightly sharp pitch for jazz brightness
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=_scale(intensity, 0.5, 1.0, 1.5))
            y = _norm(y)

        else:
            # Generic fallback: pitch shift + reverb
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=pitch_steps)
            y = _reverb(y, sr, room_ms=reverb_ms, decay=reverb_decay)
            y = _norm(y)

        # ── GLOBAL ENHANCEMENTS ──────────────────────────
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
