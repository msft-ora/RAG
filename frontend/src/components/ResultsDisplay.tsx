import React, { useState } from 'react'
import { QueryResponse } from '../api'
import './ResultsDisplay.css'

interface ResultsDisplayProps {
  result: QueryResponse | null
  loading: boolean
  error: string | null
}

export const ResultsDisplay: React.FC<ResultsDisplayProps> = ({ result, loading, error }) => {
  const [showSql, setShowSql] = useState(false)

  if (loading) {
    return <div className="results-loading">Processing query...</div>
  }

  if (error) {
    return <div className="results-error">{error}</div>
  }

  if (!result || !result.success) {
    return <div className="results-empty">Enter a question to get started</div>
  }

  // Handle metadata actions
  if (result.action === 'list_databases' && result.databases) {
    return (
      <div className="results-container">
        <div className="metadata-display">
          <div className="metadata-header">
            <h2>Databases</h2>
            <span className="count-badge">{result.database_count}</span>
          </div>
          <table className="metadata-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>State</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {result.databases.map((db: any) => (
                <tr key={db.name}>
                  <td><strong>{db.name}</strong></td>
                  <td>{db.state}</td>
                  <td>{db.created}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  if (result.action === 'list_tables' && result.tables) {
    return (
      <div className="results-container">
        <div className="metadata-display">
          <div className="metadata-header">
            <h2>Tables in {result.database}</h2>
            <span className="count-badge">{result.table_count}</span>
          </div>
          <table className="metadata-table">
            <thead>
              <tr>
                <th>Table Name</th>
                <th>Schema</th>
              </tr>
            </thead>
            <tbody>
              {result.tables.map((tbl: any) => (
                <tr key={tbl.name}>
                  <td><strong>{tbl.name}</strong></td>
                  <td>{tbl.schema}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  if (result.action === 'show_schema' && result.columns) {
    return (
      <div className="results-container">
        <div className="metadata-display">
          <div className="metadata-header">
            <h2>Schema: {result.table_name}</h2>
            <span className="database-badge">{result.database}</span>
          </div>
          <table className="metadata-table">
            <thead>
              <tr>
                <th>Column Name</th>
                <th>Type</th>
                <th>Nullable</th>
                <th>Max Length</th>
                <th>Precision</th>
              </tr>
            </thead>
            <tbody>
              {result.columns.map((col: any) => (
                <tr key={col.name}>
                  <td><strong>{col.name}</strong></td>
                  <td>{col.type}</td>
                  <td>{col.nullable ? '✓' : '✗'}</td>
                  <td>{col.max_length || '-'}</td>
                  <td>{col.precision || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  if (result.action === 'show_indexes' && result.indexes) {
    return (
      <div className="results-container">
        <div className="metadata-display">
          <div className="metadata-header">
            <h2>Indexes: {result.table_name}</h2>
            <span className="database-badge">{result.database}</span>
          </div>
          {result.indexes.length > 0 ? (
            <table className="metadata-table">
              <thead>
                <tr>
                  <th>Index Name</th>
                  <th>Type</th>
                  <th>Columns</th>
                </tr>
              </thead>
              <tbody>
                {result.indexes.map((idx: any) => (
                  <tr key={idx.name}>
                    <td><strong>{idx.name}</strong></td>
                    <td>{idx.type}</td>
                    <td>{idx.columns.join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="results-empty">No indexes found</p>
          )}
        </div>
      </div>
    )
  }

  if (result.action === 'show_constraints' && result.constraints) {
    return (
      <div className="results-container">
        <div className="metadata-display">
          <div className="metadata-header">
            <h2>Constraints: {result.table_name}</h2>
            <span className="database-badge">{result.database}</span>
          </div>
          {result.constraints.length > 0 ? (
            <table className="metadata-table">
              <thead>
                <tr>
                  <th>Constraint Name</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {result.constraints.map((con: any) => (
                  <tr key={con.name}>
                    <td><strong>{con.name}</strong></td>
                    <td>{con.type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="results-empty">No constraints found</p>
          )}
        </div>
      </div>
    )
  }

  if (result.action === 'show_relationships' && result.relationships) {
    return (
      <div className="results-container">
        <div className="metadata-display">
          <div className="metadata-header">
            <h2>Foreign Key Relationships {result.table_name ? `(${result.table_name})` : ''}</h2>
            <span className="database-badge">{result.database}</span>
          </div>
          {result.relationships.length > 0 ? (
            <table className="metadata-table">
              <thead>
                <tr>
                  <th>Constraint</th>
                  <th>Source Table</th>
                  <th>Source Column</th>
                  <th>References Table</th>
                  <th>References Column</th>
                </tr>
              </thead>
              <tbody>
                {result.relationships.map((rel: any) => (
                  <tr key={rel.constraint}>
                    <td><strong>{rel.constraint}</strong></td>
                    <td>{rel.source_table}</td>
                    <td>{rel.source_column}</td>
                    <td>{rel.references_table}</td>
                    <td>{rel.references_column}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="results-empty">No relationships found</p>
          )}
        </div>
      </div>
    )
  }

  if (result.action === 'database_stats') {
    return (
      <div className="results-container">
        <div className="metadata-display">
          <div className="metadata-header">
            <h2>Database Statistics: {result.database}</h2>
          </div>
          <div className="stats-grid">
            <div className="stat-box">
              <label>Database</label>
              <div className="stat-value">{result.database}</div>
            </div>
            <div className="stat-box">
              <label>Tables</label>
              <div className="stat-value">{result.table_count}</div>
            </div>
            <div className="stat-box">
              <label>Status</label>
              <div className="stat-value">{result.status}</div>
            </div>
            <div className="stat-box">
              <label>Created</label>
              <div className="stat-value-small">{result.created}</div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Handle profile action
  if (result.action === 'profile' && result.profile) {
    const profile = result.profile
    return (
      <div className="results-container">
        <div className="profile-display">
          <div className="profile-header">
            <h2>{profile.table_name}</h2>
            <span className="database-badge">{profile.database}</span>
          </div>

          <div className="profile-stats">
            <div className="stat">
              <label>Rows</label>
              <div className="stat-value">{profile.row_count.toLocaleString()}</div>
            </div>
            <div className="stat">
              <label>Columns</label>
              <div className="stat-value">{profile.column_count}</div>
            </div>
            <div className="stat">
              <label>Size (MB)</label>
              <div className="stat-value">{profile.size_mb.toFixed(2)}</div>
            </div>
            <div className="stat">
              <label>Indexes</label>
              <div className="stat-value">{profile.indexes.length}</div>
            </div>
          </div>

          {profile.columns_detail.length > 0 && (
            <div className="profile-section">
              <h3>Columns</h3>
              <table className="columns-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Nullable</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.columns_detail.map((col) => (
                    <tr key={col.name}>
                      <td>{col.name}</td>
                      <td>{col.type}</td>
                      <td>{col.nullable ? '✓' : '✗'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {profile.indexes.length > 0 && (
            <div className="profile-section">
              <h3>Indexes</h3>
              <ul className="items-list">
                {profile.indexes.map((idx) => (
                  <li key={idx.name}>{idx.name} ({idx.type})</li>
                ))}
              </ul>
            </div>
          )}

          {profile.constraints.length > 0 && (
            <div className="profile-section">
              <h3>Constraints</h3>
              <ul className="items-list">
                {profile.constraints.map((con) => (
                  <li key={con.name}>{con.name} ({con.type})</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="results-container">
      <div className="results-header">
        <h2>Results ({result.row_count} rows)</h2>
        {result.relevant_tables && (
          <div className="relevant-tables">
            <strong>Tables used:</strong> {result.relevant_tables.join(', ')}
          </div>
        )}
      </div>

      {result.sql_query && (
        <div className="sql-section">
          <button 
            className="toggle-sql-btn"
            onClick={() => setShowSql(!showSql)}
          >
            {showSql ? '▼' : '▶'} Generated SQL
          </button>
          {showSql && (
            <pre className="sql-query">
              <code>{result.sql_query}</code>
            </pre>
          )}
        </div>
      )}

      {result.results && result.results.length > 0 ? (
        <div className="results-table-wrapper">
          <table className="results-table">
            <thead>
              <tr>
                {Object.keys(result.results[0]).map((key) => (
                  <th key={key}>{key}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.results.map((row, idx) => (
                <tr key={idx}>
                  {Object.values(row).map((val, cellIdx) => (
                    <td key={cellIdx}>{String(val)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="results-empty">No results found</div>
      )}
    </div>
  )
}
