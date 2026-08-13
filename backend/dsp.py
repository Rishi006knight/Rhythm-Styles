import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter
import json
import tempfile
import os

def apply_bass_boost(y_mono, sr, boost_percent):
    if boost_percent <= 0:
        return y_mono
    nyq = 0.5 * sr
    cutoff = 150.0 / nyq
    b, a = butter(2, cutoff, btype='low', analog=False)
    bass = lfilter(b, a, y_mono)
    boost_factor = (boost_percent / 100.0) * 5.0 
    y = y_mono + (bass * boost_factor)
    max_val = np.max(np.abs(y))
    if max_val > 1.0:
        y = y / max_val
    return y

def apply_3d_surround(y_mono, sr):
    length = len(y_mono)
    time = np.arange(length) / sr
    # 0.125 Hz sine wave for panning (8 seconds per rotation)
    pan_freq = 0.125
    lfo = np.sin(2 * np.pi * pan_freq * time)
    # Equal power panning
    angle = (lfo + 1) * (np.pi / 4)
    gain_l = np.cos(angle)
    gain_r = np.sin(angle)
    
    y_stereo = np.zeros((length, 2))
    y_stereo[:, 0] = y_mono * gain_l
    y_stereo[:, 1] = y_mono * gain_r
    
    # Haas effect for stereo widening
    delay_samples = int(0.015 * sr)
    if delay_samples < length:
        y_stereo[delay_samples:, 1] += y_stereo[:-delay_samples, 0] * 0.4
        y_stereo[delay_samples:, 0] += y_stereo[:-delay_samples, 1] * 0.4
        
    max_val = np.max(np.abs(y_stereo))
    if max_val > 0:
        y_stereo = y_stereo / max_val
    return y_stereo

def process_audio(file_bytes: bytes, filename: str, genre: str, intensity: str, effects_json: str, surround_3d: bool = False, bass_boost: int = 0) -> bytes:
    """
    Applies real DSP effects to the audio bytes based on the selected genre and effects.
    """
    try:
        bass_boost = int(bass_boost)
    except (ValueError, TypeError):
        bass_boost = 0
        
    if isinstance(surround_3d, str):
        surround_3d = surround_3d.lower() in ('true', '1', 'yes')

    # Extract extension for the temporary file
    ext = os.path.splitext(filename)[1]
    if not ext:
        ext = ".wav"
        
    # Write incoming bytes to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_in:
        temp_in.write(file_bytes)
        temp_in_path = temp_in.name
        
    out_path = temp_in_path + "_out.wav"
    
    try:
        # Load audio as 1D mono to ensure predictable filter/convolution processing
        y, sr = librosa.load(temp_in_path, sr=None, mono=True)
        
        # Parse effects JSON
        try:
            effects = json.loads(effects_json)
        except:
            effects = {}

        # -----------------------------------------
        # APPLY DSP BASED ON GENRE & EFFECTS
        # -----------------------------------------
        
        if genre == '8-bit / Chiptune':
            # Bit Crush (Quantization)
            bit_crush_level = effects.get('Bit Crush', 'Medium')
            bit_depth = 4 if bit_crush_level == 'High' else (8 if bit_crush_level == 'Medium' else 12)
            step = 2.0 / (2**bit_depth)
            y = np.round(y / step) * step
            
            # Downsampling
            downsample_level = effects.get('Downsampling', 'Medium')
            if downsample_level == 'High':
                y = librosa.resample(y, orig_sr=sr, target_sr=sr//4)
                sr = sr // 4
            elif downsample_level == 'Medium':
                y = librosa.resample(y, orig_sr=sr, target_sr=sr//2)
                sr = sr // 2
                
        elif genre == 'Synthwave / 1980s':
            # Retro Filter (Lowpass via moving average)
            filter_level = effects.get('Retro Filter', 'Medium')
            window = 15 if filter_level == 'High' else (7 if filter_level == 'Medium' else 3)
            y = np.convolve(y, np.ones(window)/window, mode='same')
            
        elif genre == 'Metal' or genre == 'Rock':
            # Distortion (Hard Clipping)
            dist_level = effects.get('Distortion', 'Medium')
            gain = 15.0 if dist_level == 'High' else (6.0 if dist_level == 'Medium' else 2.0)
            y = np.clip(y * gain, -1.0, 1.0)
            
        else:
            # Generic transformation (Pitch shift) to prove the audio changed
            n_steps = 4 if intensity == 'High' else (2 if intensity == 'Medium' else 1)
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=n_steps)

        # -----------------------------------------
        
        # Apply Global Bass Boost
        if bass_boost > 0:
            y = apply_bass_boost(y, sr, bass_boost)
            
        # Apply 3D Surround (Returns stereo array)
        if surround_3d:
            y = apply_3d_surround(y, sr)
        
        # Write processed audio to output temp file
        sf.write(out_path, y, sr, format='WAV')
        
        # Read the processed bytes
        with open(out_path, 'rb') as f:
            out_bytes = f.read()
            
        return out_bytes
        
    except Exception as e:
        print(f"DSP Error: {e}")
        # Fallback to original bytes if processing fails
        return file_bytes
        
    finally:
        # Cleanup temp files
        if os.path.exists(temp_in_path):
            os.remove(temp_in_path)
        if os.path.exists(out_path):
            os.remove(out_path)
