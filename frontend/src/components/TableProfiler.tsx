import React, { useState } from 'react'
import { queryApi, TableProfile } from '../api'
import './TableProfiler.css'

interface TableProfilerProps {
  tableName?: string
  onProfileLoaded?: (profile: TableProfile) => void
}

export const TableProfiler: React.FC<TableProfilerProps> = ({ tableName, onProfileLoaded }) => {
  const [table, setTable] = useState(tableName || '')
  const [database, setDatabase] = useState('')
  const [profile, setProfile] = useState<TableProfile | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!table.trim()) {
      setError('Table name is required')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const result = await queryApi.profileTable(table, database || undefined)
      setProfile(result.profile)
      if (onProfileLoaded) {
        onProfileLoaded(result.profile)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to profile table')
      setProfile(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="table-profile-container">
      <form onSubmit={handleProfile} className="profile-form">
        <div className="form-group-inline">
          <input
            type="text"
            value={table}
            onChange={(e) => setTable(e.target.value)}
            placeholder="Table name (e.g., orders or TEST_0.products)"
            className="profile-input"
          />
          <button type="submit" disabled={loading} className="profile-btn">
            {loading ? 'Analyzing...' : 'Profile Table'}
          </button>
        </div>
        {error && <div className="error-message">{error}</div>}
      </form>

      {profile && (
        <div className="profile-results">
          <div className="profile-header">
            <h2>{profile.table_name}</h2>
            <span className="database-badge">{profile.database}</span>
          </div>

          <div className="profile-grid">
            <div className="profile-stat">
              <label>Rows</label>
              <div className="stat-value">{profile.row_count.toLocaleString()}</div>
            </div>
            <div className="profile-stat">
              <label>Columns</label>
              <div className="stat-value">{profile.column_count}</div>
            </div>
            <div className="profile-stat">
              <label>Size (MB)</label>
              <div className="stat-value">{profile.size_mb.toFixed(2)}</div>
            </div>
            <div className="profile-stat">
              <label>Indexes</label>
              <div className="stat-value">{profile.indexes.length}</div>
            </div>
          </div>

          <div className="profile-section">
            <h3>Columns ({profile.column_count})</h3>
            <div className="columns-table">
              <div className="table-header">
                <div className="col-name">Name</div>
                <div className="col-type">Type</div>
                <div className="col-nullable">Nullable</div>
              </div>
              {profile.columns_detail.map((col) => (
                <div key={col.name} className="table-row">
                  <div className="col-name">{col.name}</div>
                  <div className="col-type">{col.type}</div>
                  <div className="col-nullable">{col.nullable ? '✓' : '✗'}</div>
                </div>
              ))}
            </div>
          </div>

          {profile.indexes.length > 0 && (
            <div className="profile-section">
              <h3>Indexes ({profile.indexes.length})</h3>
              <div className="indexes-list">
                {profile.indexes.map((idx) => (
                  <div key={idx.name} className="index-item">
                    <span className="index-name">{idx.name}</span>
                    <span className="index-type">{idx.type}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {profile.constraints.length > 0 && (
            <div className="profile-section">
              <h3>Constraints ({profile.constraints.length})</h3>
              <div className="constraints-list">
                {profile.constraints.map((con) => (
                  <div key={con.name} className="constraint-item">
                    <span className="constraint-name">{con.name}</span>
                    <span className="constraint-type">{con.type}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
