from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from config import settings
from db import MSSQLConnection
from embeddings import EmbeddingStore
from rag import RAGPipeline
from schemas import QueryRequest, QueryResponse, AnalyzeRequest, TableListResponse, HealthResponse, CreateTableRequest, CreateTableResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize components
mssql_conn = None
embedding_store = None
rag_pipeline = None
scheduler = None

def refresh_embeddings_task():
    """Background task to refresh embeddings"""
    try:
        logger.info("Auto-refreshing embeddings...")
        embedding_store.clear_collection()
        for table_name in mssql_conn.list_whitelisted_tables():
            table_info = mssql_conn.get_table_info(table_name)
            embedding_store.store_table_schema(
                table_name,
                table_info["schema"],
                table_info["sample_data"]
            )
        logger.info("✓ Embeddings auto-refreshed successfully")
    except Exception as e:
        logger.error(f"Error auto-refreshing embeddings: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup, cleanup on shutdown"""
    global mssql_conn, embedding_store, rag_pipeline, scheduler
    
    # Startup
    logger.info("Starting RAG application...")
    mssql_conn = MSSQLConnection()
    embedding_store = EmbeddingStore()
    rag_pipeline = RAGPipeline(mssql_conn, embedding_store)
    
    # Start background scheduler for automatic embedding refresh (every 1 hour)
    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh_embeddings_task, 'interval', minutes=60)
    scheduler.start()
    logger.info("Embeddings auto-refresh scheduled every 60 minutes")
    logger.info("Application initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    if scheduler:
        scheduler.shutdown()

app = FastAPI(
    title="RAG MSSQL Query System",
    description="Natural language query interface for MSSQL databases",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check application health"""
    return {
        "status": "healthy",
        "database": "connected",
        "embeddings": "ready",
        "openai": "configured"
    }

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process natural language query and return results"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    result = rag_pipeline.process_query(request.question)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Query processing failed"))
    
    return result

@app.post("/analyze")
async def analyze_query(request: AnalyzeRequest):
    """Analyze a question and show relevant tables without executing"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    result = rag_pipeline.analyze_question(request.question)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
    
    return result

@app.get("/tables", response_model=TableListResponse)
async def list_tables():
    """List all whitelisted tables"""
    tables = mssql_conn.list_whitelisted_tables()
    return {
        "tables": tables,
        "count": len(tables)
    }

@app.get("/database")
async def get_database():
    """Get database metadata and connection info"""
    try:
        db_info = mssql_conn.get_database_info()
        return db_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tables/{table_name}")
async def get_table_info(table_name: str):
    """Get schema and sample data for a specific table"""
    try:
        info = mssql_conn.get_table_info(table_name)
        return info
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/refresh-embeddings")
async def refresh_embeddings(background_tasks: BackgroundTasks):
    """Rebuild embeddings from current database schemas"""
    def rebuild_embeddings():
        try:
            embedding_store.clear_collection()
            for table_name in mssql_conn.list_whitelisted_tables():
                table_info = mssql_conn.get_table_info(table_name)
                embedding_store.store_table_schema(
                    table_name,
                    table_info["schema"],
                    table_info["sample_data"]
                )
            logger.info("Embeddings refreshed successfully")
        except Exception as e:
            logger.error(f"Error rebuilding embeddings: {e}")
    
    background_tasks.add_task(rebuild_embeddings)
    return {"status": "rebuilding", "message": "Embedding refresh started in background"}

@app.get("/embeddings/stats")
async def embedding_stats():
    """Get statistics about the embedding collection"""
    stats = embedding_store.get_collection_stats()
    return stats

@app.post("/create-table", response_model=CreateTableResponse)
async def create_table(request: CreateTableRequest):
    """Create a new table in the database"""
    try:
        db_name = request.database or settings.MSSQL_DATABASE
        columns = [col.model_dump() for col in request.columns]
        message = mssql_conn.create_table(request.table_name, columns, db_name)
        
        return {
            "success": True,
            "message": message,
            "table_name": request.table_name,
            "database": db_name,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error creating table: {e}")
        return {
            "success": False,
            "message": f"Failed to create table",
            "table_name": request.table_name,
            "database": request.database or settings.MSSQL_DATABASE,
            "error": str(e)
        }

@app.get("/profile/{table_name}")
async def profile_table(table_name: str, database: str = None):
    """Get comprehensive profile statistics for a table"""
    try:
        db_name = database or settings.MSSQL_DATABASE
        profile_data = mssql_conn.profile_table(table_name, db_name)
        return {
            "success": True,
            "profile": profile_data
        }
    except Exception as e:
        logger.error(f"Error profiling table: {e}")
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
