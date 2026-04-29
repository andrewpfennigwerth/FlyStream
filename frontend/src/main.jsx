import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import dryIcon from './storage/dry.png';
import flystreamLogo from './storage/flystream-logo.svg';
import junkIcon from './storage/junk.png';
import nymphIcon from './storage/nymph.png';
import streamerIcon from './storage/streamer.png';
import ShaderBackground from './ShaderBackground';
import './styles.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const FLY_TYPE_ICONS = {
  dry: dryIcon,
  junk: junkIcon,
  nymph: nymphIcon,
  streamer: streamerIcon,
};

function FlyList({ title, flies }) {
  if (!flies?.length) {
    return null;
  }

  const icon = FLY_TYPE_ICONS[title.toLowerCase()];

  return (
    <section className="card">
      <div className="fly-card-header">
        {icon && <img src={icon} alt="" aria-hidden="true" />}
        <h3>{title}</h3>
      </div>
      <ul className="fly-list">
        {flies.map((fly) => (
          <li key={`${title}-${fly.fly_name}`}>
            <span>{fly.fly_name}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function App() {
  const [location, setLocation] = useState('Farmington, CT');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setResult(null);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ location }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || 'Could not get recommendations.');
      }

      setResult(payload);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  const fliesByType = result?.flies_by_type || {};

  return (
    <>
      <ShaderBackground />
      <main className="app">
        <section className="hero">
          <div className="brand">
            <img src={flystreamLogo} alt="FlyStream logo" />
            <span>FlyStream</span>
          </div>
          <h1>Find a focused fly box for your next trip.</h1>
          <form onSubmit={handleSubmit} className="search-form">
            <label htmlFor="location">Destination</label>
            <div className="input-row">
              <input
                id="location"
                value={location}
                onChange={(event) => setLocation(event.target.value)}
                placeholder="Farmington, CT"
                required
              />
              <button type="submit" disabled={isLoading}>
                {isLoading ? 'Finding flies...' : 'Recommend flies'}
              </button>
            </div>
          </form>
        </section>

        {error && <p className="error">{error}</p>}

        {result && (
          <section className="results">
            <div className="summary">
              <div>
                <p className="eyebrow">Recommendations for</p>
                <h2>{result.location}</h2>
              </div>
              {result.region && <span className="pill">{result.region.replaceAll('_', ' ')}</span>}
            </div>

            {!!result.waters?.length && (
              <section className="card">
                <h3>Waters Refrenced</h3>
                <div className="chips">
                  {result.waters.map((water) => (
                    <span key={water}>{water}</span>
                  ))}
                </div>
              </section>
            )}

            <div className="grid">
              {Object.entries(fliesByType).map(([type, flies]) => (
                <FlyList key={type} title={type} flies={flies} />
              ))}
            </div>

            {result.verification && (
              <p className="meta">
                Verification: {result.verification.used_llm ? 'LLM checked' : 'local ranking'}
                {result.verification.fallback_used ? ', fallback used' : ''}
              </p>
            )}
          </section>
        )}
      </main>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
