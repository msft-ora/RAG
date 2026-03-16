import pyodbc
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from config import settings
import logging

logger = logging.getLogger(__name__)

class MSSQLConnection:
    """Handles MSSQL database connections with pooling and whitelisting"""
    
    def __init__(self):
        self.connection_string = self._build_connection_string()
        self.whitelisted_tables = set(settings.WHITELISTED_TABLES)
    
    def _build_connection_string(self, database: str = None) -> str:
        """Build ODBC connection string from settings"""
        db_name = database or settings.MSSQL_DATABASE
        # Use Port parameter for FreeTDS driver compatibility
        return (
            f"Driver={{{settings.MSSQL_DRIVER}}};"
            f"Server={settings.MSSQL_SERVER};"
            f"Port=1433;"
            f"Database={db_name};"
            f"UID={settings.MSSQL_USER};"
            f"PWD={settings.MSSQL_PASSWORD};"
        )
    
    def get_connection(self, database: str = None):
        """Context manager for database connections"""
        conn_str = self._build_connection_string(database)
        return self._connect(conn_str)
    
    @contextmanager
    def _connect(self, connection_string: str):
        """Context manager for database connections"""
        conn = None
        try:
            conn = pyodbc.connect(connection_string)
            yield conn
        except pyodbc.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def validate_table_name(self, table_name: str) -> bool:
        """Check if table is in whitelist"""
        return table_name.lower() in {t.lower() for t in self.whitelisted_tables}
    
    def get_table_schema(self, table_name: str) -> Dict[str, str]:
        """Fetch column names and types for a table"""
        if not self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' not in whitelist")
        
        query = """
        SELECT COLUMN_NAME, DATA_TYPE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = ? 
        ORDER BY ORDINAL_POSITION
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (table_name,))
            schema = {row[0]: row[1] for row in cursor.fetchall()}
        
        return schema
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch sample rows from a table"""
        if not self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' not in whitelist")
        
        query = f"SELECT TOP {limit} * FROM [{table_name}]"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return rows
    
    def execute_query(self, query: str, max_results: int = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results"""
        if max_results is None:
            max_results = settings.MAX_QUERY_RESULTS
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()[:max_results]]
        
        return rows
    
    def list_whitelisted_tables(self) -> List[str]:
        """Return list of whitelisted tables"""
        return sorted(list(self.whitelisted_tables))
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get database metadata"""
        return {
            "server": settings.MSSQL_SERVER,
            "database": settings.MSSQL_DATABASE,
            "user": settings.MSSQL_USER,
            "tables_count": len(self.whitelisted_tables),
            "whitelisted_tables": self.list_whitelisted_tables()
        }
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get full schema and sample data for a table"""
        if not self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' not in whitelist")
        
        schema = self.get_table_schema(table_name)
        sample_data = self.get_sample_data(table_name)
        
        return {
            "table_name": table_name,
            "schema": schema,
            "sample_data": sample_data,
            "row_count": len(sample_data)
        }
    
    def create_table(self, table_name: str, columns: List[Dict[str, Any]], database: str = None) -> str:
        """Create a new table in the database"""
        # Validate table name (simple alphanumeric + underscore)
        if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        
        if not columns or len(columns) == 0:
            raise ValueError("At least one column is required")
        
        # Build column definitions
        column_defs = []
        for col in columns:
            col_name = col.get("name", "").strip()
            col_type = col.get("type", "").strip()
            nullable = col.get("nullable", True)
            primary_key = col.get("primary_key", False)
            
            if not col_name or not col_type:
                raise ValueError(f"Column name and type are required")
            
            # Validate column name
            if not all(c.isalnum() or c == '_' for c in col_name):
                raise ValueError(f"Invalid column name: {col_name}")
            
            col_def = f"[{col_name}] {col_type}"
            if not nullable:
                col_def += " NOT NULL"
            if primary_key:
                col_def += " PRIMARY KEY"
            
            column_defs.append(col_def)
        
        # Build CREATE TABLE statement
        create_sql = f"CREATE TABLE [{table_name}] (\n    " + ",\n    ".join(column_defs) + "\n)"
        
        db_name = database or settings.MSSQL_DATABASE
        conn_str = self._build_connection_string(db_name)
        
        try:
            with self._connect(conn_str) as conn:
                cursor = conn.cursor()
                cursor.execute(create_sql)
                conn.commit()
            
            # Add to whitelist
            self.whitelisted_tables.add(table_name)
            logger.info(f"Table '{table_name}' created successfully in database '{db_name}'")
            return f"Table '{table_name}' created successfully"
        
        except pyodbc.Error as e:
            logger.error(f"Error creating table: {e}")
            raise ValueError(f"Failed to create table: {str(e)}")
    
    def drop_table(self, table_name: str, database: str = None) -> str:
        """Drop a table from the database"""
        # Validate table name (simple alphanumeric + underscore)
        if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        
        db_name = database or settings.MSSQL_DATABASE
        conn_str = self._build_connection_string(db_name)
        
        # Build DROP TABLE statement
        drop_sql = f"DROP TABLE [{table_name}]"
        
        try:
            with self._connect(conn_str) as conn:
                cursor = conn.cursor()
                cursor.execute(drop_sql)
                conn.commit()
            
            # Remove from whitelist
            self.whitelisted_tables.discard(table_name)
            logger.info(f"Table '{table_name}' dropped successfully from database '{db_name}'")
            return f"Table '{table_name}' dropped successfully"
        
        except pyodbc.Error as e:
            logger.error(f"Error dropping table: {e}")
            raise ValueError(f"Failed to drop table: {str(e)}")
    
    def profile_table(self, table_name: str, database: str = None) -> Dict[str, Any]:
        """Get comprehensive profile statistics for a table"""
        if not self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' not in whitelist")
        
        db_name = database or settings.MSSQL_DATABASE
        conn_str = self._build_connection_string(db_name)
        
        profile_data = {
            "table_name": table_name,
            "database": db_name,
            "schema": {},
            "row_count": 0,
            "column_count": 0,
            "size_mb": 0,
            "columns_detail": [],
            "indexes": [],
            "constraints": []
        }
        
        try:
            with self._connect(conn_str) as conn:
                cursor = conn.cursor()
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                profile_data["row_count"] = cursor.fetchone()[0]
                
                # Get column information
                schema_query = """
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
                """
                cursor.execute(schema_query, (table_name,))
                columns = cursor.fetchall()
                profile_data["column_count"] = len(columns)
                
                for col in columns:
                    col_name, data_type, is_nullable, char_length, numeric_precision = col
                    col_info = {
                        "name": col_name,
                        "type": data_type,
                        "nullable": is_nullable == "YES",
                        "max_length": char_length,
                        "precision": numeric_precision
                    }
                    profile_data["columns_detail"].append(col_info)
                    profile_data["schema"][col_name] = data_type
                
                # Get constraints (simpler query that works with FreeTDS)
                constraints_query = """
                SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
                WHERE TABLE_NAME = ?
                """
                try:
                    cursor.execute(constraints_query, (table_name,))
                    for constraint_name, constraint_type in cursor.fetchall():
                        profile_data["constraints"].append({
                            "name": constraint_name,
                            "type": constraint_type
                        })
                except Exception as e:
                    logger.warning(f"Could not fetch constraints: {e}")
        
        except pyodbc.Error as e:
            logger.error(f"Error profiling table: {e}")
            raise ValueError(f"Failed to profile table: {str(e)}")
        
        return profile_data
    
    def list_databases(self) -> Dict[str, Any]:
        """List all databases on the server"""
        try:
            with self.get_connection("master") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name, state_desc, create_date 
                    FROM sys.databases 
                    WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')
                    ORDER BY name
                """)
                databases = []
                for db_name, state, create_date in cursor.fetchall():
                    databases.append({
                        "name": db_name,
                        "state": state,
                        "created": str(create_date)
                    })
                return {
                    "databases": databases,
                    "count": len(databases)
                }
        except pyodbc.Error as e:
            logger.error(f"Error listing databases: {e}")
            raise ValueError(f"Failed to list databases: {str(e)}")
    
    def list_tables(self, database: str = None) -> Dict[str, Any]:
        """List all tables in a specific database"""
        db_name = database or settings.MSSQL_DATABASE
        try:
            with self.get_connection(db_name) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT TABLE_NAME, TABLE_SCHEMA
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_TYPE = 'BASE TABLE'
                    ORDER BY TABLE_NAME
                """)
                tables = []
                for table_name, schema in cursor.fetchall():
                    tables.append({
                        "name": table_name,
                        "schema": schema
                    })
                return {
                    "database": db_name,
                    "tables": tables,
                    "count": len(tables)
                }
        except pyodbc.Error as e:
            logger.error(f"Error listing tables: {e}")
            raise ValueError(f"Failed to list tables: {str(e)}")
    
    def get_table_schema(self, table_name: str, database: str = None) -> Dict[str, Any]:
        """Get detailed schema information for a table"""
        if not self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' not in whitelist")
        
        db_name = database or settings.MSSQL_DATABASE
        try:
            with self.get_connection(db_name) as conn:
                cursor = conn.cursor()
                schema_query = """
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH, 
                       NUMERIC_PRECISION, NUMERIC_SCALE, COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
                """
                cursor.execute(schema_query, (table_name,))
                columns = []
                for col in cursor.fetchall():
                    col_name, data_type, is_nullable, char_length, numeric_precision, numeric_scale, col_default = col
                    columns.append({
                        "name": col_name,
                        "type": data_type,
                        "nullable": is_nullable == "YES",
                        "max_length": char_length,
                        "precision": numeric_precision,
                        "scale": numeric_scale,
                        "default": col_default
                    })
                return {
                    "table_name": table_name,
                    "database": db_name,
                    "columns": columns,
                    "column_count": len(columns)
                }
        except pyodbc.Error as e:
            logger.error(f"Error getting table schema: {e}")
            raise ValueError(f"Failed to get table schema: {str(e)}")
    
    def get_table_indexes(self, table_name: str, database: str = None) -> Dict[str, Any]:
        """Get indexes on a table"""
        if not self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' not in whitelist")
        
        db_name = database or settings.MSSQL_DATABASE
        try:
            with self.get_connection(db_name) as conn:
                cursor = conn.cursor()
                # Simpler query that works with FreeTDS
                indexes_query = """
                SELECT i.name, i.type_desc, c.name
                FROM sys.indexes i
                JOIN sys.tables t ON i.object_id = t.object_id
                LEFT JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                LEFT JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE t.name = ?
                ORDER BY i.name, ic.key_ordinal
                """
                cursor.execute(indexes_query, (table_name,))
                indexes = {}
                for idx_name, idx_type, col_name in cursor.fetchall():
                    if idx_name not in indexes:
                        indexes[idx_name] = {
                            "name": idx_name,
                            "type": idx_type,
                            "columns": []
                        }
                    if col_name:
                        indexes[idx_name]["columns"].append(col_name)
                
                return {
                    "table_name": table_name,
                    "database": db_name,
                    "indexes": list(indexes.values()),
                    "index_count": len(indexes)
                }
        except Exception as e:
            logger.warning(f"Error getting table indexes: {e}")
            return {
                "table_name": table_name,
                "database": db_name,
                "indexes": [],
                "index_count": 0,
                "warning": "Could not retrieve indexes"
            }
    
    def get_table_constraints(self, table_name: str, database: str = None) -> Dict[str, Any]:
        """Get constraints on a table"""
        if not self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' not in whitelist")
        
        db_name = database or settings.MSSQL_DATABASE
        try:
            with self.get_connection(db_name) as conn:
                cursor = conn.cursor()
                constraints_query = """
                SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
                WHERE TABLE_NAME = ?
                ORDER BY CONSTRAINT_NAME
                """
                cursor.execute(constraints_query, (table_name,))
                constraints = []
                for constraint_name, constraint_type in cursor.fetchall():
                    constraints.append({
                        "name": constraint_name,
                        "type": constraint_type
                    })
                return {
                    "table_name": table_name,
                    "database": db_name,
                    "constraints": constraints,
                    "constraint_count": len(constraints)
                }
        except pyodbc.Error as e:
            logger.warning(f"Error getting table constraints: {e}")
            return {
                "table_name": table_name,
                "database": db_name,
                "constraints": [],
                "constraint_count": 0,
                "warning": "Could not retrieve constraints"
            }
    
    def get_foreign_keys(self, table_name: str = None, database: str = None) -> Dict[str, Any]:
        """Get foreign key relationships for a table or all tables"""
        db_name = database or settings.MSSQL_DATABASE
        try:
            with self.get_connection(db_name) as conn:
                cursor = conn.cursor()
                if table_name:
                    if not self.validate_table_name(table_name):
                        raise ValueError(f"Table '{table_name}' not in whitelist")
                    
                    fk_query = """
                    SELECT 
                        rc.CONSTRAINT_NAME,
                        kcu1.TABLE_NAME AS source_table,
                        kcu1.COLUMN_NAME AS source_column,
                        kcu2.TABLE_NAME AS referenced_table,
                        kcu2.COLUMN_NAME AS referenced_column
                    FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu1 ON rc.CONSTRAINT_NAME = kcu1.CONSTRAINT_NAME
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2 ON rc.UNIQUE_CONSTRAINT_NAME = kcu2.CONSTRAINT_NAME
                    WHERE kcu1.TABLE_NAME = ? OR kcu2.TABLE_NAME = ?
                    ORDER BY rc.CONSTRAINT_NAME
                    """
                    cursor.execute(fk_query, (table_name, table_name))
                else:
                    fk_query = """
                    SELECT 
                        rc.CONSTRAINT_NAME,
                        kcu1.TABLE_NAME AS source_table,
                        kcu1.COLUMN_NAME AS source_column,
                        kcu2.TABLE_NAME AS referenced_table,
                        kcu2.COLUMN_NAME AS referenced_column
                    FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu1 ON rc.CONSTRAINT_NAME = kcu1.CONSTRAINT_NAME
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2 ON rc.UNIQUE_CONSTRAINT_NAME = kcu2.CONSTRAINT_NAME
                    ORDER BY rc.CONSTRAINT_NAME
                    """
                    cursor.execute(fk_query)
                
                relationships = []
                for fk_name, source_tbl, source_col, ref_tbl, ref_col in cursor.fetchall():
                    relationships.append({
                        "constraint": fk_name,
                        "source_table": source_tbl,
                        "source_column": source_col,
                        "references_table": ref_tbl,
                        "references_column": ref_col
                    })
                
                return {
                    "table_name": table_name,
                    "database": db_name,
                    "relationships": relationships,
                    "count": len(relationships)
                }
        except pyodbc.Error as e:
            logger.warning(f"Error getting foreign keys: {e}")
            return {
                "table_name": table_name,
                "database": db_name,
                "relationships": [],
                "count": 0,
                "warning": "Could not retrieve relationships"
            }
    
    def get_database_stats(self, database: str = None) -> Dict[str, Any]:
        """Get statistics for a database"""
        db_name = database or settings.MSSQL_DATABASE
        try:
            with self.get_connection(db_name) as conn:
                cursor = conn.cursor()
                
                # Table count
                cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
                table_count = cursor.fetchone()[0]
                
                # Get database creation date
                cursor.execute("""
                    SELECT create_date FROM sys.databases WHERE name = ?
                """, (db_name,))
                result = cursor.fetchone()
                create_date = str(result[0]) if result else None
                
                return {
                    "database": db_name,
                    "table_count": table_count,
                    "created": create_date,
                    "status": "Online"
                }
        except pyodbc.Error as e:
            logger.warning(f"Error getting database stats: {e}")
            return {
                "database": db_name,
                "error": str(e)
            }
