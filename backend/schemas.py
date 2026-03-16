from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class QueryRequest(BaseModel):
    """Request model for natural language queries"""
    question: str
    
    class Config:
        schema_extra = {
            "example": {
                "question": "Show me all customers from New York"
            }
        }

class QueryResponse(BaseModel):
    """Response model for query results"""
    success: bool
    user_question: Optional[str] = None
    sql_query: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    row_count: Optional[int] = None
    relevant_tables: Optional[List[str]] = None
    error: Optional[str] = None
    message: Optional[str] = None
    table_name: Optional[str] = None
    database: Optional[str] = None
    columns: Optional[Any] = None  # Changed from int to Any to support both int and list
    action: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    # Metadata response fields
    databases: Optional[List[Dict[str, Any]]] = None
    database_count: Optional[int] = None
    tables: Optional[List[Dict[str, Any]]] = None
    table_count: Optional[int] = None
    column_count: Optional[int] = None
    indexes: Optional[List[Dict[str, Any]]] = None
    index_count: Optional[int] = None
    constraints: Optional[List[Dict[str, Any]]] = None
    constraint_count: Optional[int] = None
    relationships: Optional[List[Dict[str, Any]]] = None
    relationship_count: Optional[int] = None
    status: Optional[str] = None
    created: Optional[str] = None

class AnalyzeRequest(BaseModel):
    """Request model for question analysis"""
    question: str

class TableListResponse(BaseModel):
    """Response model for table listing"""
    tables: List[str]
    count: int

class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    database: str
    embeddings: str
    openai: str

class ColumnDef(BaseModel):
    """Column definition for table creation"""
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False

class CreateTableRequest(BaseModel):
    """Request model for creating a table"""
    database: Optional[str] = None
    table_name: str
    columns: List[ColumnDef]
    
    class Config:
        schema_extra = {
            "example": {
                "database": "TEST",
                "table_name": "customers",
                "columns": [
                    {"name": "id", "type": "int", "primary_key": True, "nullable": False},
                    {"name": "name", "type": "varchar(100)", "nullable": False},
                    {"name": "email", "type": "varchar(100)", "nullable": True}
                ]
            }
        }

class CreateTableResponse(BaseModel):
    """Response model for table creation"""
    success: bool
    message: str
    table_name: str
    database: str
    error: Optional[str] = None
