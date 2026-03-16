import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application settings from environment variables"""
    
    # MSSQL Configuration
    MSSQL_SERVER: str = os.getenv("MSSQL_SERVER", "localhost")
    MSSQL_DATABASE: str = os.getenv("MSSQL_DATABASE", "master")
    MSSQL_USER: str = os.getenv("MSSQL_USER", "sa")
    MSSQL_PASSWORD: str = os.getenv("MSSQL_PASSWORD", "")
    MSSQL_DRIVER: str = os.getenv("MSSQL_DRIVER", "ODBC Driver 17 for SQL Server")
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    
    # ChromaDB Configuration
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    
    # Whitelisted tables (comma-separated)
    WHITELISTED_TABLES: List[str] = [
        t.strip() for t in os.getenv("WHITELISTED_TABLES", "").split(",") 
        if t.strip()
    ]
    
    # Application Configuration
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    MAX_QUERY_RESULTS: int = int(os.getenv("MAX_QUERY_RESULTS", "100"))
    
    class Config:
        env_file = ".env"

settings = Settings()
