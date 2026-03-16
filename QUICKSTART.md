# Quick Start Guide

## Setup Steps

### 1. Backend Configuration

```bash
cd backend
cp .env.example .env
```

Edit `.env` with your MSSQL credentials and OpenAI API key:
```
MSSQL_SERVER=your_server_address
MSSQL_DATABASE=your_database
MSSQL_USER=your_username
MSSQL_PASSWORD=your_password
OPENAI_API_KEY=your_openai_key
WHITELISTED_TABLES=Table1,Table2,Table3
```

### 2. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Start Backend Server

```bash
cd backend
python3 main.py
```

The API will be available at `http://localhost:8000`

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 5. Start Frontend Development Server

```bash
cd frontend
npm run dev
```

The UI will be available at `http://localhost:5173`

## Testing the System

1. Navigate to `http://localhost:5173`
2. Check that the "Backend connected" indicator appears in the header
3. Try an example query from the suggested buttons
4. Or type your own natural language question about your database

## Troubleshooting

### Backend won't start
- Check MSSQL connection credentials in `.env`
- Verify ODBC driver is installed: `odbcinst -j` (Linux)
- Check OpenAI API key is valid

### Frontend won't load
- Verify Node.js is installed: `node --version`
- Check port 5173 is not in use

### Queries not working
- Ensure whitelisted tables exist in your database
- Check backend logs for specific error messages
- Try running `/refresh-embeddings` endpoint to rebuild schema embeddings

## API Documentation

Once backend is running, visit `http://localhost:8000/docs` for interactive API docs.

## Project Structure

```
RAG/
├── backend/
│   ├── main.py          # FastAPI app entry point
│   ├── db.py            # MSSQL connection
│   ├── embeddings.py    # ChromaDB integration
│   ├── rag.py           # RAG pipeline
│   ├── config.py        # Settings
│   ├── schemas.py       # Data models
│   └── requirements.txt  # Dependencies
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx      # Main app component
│   │   ├── api.ts       # API client
│   │   └── components/  # React components
│   ├── package.json
│   └── index.html
│
└── README.md            # Full documentation
```

## Next Steps

1. Set up your MSSQL database connection
2. Configure whitelisted tables
3. Run `/refresh-embeddings` after schema changes
4. Start using natural language queries!
