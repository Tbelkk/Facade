const VIEWS = [['dashboard', 'Dashboard'], ['api', 'API']];

export default function Titlebar({ view, onView }) {
  return (
    <header className="titlebar">
      <a className="brand" href="../" style={{ textDecoration: 'none' }} title="Home">RESTore</a>
      <div className="crumb">Website <span>→</span> data + API</div>
      <nav className="tabs-nav" role="tablist" aria-label="Pages">
        {VIEWS.map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={view === id} data-view={id} onClick={() => onView(id)}>
            {label}
          </button>
        ))}
      </nav>
    </header>
  );
}
