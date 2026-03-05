const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function App() {
  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">GuitarOnline</p>
        <h1>Admin Console Bootstrap</h1>
        <p className="summary">
          Vite + React + TypeScript scaffold is ready. Next tasks will add auth flow, protected
          routing, and domain pages.
        </p>
      </section>

      <section className="card">
        <h2>Environment</h2>
        <p>
          <strong>VITE_API_BASE_URL:</strong> <code>{apiBaseUrl}</code>
        </p>
      </section>
    </main>
  );
}
