import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function FlyList({ title, flies }) {
  if (!flies?.length) {
    return null;
  }

  return (
    <section className="card">
      <h3>{title}</h3>
      <ul className="fly-list">
        {flies.map((fly) => (
          <li key={`${title}-${fly.fly_name}`}>
            <span>{fly.fly_name}</span>
            {fly.type && <small>{fly.type}</small>}
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
    <main className="app">
      <section className="hero">
        <p className="eyebrow">FlyStream</p>
        <h1>Find a focused fly box for your next trout trip.</h1>
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
              <h3>Waters Checked</h3>
              <div className="chips">
                {result.waters.map((water) => (
                  <span key={water}>{water}</span>
                ))}
              </div>
            </section>
          )}

          {!!result.fly_box?.length && (
            <section className="card">
              <h3>Fly Box</h3>
              <div className="chips">
                {result.fly_box.map((flyName) => (
                  <span key={flyName}>{flyName}</span>
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
  );
}

createRoot(document.getElementById('root')).render(<App />);
