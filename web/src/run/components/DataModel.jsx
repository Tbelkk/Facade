import { TYPE_NAME } from '../data/normalize.js';

const fmt = (n) => Number(n).toLocaleString('en-US');

export default function DataModel({ model }) {
  return (
    <section className="run-panel model" aria-label="Data model">
      <div className="run-ph"><h2>Data model</h2><span className="note">from data_model.json</span></div>
      {model.length === 0 ? (
        <div className="empty">No data model yet. It comes from <code>data_model.json</code>.</div>
      ) : (
        <div className="ents">
          {model.map((e) => (
            <div className="ent" key={e.name}>
              <h3>{e.name}<small>{e.fields.length} fields{e.recordCount !== null ? ` · ${fmt(e.recordCount)} records` : ''}</small></h3>
              <div className="fields">
                {e.fields.map((f) => (
                  <span className={'field' + (f.required ? '' : ' opt')} key={f.name} title={`${f.type}${f.required ? ', required' : ', optional'}`}>
                    <b>{f.name}</b> · {TYPE_NAME[f.type] || f.type}
                  </span>
                ))}
              </div>
              {e.rules.length > 0 && <p>{e.rules.length} rule{e.rules.length > 1 ? 's' : ''}</p>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
