# RAG MSSQL Query System

A Retrieval-Augmented Generation (RAG) system that enables natural language queries against MSSQL databases. Ask questions in plain English and get SQL-generated results automatically.

## Architecture

### Backend (Python FastAPI)
- **RAG Pipeline**: Converts natural language to SQL using OpenAI GPT-4
- **MSSQL Integration**: Secure connection with table whitelisting
- **Vector Store**: ChromaDB for schema embeddings
- **API Endpoints**: RESTful interface for queries

### Frontend (React + TypeScript)
- Query interface for natural language input
- Results display and visualization
- Query history
- Table browser

## Setup

### Prerequisites
- Python 3.8+
- Node.js 16+
- MSSQL Server instance
- OpenAI API key

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Create virtual environment (optional but recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:
- `MSSQL_SERVER`: MSSQL server address
- `MSSQL_DATABASE`: Database name
- `MSSQL_USER`: Database user
- `MSSQL_PASSWORD`: Database password
- `OPENAI_API_KEY`: Your OpenAI API key
- `WHITELISTED_TABLES`: Comma-separated list of tables to allow access

5. Run the backend:
```bash
python3 main.py
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start development server:
```bash
npm run dev
```

The UI will be available at `http://localhost:5173`

## API Endpoints

### GET `/health`
Check application health status.

### POST `/query`
Process a natural language query.
```json
{
  "question": "Show me all customers from New York"
}
```

### POST `/analyze`
Analyze a question and show relevant tables without executing.
```json
{
  "question": "Which products were ordered last month?"
}
```

### GET `/tables`
List all whitelisted tables.

### GET `/tables/{table_name}`
Get schema and sample data for a specific table.

### POST `/refresh-embeddings`
Rebuild vector embeddings from current database schemas.

### GET `/embeddings/stats`
Get statistics about the embedding collection.

## Security Considerations

1. **Table Whitelisting**: Only specified tables can be queried
2. **Query Validation**: Generated queries are validated before execution
3. **Environment Variables**: Store credentials securely, never commit `.env`
4. **Rate Limiting**: Implement on production (future)
5. **SQL Injection Prevention**: Always use parameterized queries

## Project Structure

```
RAG/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── db.py                # MSSQL connection module
│   ├── embeddings.py        # ChromaDB integration
│   ├── rag.py               # RAG pipeline logic
│   ├── schemas.py           # Pydantic models
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example         # Environment template
│   └── chroma_db/           # Vector store (auto-created)
│
└── frontend/
    ├── src/
    │   ├── components/      # React components
    │   ├── pages/          # Page components
    │   ├── App.tsx         # Main app
    │   └── main.tsx        # Entry point
    ├── package.json
    └── tsconfig.json
```

## Future Enhancements

- [ ] Rate limiting and usage analytics
- [ ] Query history and saved queries
- [ ] Multiple database support
- [ ] Advanced result visualization
- [ ] User authentication
- [ ] Result caching
- [ ] Custom prompt templates

## Troubleshooting

### MSSQL Connection Error
- Verify `MSSQL_SERVER`, database name, and credentials in `.env`
- Ensure ODBC driver is installed: `sudo apt install odbc-mssqlserver17` (Linux)

### OpenAI API Error
- Check `OPENAI_API_KEY` is valid
- Verify API quota hasn't been exceeded

### ChromaDB Issues
- Delete `chroma_db/` directory and run `/refresh-embeddings` endpoint

## License

MIT
