import { useState } from 'react'
import './App.css'

function App() {
  const [selectedGenre, setSelectedGenre] = useState('');
  const [intensity, setIntensity] = useState('Medium');
  const [effects, setEffects] = useState({});
  const [file, setFile] = useState(null);
  const [isTransforming, setIsTransforming] = useState(false);
  const [resultAudioUrl, setResultAudioUrl] = useState(null);
  const [resultFilename, setResultFilename] = useState('');
  
  // Global Effects
  const [surround3D, setSurround3D] = useState(false);
  const [bassBoost, setBassBoost] = useState(0);

  const genreEffectsMap = {
    'Rock': ['Distortion', 'Overdrive', 'Reverb', 'Drum Impact'],
    'Pop': ['Reverb', 'Chorus', 'Delay', 'Compression'],
    'Disco': ['Groove', 'Bass Punch', 'Chorus', 'Reverb'],
    '8-bit / Chiptune': ['Bit Crush', 'Downsampling', '8-bit Synthesis', 'Retro Filter'],
    'Synthwave / 1980s': ['Chorus', 'Delay', 'Reverb', 'Retro Filter'],
    'Metal': ['Distortion', 'Compression', 'Drum Impact', 'Low-End'],
    'Ballad': ['Reverb', 'Delay', 'Warmth', 'Dynamics'],
    'Reggae': ['Bass', 'Offbeat Groove', 'Delay', 'Reverb'],
    'Funk': ['Bass Groove', 'Compression', 'Wah/Filter', 'Drum Groove'],
    'Jazz': ['Swing', 'Reverb', 'Warmth', 'Improvisation']
  };

  const genres = Object.keys(genreEffectsMap);

  const handleGenreSelect = (genre) => {
    setSelectedGenre(genre);
    const initialEffects = {};
    genreEffectsMap[genre].forEach(effect => {
      initialEffects[effect] = 'Medium';
    });
    setEffects(initialEffects);
  };

  const handleEffectChange = (effect, level) => {
    setEffects(prev => ({ ...prev, [effect]: level }));
  };

  const handleTransform = async () => {
    if (!file || !selectedGenre) return;
    
    setIsTransforming(true);
    setResultAudioUrl(null);
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('genre', selectedGenre);
    formData.append('intensity', intensity);
    formData.append('effects', JSON.stringify(effects));
    formData.append('surround_3d', surround3D);
    formData.append('bass_boost', bassBoost);

    try {
      const response = await fetch('http://127.0.0.1:8000/transform/', {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server status ${response.status}: ${errorText || response.statusText}`);
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      setResultAudioUrl(url);
      
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = 'transformed_audio.wav';
      if (contentDisposition && contentDisposition.includes('filename=')) {
        filename = contentDisposition.split('filename=')[1].replace(/["']/g, '');
      }
      setResultFilename(filename);
      
    } catch (error) {
      console.error('Error transforming audio:', error);
      alert(`Transformation failed: ${error.message}`);
    } finally {
      setIsTransforming(false);
    }
  };

  return (
    <div className="app-container">
      <header>
        <h1>Rhythm-Styles 🎵</h1>
        <p>Transform your song in different style</p>
      </header>

      <main>
        <section className="upload-section">
          <h2>1. Upload Song</h2>
          <div className="file-upload">
            <input 
              type="file" 
              accept="audio/*" 
              onChange={(e) => setFile(e.target.files[0])}
            />
            {file && <p className="file-name">Selected: {file.name}</p>}
          </div>
        </section>

        <section className="genre-section">
          <h2>2. Select Genre</h2>
          <div className="genre-grid">
            {genres.map(genre => (
              <button 
                key={genre} 
                className={`genre-btn ${selectedGenre === genre ? 'active' : ''}`}
                onClick={() => handleGenreSelect(genre)}
              >
                {genre}
              </button>
            ))}
          </div>
        </section>

        <section className="intensity-section">
          <h2>3. Style Intensity</h2>
          <div className="radio-group">
            {['Low', 'Medium', 'High'].map(level => (
              <label key={level} className="radio-label">
                <input 
                  type="radio" 
                  name="intensity" 
                  value={level}
                  checked={intensity === level}
                  onChange={(e) => setIntensity(e.target.value)}
                />
                {level}
              </label>
            ))}
          </div>
        </section>

        {/* Effects section will dynamically update based on genre */}
        <section className="effects-section">
          <h2>4. Genre-Specific Effects</h2>
          {!selectedGenre ? (
            <p className="placeholder-text">Select a genre to see effects.</p>
          ) : (
            <div className="effects-grid">
              {genreEffectsMap[selectedGenre].map(effect => (
                <div key={effect} className="effect-control">
                  <h3>{effect}</h3>
                  <div className="radio-group effect-radio-group">
                    {['Low', 'Medium', 'High'].map(level => (
                      <label key={level} className="radio-label">
                        <input 
                          type="radio" 
                          name={`effect-${effect}`} 
                          value={level}
                          checked={effects[effect] === level}
                          onChange={(e) => handleEffectChange(effect, e.target.value)}
                        />
                        {level}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="global-effects-section">
          <h2>Global Enhancements</h2>
          <div className="global-effects-container">
            <label className="checkbox-label">
              <input 
                type="checkbox" 
                checked={surround3D}
                onChange={(e) => setSurround3D(e.target.checked)}
              />
              Enable 3D Surround (8D Audio)
            </label>
            
            <div className="slider-container">
              <label>
                Bass Boost: {bassBoost}%
              </label>
              <input 
                type="range" 
                min="0" 
                max="100" 
                value={bassBoost} 
                onChange={(e) => setBassBoost(e.target.value)}
                className="slider"
              />
            </div>
          </div>
        </section>
        
        <div className="action-section">
            <button 
              className="transform-btn" 
              disabled={!selectedGenre || !file || isTransforming}
              onClick={handleTransform}
            >
                {isTransforming ? 'Transforming...' : 'Transform Audio'}
            </button>
        </div>

        {resultAudioUrl && (
          <section className="result-section">
            <h2>5. Result</h2>
            <div className="audio-player-container">
              <audio controls src={resultAudioUrl} className="audio-player" />
            </div>
            <div className="download-container">
              <a 
                href={resultAudioUrl} 
                download={resultFilename} 
                className="download-btn"
              >
                ⬇️ Download {resultFilename}
              </a>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
