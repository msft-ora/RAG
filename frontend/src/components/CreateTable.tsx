import React, { useState } from 'react'
import { queryApi, ColumnDef, CreateTableResponse } from '../api'
import './CreateTable.css'

interface CreateTableProps {
  onTableCreated: (response: CreateTableResponse) => void
  onError: (error: string) => void
}

export const CreateTable: React.FC<CreateTableProps> = ({ onTableCreated, onError }) => {
  const [showForm, setShowForm] = useState(false)
  const [database, setDatabase] = useState('')
  const [tableName, setTableName] = useState('')
  const [columns, setColumns] = useState<ColumnDef[]>([
    { name: '', type: 'varchar(100)', nullable: true, primary_key: false }
  ])
  const [loading, setLoading] = useState(false)

  const dataTypes = [
    'int',
    'bigint',
    'smallint',
    'tinyint',
    'float',
    'decimal(10,2)',
    'varchar(50)',
    'varchar(100)',
    'varchar(255)',
    'varchar(max)',
    'char(10)',
    'text',
    'date',
    'datetime',
    'datetime2',
    'time',
    'bit',
    'uniqueidentifier'
  ]

  const updateColumn = (index: number, field: keyof ColumnDef, value: any) => {
    const newColumns = [...columns]
    newColumns[index] = { ...newColumns[index], [field]: value }
    setColumns(newColumns)
  }

  const addColumn = () => {
    setColumns([...columns, { name: '', type: 'varchar(100)', nullable: true, primary_key: false }])
  }

  const removeColumn = (index: number) => {
    if (columns.length > 1) {
      setColumns(columns.filter((_, i) => i !== index))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!tableName.trim()) {
      onError('Table name is required')
      return
    }

    if (columns.some(col => !col.name.trim())) {
      onError('All column names are required')
      return
    }

    setLoading(true)
    try {
      const response = await queryApi.createTable({
        database: database || undefined,
        table_name: tableName,
        columns: columns.map(col => ({
          name: col.name,
          type: col.type,
          nullable: col.nullable !== false,
          primary_key: col.primary_key || false
        }))
      })

      onTableCreated(response)
      resetForm()
      setShowForm(false)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Failed to create table')
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setDatabase('')
    setTableName('')
    setColumns([{ name: '', type: 'varchar(100)', nullable: true, primary_key: false }])
  }

  return (
    <div className="create-table-container">
      <button
        className="toggle-btn"
        onClick={() => {
          setShowForm(!showForm)
          if (showForm) resetForm()
        }}
      >
        {showForm ? '✕ Close' : '+ Create Table'}
      </button>

      {showForm && (
        <form onSubmit={handleSubmit} className="create-table-form">
          <h2>Create New Table</h2>

          <div className="form-group">
            <label htmlFor="database">Database (optional)</label>
            <input
              id="database"
              type="text"
              value={database}
              onChange={(e) => setDatabase(e.target.value)}
              placeholder="e.g., TEST or TEST_0 (defaults to TEST)"
            />
          </div>

          <div className="form-group">
            <label htmlFor="tableName">Table Name *</label>
            <input
              id="tableName"
              type="text"
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              placeholder="e.g., customers, orders, products"
              required
            />
          </div>

          <div className="columns-section">
            <h3>Columns</h3>
            {columns.map((column, index) => (
              <div key={index} className="column-row">
                <input
                  type="text"
                  placeholder="Column name"
                  value={column.name}
                  onChange={(e) => updateColumn(index, 'name', e.target.value)}
                  className="column-input"
                />

                <select
                  value={column.type}
                  onChange={(e) => updateColumn(index, 'type', e.target.value)}
                  className="column-type"
                >
                  {dataTypes.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={column.primary_key || false}
                    onChange={(e) => updateColumn(index, 'primary_key', e.target.checked)}
                  />
                  Primary Key
                </label>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={column.nullable !== false}
                    onChange={(e) => updateColumn(index, 'nullable', e.target.checked)}
                  />
                  Nullable
                </label>

                <button
                  type="button"
                  onClick={() => removeColumn(index)}
                  disabled={columns.length === 1}
                  className="remove-btn"
                >
                  ✕
                </button>
              </div>
            ))}

            <button type="button" onClick={addColumn} className="add-column-btn">
              + Add Column
            </button>
          </div>

          <div className="form-actions">
            <button type="submit" disabled={loading} className="submit-btn">
              {loading ? 'Creating...' : 'Create Table'}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false)
                resetForm()
              }}
              className="cancel-btn"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
