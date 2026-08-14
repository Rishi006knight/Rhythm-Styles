import { useState, useRef, useEffect } from 'react'
import './App.css'

const DEFAULT_BACKEND_URL = 'https://rhythm-styles-backend.onrender.com';

function App() {
  const [selectedGenre, setSelectedGenre] = useState('');
  const [intensity, setIntensity] = useState('Medium');
  const [effects, setEffects] = useState({});
  const [file, setFile] = useState(null);
  const [filePreviewUrl, setFilePreviewUrl] = useState(null);
  const [isTransforming, setIsTransforming] = useState(false);
  const [transformStatus, setTransformStatus] = useState(''); // status sub-label
  const [resultAudioUrl, setResultAudioUrl] = useState(null);
  const [resultFilename, setResultFilename] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [usedFallback, setUsedFallback] = useState(false);
  const [serverStatus, setServerStatus] = useState('checking'); // 'online' | 'waking' | 'offline'

  // Global Enhancements
  const [surround3D, setSurround3D] = useState(false);
  const [bassBoost, setBassBoost] = useState(25);

  const fileInputRef = useRef(null);

  const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || DEFAULT_BACKEND_URL).replace(/\/$/, '');

  // Auto-wake Render backend immediately on page load
  useEffect(() => {
    let isMounted = true;
    const checkServer = async () => {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 6000);
        const res = await fetch(`${apiBaseUrl}/health`, { signal: controller.signal });
        clearTimeout(timer);
        if (res.ok && isMounted) {
          setServerStatus('online');
          return;
        }
      } catch (err) {
        // May be sleeping
      }

      if (isMounted) setServerStatus('waking');

      // Retry after 15 seconds if it was sleeping
      try {
        const controller2 = new AbortController();
        const timer2 = setTimeout(() => controller2.abort(), 35000);
        const res2 = await fetch(`${apiBaseUrl}/health`, { signal: controller2.signal });
        clearTimeout(timer2);
        if (res2.ok && isMounted) {
          setServerStatus('online');
        } else if (isMounted) {
          setServerStatus('offline');
        }
      } catch {
        if (isMounted) setServerStatus('offline');
      }
    };

    checkServer();
    return () => { isMounted = false; };
  }, [apiBaseUrl]);

  const genreDetails = {
    'Rock': { emoji: '🎸', fx: ['Distortion', 'Overdrive', 'Reverb', 'Drum Impact'] },
    'Pop': { emoji: '🎤', fx: ['Reverb', 'Chorus', 'Delay', 'Compression'] },
    'Disco': { emoji: '🕺', fx: ['Groove', 'Bass Punch', 'Chorus', 'Reverb'] },
    '8-bit': { emoji: '👾', fx: ['Bit Crush', 'Downsampling', '8-bit Synth', 'Retro Filter'] },
    'Synthwave': { emoji: '🌆', fx: ['Chorus', 'Delay', 'Reverb', 'Retro Filter'] },
    'Metal': { emoji: '🤘', fx: ['Distortion', 'Compression', 'Drum Impact', 'Low-End'] },
    'Ballad': { emoji: '🎵', fx: ['Reverb', 'Delay', 'Warmth', 'Dynamics'] },
    'Reggae': { emoji: '🟢', fx: ['Bass', 'Offbeat Groove', 'Delay', 'Reverb'] },
    'Funk': { emoji: '🎸', fx: ['Bass Groove', 'Compression', 'Wah/Filter', 'Drum Groove'] },
    'Jazz': { emoji: '🎷', fx: ['Swing', 'Reverb', 'Warmth', 'Improvisation'] }
  };

  const genres = Object.keys(genreDetails);

  const handleFileChange = (e) => {
    const uploadedFile = e.target.files[0];
    if (uploadedFile) {
      setFile(uploadedFile);
      setFilePreviewUrl(URL.createObjectURL(uploadedFile));
      setResultAudioUrl(null);
      setErrorMessage(null);
    }
  };

  const handleRemoveFile = (e) => {
    e.stopPropagation();
    setFile(null);
    setFilePreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      setFile(droppedFile);
      setFilePreviewUrl(URL.createObjectURL(droppedFile));
      setResultAudioUrl(null);
      setErrorMessage(null);
    }
  };

  const handleGenreSelect = (genre) => {
    setSelectedGenre(genre);
    const initialEffects = {};
    genreDetails[genre].fx.forEach(effect => {
      initialEffects[effect] = 'Medium';
    });
    setEffects(initialEffects);
  };

  const handleEffectChange = (effect, level) => {
    setEffects(prev => ({ ...prev, [effect]: level }));
  };

  // Distortion curve generator for WaveShaperNode
  const makeDistortionCurve = (amount = 20) => {
    const k = typeof amount === 'number' ? amount : 50;
    const n_samples = 44100;
    const curve = new Float32Array(n_samples);
    const deg = Math.PI / 180;
    for (let i = 0; i < n_samples; ++i) {
      const x = (i * 2) / n_samples - 1;
      curve[i] = ((3 + k) * x * 20 * deg) / (Math.PI + k * Math.abs(x));
    }
    return curve;
  };

  // Client-Side Web Audio API Fallback Processing (High-Impact Real DSP)
  const processAudioWithWebAudio = async (audioFile) => {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const arrayBuffer = await audioFile.arrayBuffer();
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

    // Calculate playback speed based on genre
    let playbackRate = 1.0;
    if (selectedGenre === 'Synthwave') playbackRate = 0.93; // 80s slow tape
    else if (selectedGenre === 'Disco') playbackRate = 1.06; // Upbeat dance tempo
    else if (selectedGenre === 'Pop') playbackRate = 1.03; // Bright pop
    else if (selectedGenre === 'Jazz') playbackRate = 0.95; // Laid-back swing
    else if (selectedGenre === '8-bit') playbackRate = 1.05; // Fast arcade

    const outputLength = Math.ceil(audioBuffer.length / playbackRate);
    const offlineCtx = new OfflineAudioContext(
      audioBuffer.numberOfChannels,
      outputLength,
      audioBuffer.sampleRate
    );

    const source = offlineCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.playbackRate.value = playbackRate;

    // 1. Bass Boost Low-shelf
    const bassFilter = offlineCtx.createBiquadFilter();
    bassFilter.type = 'lowshelf';
    bassFilter.frequency.value = 160;
    bassFilter.gain.value = (bassBoost / 100) * 16; // 0 to +16dB

    // 2. Genre-Specific Chain
    let lastNode = source;
    lastNode.connect(bassFilter);
    lastNode = bassFilter;

    if (selectedGenre === 'Rock' || selectedGenre === 'Metal') {
      // WaveShaper Overdrive / Distortion
      const distortion = offlineCtx.createWaveShaper();
      distortion.curve = makeDistortionCurve(selectedGenre === 'Metal' ? 120 : 50);
      distortion.oversample = '4x';

      const cabFilter = offlineCtx.createBiquadFilter();
      cabFilter.type = 'lowpass';
      cabFilter.frequency.value = selectedGenre === 'Metal' ? 4500 : 5500;

      lastNode.connect(distortion);
      distortion.connect(cabFilter);
      lastNode = cabFilter;

    } else if (selectedGenre === '8-bit') {
      // Direct Buffer Bit-Crush & Decimation
      const bitFilter = offlineCtx.createBiquadFilter();
      bitFilter.type = 'peaking';
      bitFilter.frequency.value = 1500;
      bitFilter.gain.value = 12;
      lastNode.connect(bitFilter);
      lastNode = bitFilter;

    } else if (selectedGenre === 'Synthwave') {
      // Lowpass + Delay + Chorus
      const lpFilter = offlineCtx.createBiquadFilter();
      lpFilter.type = 'lowpass';
      lpFilter.frequency.value = 3200;

      const delay = offlineCtx.createDelay(1.0);
      delay.delayTime.value = 0.38;
      const delayGain = offlineCtx.createGain();
      delayGain.gain.value = 0.35;

      lastNode.connect(lpFilter);
      lpFilter.connect(delay);
      delay.connect(delayGain);
      delayGain.connect(offlineCtx.destination);
      lastNode = lpFilter;

    } else if (selectedGenre === 'Disco') {
      // High-pass sparkle + Low punch
      const highFilter = offlineCtx.createBiquadFilter();
      highFilter.type = 'highshelf';
      highFilter.frequency.value = 3500;
      highFilter.gain.value = 8;
      lastNode.connect(highFilter);
      lastNode = highFilter;

    } else if (selectedGenre === 'Reggae') {
      // Dub Delay Feedback Loop
      const dubDelay = offlineCtx.createDelay(1.0);
      dubDelay.delayTime.value = 0.32;
      const dubFeedback = offlineCtx.createGain();
      dubFeedback.gain.value = 0.45;
      const dubFilter = offlineCtx.createBiquadFilter();
      dubFilter.type = 'lowpass';
      dubFilter.frequency.value = 2200;

      lastNode.connect(dubDelay);
      dubDelay.connect(dubFilter);
      dubFilter.connect(dubFeedback);
      dubFeedback.connect(dubDelay); // Feedback loop
      dubFilter.connect(offlineCtx.destination);

    } else if (selectedGenre === 'Funk') {
      // Resonant Wah Filter Peak
      const wahFilter = offlineCtx.createBiquadFilter();
      wahFilter.type = 'bandpass';
      wahFilter.frequency.value = 1200;
      wahFilter.Q.value = 4.0;
      lastNode.connect(wahFilter);
      lastNode = wahFilter;

    } else if (selectedGenre === 'Jazz') {
      // Warm Vintage Horn Lowpass
      const jazzFilter = offlineCtx.createBiquadFilter();
      jazzFilter.type = 'lowpass';
      jazzFilter.frequency.value = 4000;
      lastNode.connect(jazzFilter);
      lastNode = jazzFilter;

    } else {
      // Pop / Ballad: High-shelf Shimmer
      const shimmerFilter = offlineCtx.createBiquadFilter();
      shimmerFilter.type = 'highshelf';
      shimmerFilter.frequency.value = 5000;
      shimmerFilter.gain.value = 7;
      lastNode.connect(shimmerFilter);
      lastNode = shimmerFilter;
    }

    const renderedBuffer = await offlineCtx.startRendering();

    // 3. Post-Process: 3D Surround (8D Audio Circular Panning & Haas Widening)
    if (surround3D && renderedBuffer.numberOfChannels >= 2) {
      const leftChan = renderedBuffer.getChannelData(0);
      const rightChan = renderedBuffer.getChannelData(1);
      const sr = renderedBuffer.sampleRate;
      const len = leftChan.length;

      // 0.12 Hz circular panning LFO (8.3 seconds per 360° rotation)
      const panFreq = 0.12;
      const haasSamples = Math.floor(0.016 * sr); // 16ms Haas stereo delay

      for (let i = 0; i < len; i++) {
        const t = i / sr;
        const angle = (Math.sin(2 * Math.PI * panFreq * t) + 1) * (Math.PI / 4);
        const gainL = Math.cos(angle);
        const gainR = Math.sin(angle);

        const l = leftChan[i];
        const r = rightChan[i];

        leftChan[i] = l * gainL;
        rightChan[i] = r * gainR;

        // Haas stereo widening
        if (i >= haasSamples) {
          leftChan[i] += rightChan[i - haasSamples] * 0.35;
          rightChan[i] += leftChan[i - haasSamples] * 0.35;
        }
      }
    }

    // 4. Post-Process: 8-Bit chiptune quantization if selected
    if (selectedGenre === '8-bit') {
      const step = 4; // Downsampling step
      const bitDepth = 5; // 5-bit arcade audio
      const qStep = 2.0 / Math.pow(2, bitDepth);
      for (let ch = 0; ch < renderedBuffer.numberOfChannels; ch++) {
        const data = renderedBuffer.getChannelData(ch);
        for (let i = 0; i < data.length; i += step) {
          const quant = Math.round(data[i] / qStep) * qStep;
          for (let s = 0; s < step && i + s < data.length; s++) {
            data[i + s] = quant;
          }
        }
      }
    }

    return audioBufferToWavBlob(renderedBuffer);
  };

  // Helper to convert AudioBuffer to WAV format
  const audioBufferToWavBlob = (buffer) => {
    const numOfChan = buffer.numberOfChannels;
    const length = buffer.length * numOfChan * 2 + 44;
    const outBuffer = new ArrayBuffer(length);
    const view = new DataView(outBuffer);
    const channels = [];
    let sample = 0;
    let offset = 0;
    let pos = 0;

    function setUint16(data) { view.setUint16(pos, data, true); pos += 2; }
    function setUint32(data) { view.setUint32(pos, data, true); pos += 4; }

    setUint32(0x46464952); // "RIFF"
    setUint32(length - 8);
    setUint32(0x45564157); // "WAVE"
    setUint32(0x20746d66); // "fmt "
    setUint32(16);         // length
    setUint16(1);          // PCM
    setUint16(numOfChan);
    setUint32(buffer.sampleRate);
    setUint32(buffer.sampleRate * 2 * numOfChan);
    setUint16(numOfChan * 2);
    setUint16(16);
    setUint32(0x61746164); // "data"
    setUint32(length - pos - 4);

    for (let i = 0; i < buffer.numberOfChannels; i++) {
      channels.push(buffer.getChannelData(i));
    }

    while (offset < buffer.length) {
      for (let i = 0; i < numOfChan; i++) {
        sample = Math.max(-1, Math.min(1, channels[i][offset]));
        sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0;
        view.setInt16(pos, sample, true);
        pos += 2;
      }
      offset++;
    }

    return new Blob([outBuffer], { type: 'audio/wav' });
  };

  // Fast health-check with configurable timeout (ms)
  const pingBackend = async (apiBaseUrl, timeoutMs = 3000) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(`${apiBaseUrl}/health`, { signal: controller.signal });
      clearTimeout(timer);
      return res.ok;
    } catch {
      clearTimeout(timer);
      return false;
    }
  };

  const handleTransform = async () => {
    if (!file || !selectedGenre) return;

    setIsTransforming(true);
    setTransformStatus('Preparing audio...');
    setResultAudioUrl(null);
    setErrorMessage(null);
    setUsedFallback(false);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('genre', selectedGenre);
    formData.append('intensity', intensity);
    formData.append('effects', JSON.stringify(effects));
    formData.append('surround_3d', surround3D);
    formData.append('bass_boost', bassBoost);

    // 1. Attempt Server-Side Transformation (with cold-start status)
    let serverSucceeded = false;
    if (apiBaseUrl) {
      try {
        setTransformStatus('Connecting to server...');

        // Timeout after 45s to allow Render free-tier cold start if sleeping
        const controller = new AbortController();
        const timeoutTimer = setTimeout(() => {
          setTransformStatus('Server waking up (Render free tier), please wait...');
        }, 4000);
        const hardTimeout = setTimeout(() => controller.abort(), 50000);

        const response = await fetch(`${apiBaseUrl}/transform/`, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        });

        clearTimeout(timeoutTimer);
        clearTimeout(hardTimeout);

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        setResultAudioUrl(url);

        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `transformed_${selectedGenre.toLowerCase()}_${file.name}`;
        if (contentDisposition && contentDisposition.includes('filename=')) {
          filename = contentDisposition.split('filename=')[1].replace(/["']/g, '');
        }
        setResultFilename(filename);
        setServerStatus('online');
        serverSucceeded = true;

      } catch (error) {
        console.warn('Backend transform failed, activating Web Audio DSP Fallback:', error);
        setErrorMessage(`Server connection issue (${error.message}). Switched to High-Impact Web Audio DSP!`);
      }
    }

    // 2. Fallback to High-Impact Web Audio Engine if server didn't respond
    if (!serverSucceeded) {
      try {
        setTransformStatus('Processing via Web Audio DSP...');
        const fallbackBlob = await processAudioWithWebAudio(file);
        const url = window.URL.createObjectURL(fallbackBlob);
        setResultAudioUrl(url);
        setResultFilename(`${selectedGenre.toLowerCase()}_style_${file.name.replace(/\.[^/.]+$/, '')}.wav`);
        setUsedFallback(true);
      } catch (fallbackErr) {
        console.error('Fallback failed:', fallbackErr);
        setErrorMessage(`Transformation error: ${fallbackErr.message}`);
      }
    }

    setIsTransforming(false);
    setTransformStatus('');
  };

  return (
    <>
      {/* Background Decorative Layers */}
      <div className="app-bg-wrapper">
        <div className="bg-blob bg-blob-purple-1" />
        <div className="bg-blob bg-blob-cyan-1" />
        <div className="bg-blob bg-blob-purple-2" />
        <div className="synthwave-grid" />
        <div className="particles-container">
          {Array.from({ length: 18 }).map((_, i) => (
            <div
              key={i}
              className="particle"
              style={{
                left: `${(i * 5.5 + 4) % 96}%`,
                width: `${(i % 4) * 2 + 4}px`,
                height: `${(i % 4) * 2 + 4}px`,
                animationDelay: `${(i * 0.7) % 12}s`,
                animationDuration: `${12 + (i % 5) * 2}s`
              }}
            />
          ))}
        </div>
      </div>

      {/* Main Content Container */}
      <div className="app-container">

        {/* Header */}
        <header className="app-header animate-section" style={{ animationDelay: '0.1s' }}>
          <div className="logo-brand-container">
            <div className="equalizer-logo">
              <span className="eq-bar" />
              <span className="eq-bar" />
              <span className="eq-bar" />
              <span className="eq-bar" />
              <span className="eq-bar" />
            </div>
            <h1 className="app-title">
              <span className="title-rhythm">Rhythm</span>
              <span className="title-styles">-Styles</span>
            </h1>
          </div>
          <p className="app-subtitle">Transform your song in different style</p>

          {/* Live Server Health Pill */}
          <div className="server-status-pill">
            {serverStatus === 'online' && <span className="status-dot dot-online">● Backend Online</span>}
            {serverStatus === 'waking' && <span className="status-dot dot-waking">◐ Backend Waking Up...</span>}
            {serverStatus === 'offline' && <span className="status-dot dot-offline">○ Web Audio DSP Mode</span>}
            {serverStatus === 'checking' && <span className="status-dot dot-checking">◌ Connecting...</span>}
          </div>
        </header>

        {/* Error Toast Notification if Backend Cold-starts / Network error */}
        {errorMessage && (
          <div className="error-toast animate-section">
            <div className="error-toast-text">
              <span>⚠️ {errorMessage}</span>
            </div>
            <button className="error-close-btn" onClick={() => setErrorMessage(null)}>✕</button>
          </div>
        )}

        <main className="app-main">

          {/* Section 1: Upload Song */}
          <section className="glass-card upload-card animate-section" style={{ animationDelay: '0.2s' }}>
            <h2 className="section-title">
              <span className="step-num">1</span> Upload Song
            </h2>

            <div
              className={`dropzone-container ${isDragOver ? 'drag-over' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />

              {!file ? (
                <>
                  <div className="upload-icon-wrapper">
                    ☁️
                  </div>
                  <div className="dropzone-text-primary">Drop your audio file here</div>
                  <div className="dropzone-text-secondary">or click to browse audio files (.mp3, .wav, .flac)</div>
                </>
              ) : (
                <div className="file-pill">
                  <span>🎵 {file.name} ({(file.size / (1024 * 1024)).toFixed(2)} MB)</span>
                  <button className="remove-file-btn" onClick={handleRemoveFile}>✕</button>
                </div>
              )}
            </div>

            {/* Audio Preview if file uploaded */}
            {filePreviewUrl && (
              <div className="audio-preview-container">
                <div className="audio-preview-label">Source Audio Preview</div>
                <audio controls src={filePreviewUrl} className="custom-audio-player" />
              </div>
            )}
          </section>

          {/* Section 2: Genre Selection (Hero Section) */}
          <section className="glass-card genre-card animate-section" style={{ animationDelay: '0.3s' }}>
            <h2 className="section-title">
              <span className="step-num">2</span> Select Genre
            </h2>

            <div className="genre-grid">
              {genres.map((genre) => {
                const isSelected = selectedGenre === genre;
                const { emoji } = genreDetails[genre];
                return (
                  <div
                    key={genre}
                    className={`genre-tile ${isSelected ? 'active' : ''}`}
                    onClick={() => handleGenreSelect(genre)}
                  >
                    {isSelected && <span className="genre-badge-check">✓</span>}
                    <span className="genre-emoji">{emoji}</span>
                    <span className="genre-name">{genre}</span>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Section 3: Style Intensity */}
          <section className="glass-card intensity-card animate-section" style={{ animationDelay: '0.4s' }}>
            <h2 className="section-title">
              <span className="step-num">3</span> Style Intensity
            </h2>

            <div className="intensity-pills-row">
              {['Low', 'Medium', 'High'].map((level) => (
                <button
                  key={level}
                  className={`intensity-pill-btn ${intensity === level ? 'active' : ''}`}
                  onClick={() => setIntensity(level)}
                >
                  {level}
                </button>
              ))}
            </div>
          </section>

          {/* Section 4: Genre-Specific Effects */}
          <section className="glass-card effects-card animate-section" style={{ animationDelay: '0.5s' }}>
            <h2 className="section-title">
              <span className="step-num">4</span> Genre-Specific Effects
            </h2>

            {!selectedGenre ? (
              <div className="effects-placeholder">
                <span className="lock-icon">🔒</span>
                <p>Select a genre above to unlock specialized effects</p>
              </div>
            ) : (
              <div className="effects-grid">
                {genreDetails[selectedGenre].fx.map((effect) => (
                  <div key={effect} className="effect-control-card">
                    <h4>{effect}</h4>
                    <div className="effect-level-buttons">
                      {['Low', 'Medium', 'High'].map((level) => (
                        <button
                          key={level}
                          className={`effect-level-btn ${effects[effect] === level ? 'active' : ''}`}
                          onClick={() => handleEffectChange(effect, level)}
                        >
                          {level}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Section 5: Global Enhancements */}
          <section className="glass-card global-enhancements-card animate-section" style={{ animationDelay: '0.6s' }}>
            <h2 className="section-title">
              <span className="step-num">5</span> Global Enhancements
            </h2>

            <label className="neon-toggle-wrapper">
              <input
                type="checkbox"
                checked={surround3D}
                onChange={(e) => setSurround3D(e.target.checked)}
                style={{ display: 'none' }}
              />
              <span className="neon-toggle-switch" />
              <span style={{ fontWeight: 500 }}>Enable 3D Surround (8D Spatial Audio)</span>
            </label>

            <div className="neon-slider-wrapper">
              <div className="neon-slider-header">
                <span>Bass Boost</span>
                <span className="neon-slider-val">{bassBoost}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={bassBoost}
                onChange={(e) => setBassBoost(Number(e.target.value))}
                className="neon-range-slider"
              />
            </div>
          </section>

          {/* Transform Button (The Anchor) */}
          <div className="action-container animate-section" style={{ animationDelay: '0.7s' }}>
            <button
              className="transform-btn"
              disabled={!selectedGenre || !file || isTransforming}
              onClick={handleTransform}
            >
              {isTransforming ? (
                <>
                  <div className="waveform-equalizer-btn">
                    {Array.from({ length: 24 }).map((_, idx) => (
                      <span
                        key={idx}
                        className="waveform-bar"
                        style={{
                          animationDelay: `${(idx * 0.05) % 0.8}s`,
                          animationDuration: `${0.4 + (idx % 4) * 0.15}s`
                        }}
                      />
                    ))}
                  </div>
                  <span>{transformStatus || 'TRANSFORMING AUDIO...'}</span>
                </>
              ) : (
                <>
                  <span>⚡ TRANSFORM AUDIO</span>
                </>
              )}
            </button>
          </div>

          {/* Result Section */}
          {resultAudioUrl && (
            <section className="glass-card result-card animate-section">
              <h2 className="section-title" style={{ marginBottom: 0 }}>
                🎉 Transformation Result
              </h2>
              {usedFallback && (
                <span className="mode-badge">⚡ Processed via Client-Side Web Audio DSP</span>
              )}

              <audio controls src={resultAudioUrl} className="custom-audio-player" autoPlay />

              <a
                href={resultAudioUrl}
                download={resultFilename}
                className="download-btn"
              >
                <span>⬇️ Download {resultFilename}</span>
              </a>
            </section>
          )}

        </main>
      </div>
    </>
  );
}

export default App;
