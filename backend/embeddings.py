import chromadb
from typing import List, Dict, Any
import json
from config import settings
import logging

logger = logging.getLogger(__name__)

class EmbeddingStore:
    """Manages ChromaDB for storing and retrieving schema embeddings"""
    
    def __init__(self):
        # Use PersistentClient for persistent storage
        import chromadb
        self.client = chromadb.PersistentClient(path="./chroma_data")
        self.collection_name = "mssql_schemas"
        self.collection = self._get_or_create_collection()
    
    def _get_or_create_collection(self):
        """Get or create the schema collection"""
        try:
            return self.client.get_collection(name=self.collection_name)
        except:
            return self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
    
    def store_table_schema(self, table_name: str, schema: Dict[str, str], sample_data: List[Dict]) -> None:
        """Store table schema as embedding in ChromaDB"""
        
        # Create a text representation of the schema
        schema_text = f"Table: {table_name}\n"
        schema_text += "Columns:\n"
        for col_name, col_type in schema.items():
            schema_text += f"  - {col_name}: {col_type}\n"
        
        if sample_data:
            schema_text += "\nSample data:\n"
            for row in sample_data[:3]:
                schema_text += f"  {row}\n"
        
        # Add to ChromaDB
        self.collection.add(
            ids=[table_name],
            documents=[schema_text],
            metadatas=[{
                "table_name": table_name,
                "columns": json.dumps(list(schema.keys())),
                "column_types": json.dumps(schema),
            }],
        )
        
        logger.info(f"Stored schema for table: {table_name}")
    
    def retrieve_similar_tables(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Retrieve tables most relevant to a query"""
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, 5)
        )
        
        if not results["ids"] or not results["ids"][0]:
            return []
        
        relevant_tables = []
        for i, table_id in enumerate(results["ids"][0]):
            relevant_tables.append({
                "table_name": table_id,
                "schema_text": results["documents"][0][i] if results["documents"] else "",
                "similarity": results["distances"][0][i] if results["distances"] else 0,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
            })
        
        return relevant_tables
    
    def clear_collection(self) -> None:
        """Clear all embeddings from collection"""
        self.client.delete_collection(name=self.collection_name)
        self.collection = self._get_or_create_collection()
        logger.info("Cleared embedding collection")
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "total_tables": count,
                "status": "healthy"
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {
                "collection_name": self.collection_name,
                "total_tables": 0,
                "status": "error",
                "error": str(e)
            }
