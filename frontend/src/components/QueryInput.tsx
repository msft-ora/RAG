import React, { useState } from 'react'
import { queryApi } from '../api'
import './QueryInput.css'

interface QueryInputProps {
  onQuerySubmit: (result: any) => void
  onLoading: (loading: boolean) => void
  onError: (error: string | null) => void
}

export const QueryInput: React.FC<QueryInputProps> = ({
  onQuerySubmit,
  onLoading,
  onError,
}) => {
  const [question, setQuestion] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!question.trim()) {
      onError('Please enter a question')
      return
    }

    setIsSubmitting(true)
    onLoading(true)
    onError(null)

    try {
      const result = await queryApi.submitQuery(question)
      onQuerySubmit(result)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'An error occurred')
    } finally {
      setIsSubmitting(false)
      onLoading(false)
    }
  }

  const handleExamples = async (exampleQuestion: string) => {
    setQuestion(exampleQuestion)
  }

  return (
    <div className="query-input-container">
      <form onSubmit={handleSubmit} className="query-form">
        <div className="input-group">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about your data... e.g., 'Show all customers from New York'"
            className="query-input"
            disabled={isSubmitting}
          />
          <button
            type="submit"
            className="query-button"
            disabled={isSubmitting || !question.trim()}
          >
            {isSubmitting ? 'Processing...' : 'Query'}
          </button>
        </div>
      </form>

      <div className="examples">
        <p>Example questions:</p>
        <div className="example-buttons">
          <button 
            onClick={() => handleExamples('Show me all customers')}
            className="example-btn"
          >
            Show all customers
          </button>
          <button 
            onClick={() => handleExamples('How many orders were placed last month?')}
            className="example-btn"
          >
            Orders last month
          </button>
          <button 
            onClick={() => handleExamples('List top 10 products by sales')}
            className="example-btn"
          >
            Top products
          </button>
        </div>
      </div>
    </div>
  )
}
