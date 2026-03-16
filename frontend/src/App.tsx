import React, { useState, useEffect } from 'react'
import { QueryInput } from './components/QueryInput'
import { ResultsDisplay } from './components/ResultsDisplay'
import { QueryResponse, queryApi } from './api'
import './App.css'

function App() {
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<string>('checking')

  useEffect(() => {
    checkHealth()
  }, [])

  const checkHealth = async () => {
    try {
      const response = await queryApi.checkHealth()
      setHealth(response.status === 'healthy' ? 'connected' : 'disconnected')
    } catch {
      setHealth('disconnected')
    }
  }

  const handleQuerySubmit = (result: QueryResponse) => {
    setResult(result)
    if (!result.success) {
      setError(result.error || 'Query failed')
    }
  }

  const handleLoading = (isLoading: boolean) => {
    setLoading(isLoading)
  }

  const handleError = (errorMsg: string | null) => {
    setError(errorMsg)
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>RAG MSSQL Query System</h1>
          <p className="subtitle">Ask questions about your database in natural language</p>
          <div className={`health-indicator ${health}`}>
            <span className="health-dot"></span>
            {health === 'connected' ? 'Backend connected' : 'Backend disconnected'}
          </div>
        </div>
      </header>

      <main className="app-main">
        <QueryInput
          onQuerySubmit={handleQuerySubmit}
          onLoading={handleLoading}
          onError={handleError}
        />

        <ResultsDisplay
          result={result}
          loading={loading}
          error={error}
        />
      </main>

      <footer className="app-footer">
        <p>RAG MSSQL Query System © 2024</p>
      </footer>
    </div>
  )
}

export default App
