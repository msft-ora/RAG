from openai import OpenAI
from typing import Dict, List, Any
from config import settings
import logging
import re

logger = logging.getLogger(__name__)

class RAGPipeline:
    """Handles RAG workflow: question -> schema retrieval -> SQL generation -> execution"""
    
    def __init__(self, db_connection, embedding_store):
        self.db = db_connection
        self.embeddings = embedding_store
        try:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        except TypeError as e:
            # Handle httpx proxy configuration issue
            logger.warning(f"OpenAI client initialization error (non-critical): {e}")
            self.client = None
    
    def process_query(self, user_question: str) -> Dict[str, Any]:
        """
        End-to-end RAG pipeline:
        1. Check for metadata requests (databases, tables, schema, indexes, constraints, relationships)
        2. Check if user is asking to profile a table
        3. Check if user is asking to create a table
        4. Check if user is asking to drop a table
        5. If none, retrieve relevant table schemas
        6. Generate SQL query
        7. Execute query
        8. Return results
        """
        try:
            # Check metadata requests first
            if self._is_show_databases_request(user_question):
                return self._handle_show_databases_request(user_question)
            
            if self._is_show_tables_request(user_question):
                return self._handle_show_tables_request(user_question)
            
            if self._is_show_schema_request(user_question):
                return self._handle_show_schema_request(user_question)
            
            if self._is_show_indexes_request(user_question):
                return self._handle_show_indexes_request(user_question)
            
            if self._is_show_constraints_request(user_question):
                return self._handle_show_constraints_request(user_question)
            
            if self._is_show_relationships_request(user_question):
                return self._handle_show_relationships_request(user_question)
            
            if self._is_database_stats_request(user_question):
                return self._handle_database_stats_request(user_question)
            
            # Step 0a: Check if user is asking to profile a table
            if self._is_profile_table_request(user_question):
                return self._handle_profile_table_request(user_question)
            
            # Step 0: Check if user is asking to create a table
            if self._is_create_table_request(user_question):
                return self._handle_create_table_request(user_question)
            
            # Step 0b: Check if user is asking to drop a table
            if self._is_drop_table_request(user_question):
                return self._handle_drop_table_request(user_question)
            
            # Step 1: Retrieve relevant schemas
            relevant_tables = self.embeddings.retrieve_similar_tables(user_question, n_results=3)
            
            if not relevant_tables:
                return {
                    "success": False,
                    "error": "No relevant tables found for this query"
                }
            
            # Step 2: Generate SQL
            sql_query = self._generate_sql(user_question, relevant_tables)
            
            if not sql_query:
                return {
                    "success": False,
                    "error": "Failed to generate SQL query"
                }
            
            # Step 3: Execute query
            results = self.db.execute_query(sql_query)
            
            return {
                "success": True,
                "user_question": user_question,
                "sql_query": sql_query,
                "results": results,
                "row_count": len(results),
                "relevant_tables": [t["table_name"] for t in relevant_tables]
            }
        
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_create_table_request(self, user_question: str) -> bool:
        """Check if user is asking to create a table"""
        question_lower = user_question.lower().strip()
        create_keywords = [
            "create table",
            "create a table",
            "make a table",
            "add table",
            "new table",
            "build table"
        ]
        return any(keyword in question_lower for keyword in create_keywords)
    
    def _handle_create_table_request(self, user_question: str) -> Dict[str, Any]:
        """Parse create table request and create the table"""
        try:
            table_info = self._parse_create_table_request(user_question)
            
            if not table_info or not table_info.get("table_name"):
                return {
                    "success": False,
                    "error": "Could not parse table creation request. Expected format: 'create table tablename with columns: col1 type1, col2 type2, ...'"
                }
            
            # Extract database if specified
            database = table_info.get("database")
            table_name = table_info.get("table_name")
            columns = table_info.get("columns", [])
            
            if not columns:
                return {
                    "success": False,
                    "error": "No columns specified. Expected format: 'create table tablename with columns: col1 type1, col2 type2, ...'"
                }
            
            # Call create_table method
            message = self.db.create_table(table_name, columns, database)
            
            # Refresh embeddings to include new table
            try:
                self.embeddings.store_table_schema(
                    table_name,
                    {col["name"]: col["type"] for col in columns},
                    []
                )
            except Exception as e:
                logger.warning(f"Could not update embeddings: {e}")
            
            return {
                "success": True,
                "user_question": user_question,
                "message": message,
                "table_name": table_name,
                "database": database or settings.MSSQL_DATABASE,
                "columns": len(columns)
            }
        
        except Exception as e:
            logger.error(f"Error handling create table request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_create_table_request(self, user_question: str) -> Dict[str, Any]:
        """
        Parse natural language create table request
        Supports formats like:
        - "create table users with columns: id int, name varchar(100)"
        - "create table test_0.products with columns: product_id int primary key"
        - "create new table sales with columns: ..."
        - "make a table inventory in TEST_0 with columns: ..."
        """
        import re
        
        question_lower = user_question.lower()
        result = {}
        
        # Extract database and table name
        # Pattern: "create|make [a|the] [new|fresh] table [called] [database.]tablename [in|with]"
        db_table_match = re.search(r'(?:create|make|build|add)\s+(?:a\s+|the\s+)?(?:new\s+)?(?:table|t)\s+(?:called\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)', question_lower)
        if db_table_match:
            db_table = db_table_match.group(1)
            if '.' in db_table:
                result["database"], result["table_name"] = db_table.split('.')
            else:
                result["table_name"] = db_table
        
        # Also check for database specified separately "in TEST_0"
        if "in " in question_lower and not result.get("database"):
            in_match = re.search(r'\sin\s+([a-zA-Z0-9_]+)\s+with', question_lower)
            if in_match:
                result["database"] = in_match.group(1)
        
        # Extract columns from "with columns:" or "with:" or "columns:"
        columns_match = re.search(r'(?:with\s+)?columns?:\s*(.+?)(?:\s*$|[.!?])', question_lower, re.DOTALL)
        if columns_match:
            columns_str = columns_match.group(1)
            result["columns"] = self._parse_columns(columns_str)
        
        return result
    
    def _parse_columns(self, columns_str: str) -> List[Dict[str, Any]]:
        """
        Parse column definitions from string
        Supports: "id int, name varchar(100), email varchar(100)"
        Also handles: "id int primary key, name varchar(100) not null, salary decimal(10,2)"
        """
        columns = []
        
        # Split by comma but be careful of commas inside parentheses
        col_parts = []
        current = ""
        paren_count = 0
        
        for char in columns_str:
            if char == '(':
                paren_count += 1
                current += char
            elif char == ')':
                paren_count -= 1
                current += char
            elif char == ',' and paren_count == 0:
                if current.strip():
                    col_parts.append(current.strip())
                current = ""
            else:
                current += char
        
        if current.strip():
            col_parts.append(current.strip())
        
        for part in col_parts:
            if not part:
                continue
            
            # Extract column name (first word)
            match = re.match(r'^(\w+)\s+(.+)$', part)
            if not match:
                continue
            
            col_name = match.group(1)
            rest = match.group(2).strip()
            
            # Extract data type - everything until we hit "primary", "not null", etc.
            type_match = re.match(r'^([\w\(\),]+)', rest)
            if not type_match:
                continue
            
            col_type = type_match.group(1).strip()
            
            # Parse flags
            nullable = True
            primary_key = False
            
            part_lower = part.lower()
            if "not null" in part_lower or "notnull" in part_lower:
                nullable = False
            if "primary key" in part_lower or "primarykey" in part_lower:
                primary_key = True
            
            columns.append({
                "name": col_name,
                "type": col_type,
                "nullable": nullable,
                "primary_key": primary_key
            })
        
        return columns
    
    def _is_drop_table_request(self, user_question: str) -> bool:
        """Check if user is asking to drop a table"""
        import re
        question_lower = user_question.lower().strip()
        
        # Check for drop/remove/delete commands
        drop_patterns = [
            r'\b(?:drop|remove|delete)\s+(?:the\s+)?(?:table\s+)?',
            r'\b(?:drop|remove|delete)\s+(?:a\s+)?(?:table\s+)?'
        ]
        
        return any(re.search(pattern, question_lower) for pattern in drop_patterns)
    
    def _handle_drop_table_request(self, user_question: str) -> Dict[str, Any]:
        """Parse drop table request and drop the table"""
        try:
            table_info = self._parse_drop_table_request(user_question)
            
            if not table_info or not table_info.get("table_name"):
                return {
                    "success": False,
                    "error": "Could not parse table drop request. Expected format: 'drop table tablename' or 'drop table database.tablename'"
                }
            
            # Extract database and table name
            database = table_info.get("database")
            table_name = table_info.get("table_name")
            
            # Call drop_table method
            message = self.db.drop_table(table_name, database)
            
            # Remove from whitelist
            try:
                self.db.whitelisted_tables.discard(table_name)
            except Exception as e:
                logger.warning(f"Could not update whitelist: {e}")
            
            return {
                "success": True,
                "user_question": user_question,
                "message": message,
                "table_name": table_name,
                "database": database or settings.MSSQL_DATABASE,
                "action": "dropped"
            }
        
        except Exception as e:
            logger.error(f"Error handling drop table request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_drop_table_request(self, user_question: str) -> Dict[str, Any]:
        """
        Parse natural language drop table request
        Supports formats like:
        - "drop table users"
        - "drop table test_0.products"
        - "delete table from inventory"
        - "remove the users table"
        """
        import re
        
        question_lower = user_question.lower()
        result = {}
        
        # Extract database and table name
        # Pattern: "drop|remove|delete [the|a] [table] [database.]tablename"
        db_table_match = re.search(r'(?:drop|remove|delete)\s+(?:the\s+)?(?:table\s+)?(?:from\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)', question_lower)
        if db_table_match:
            db_table = db_table_match.group(1)
            if '.' in db_table:
                result["database"], result["table_name"] = db_table.split('.')
            else:
                result["table_name"] = db_table
        
        # Also check for database specified separately "in TEST_0"
        if "in " in question_lower and not result.get("database"):
            in_match = re.search(r'\sin\s+([a-zA-Z0-9_]+)(?:\s|$)', question_lower)
            if in_match:
                result["database"] = in_match.group(1)
        
        return result
    
    def _is_profile_table_request(self, user_question: str) -> bool:
        """Check if user is asking to profile a table"""
        import re
        question_lower = user_question.lower().strip()
        
        # Check for profile/analyze commands
        profile_patterns = [
            r'\bprofile\s+(?:the\s+)?(?:table\s+)?',
            r'\banalyze\s+(?:the\s+)?(?:table\s+)?',
            r'\binspect\s+(?:the\s+)?(?:table\s+)?',
            r'\bprofile\s+(?:table\s+)?',
            r'\bget\s+(?:the\s+)?(?:table\s+)?stats',
            r'\btable\s+stats'
        ]
        
        return any(re.search(pattern, question_lower) for pattern in profile_patterns)
    
    def _handle_profile_table_request(self, user_question: str) -> Dict[str, Any]:
        """Parse profile table request and return table statistics"""
        try:
            table_info = self._parse_profile_table_request(user_question)
            
            if not table_info or not table_info.get("table_name"):
                return {
                    "success": False,
                    "error": "Could not parse table profile request. Expected format: 'profile table tablename' or 'analyze table database.tablename'"
                }
            
            # Extract database and table name
            database = table_info.get("database")
            table_name = table_info.get("table_name")
            
            # Get profile data
            profile_data = self.db.profile_table(table_name, database)
            
            return {
                "success": True,
                "user_question": user_question,
                "action": "profile",
                "profile": profile_data
            }
        
        except Exception as e:
            logger.error(f"Error handling profile table request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_profile_table_request(self, user_question: str) -> Dict[str, Any]:
        """
        Parse natural language profile table request
        Supports formats like:
        - "profile table users"
        - "analyze table test_0.products"
        - "get stats for TEST_0.orders"
        - "inspect the table database.tablename"
        """
        import re
        
        question_lower = user_question.lower()
        result = {}
        
        # Extract table name (handle various patterns)
        # Pattern: "profile|analyze|inspect [the|a] [table] [database.]tablename"
        patterns = [
            r'(?:profile|analyze|inspect|stats\s+for)\s+(?:the\s+)?(?:table\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)',
            r'table\s+stats\s+(?:for\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)'
        ]
        
        db_table = None
        for pattern in patterns:
            match = re.search(pattern, question_lower)
            if match:
                db_table = match.group(1)
                break
        
        if db_table:
            if '.' in db_table:
                result["database"], result["table_name"] = db_table.split('.')
            else:
                result["table_name"] = db_table
        
        # Also check for database specified separately "in TEST_0"
        if "in " in question_lower and not result.get("database"):
            in_match = re.search(r'\sin\s+([a-zA-Z0-9_]+)(?:\s|$)', question_lower)
            if in_match:
                result["database"] = in_match.group(1)
        
        return result
    
    def _generate_sql(self, user_question: str, relevant_tables: List[Dict]) -> str:
        """Generate SQL query using OpenAI or fallback to simple template"""
        # If OpenAI client available, use it
        if self.client is not None:
            try:
                schema_context = "\n".join([
                    f"Table: {t['table_name']}\n{t['schema_text']}"
                    for t in relevant_tables
                ])
                
                prompt = f"""
You are a SQL expert. Generate a SQL query to answer the following question.
IMPORTANT: Only generate valid T-SQL SELECT queries. Do not generate INSERT, UPDATE, DELETE, or any other statements.
Do not include explanations, just the SQL query.

Database Schema:
{schema_context}

User Question: {user_question}

SQL Query:
"""
                
                response = self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=500
                )
                
                sql_query = response.choices[0].message.content.strip()
                
                # Basic validation: must be a SELECT statement
                if not sql_query.upper().startswith("SELECT"):
                    logger.warning(f"Generated non-SELECT query: {sql_query}")
                    return None
                
                # Remove markdown code blocks if present
                sql_query = re.sub(r"```sql\n?|```", "", sql_query).strip()
                
                return sql_query
            
            except Exception as e:
                logger.error(f"Error generating SQL with OpenAI: {e}")
                return None
        
        # Fallback: Generate SQL based on question keywords without OpenAI
        if relevant_tables:
            question_lower = user_question.lower()
            
            # Detect which database user is asking about
            target_database = None
            for db in ["test_0", "test_1", "test_2", "master", "model", "msdb", "tempdb"]:
                if db.replace("_", "") in question_lower.replace("_", ""):
                    target_database = db
                    break
            
            # Smart table selection based on question content
            table_name = relevant_tables[0]["table_name"]
            if "order" in question_lower and any(t.lower() == "orders" for t in [rt["table_name"] for rt in relevant_tables]):
                table_name = "orders"
            elif "customer" in question_lower and any(t.lower() == "customers" for t in [rt["table_name"] for rt in relevant_tables]):
                table_name = "customers"
            elif "product" in question_lower and any(t.lower() == "products" for t in [rt["table_name"] for rt in relevant_tables]):
                table_name = "products"
            elif "user" in question_lower and any(t.lower() == "users" for t in [rt["table_name"] for rt in relevant_tables]):
                table_name = "users"
            elif "sale" in question_lower and any(t.lower() == "sales" for t in [rt["table_name"] for rt in relevant_tables]):
                table_name = "sales"
            
            logger.info(f"Using smart fallback SQL generation for table: {table_name} in database: {target_database or 'default'}")
            
            # Detect what the user is asking for
            if ("table" in question_lower and "test_0" in question_lower):
                return "SELECT TABLE_NAME FROM TEST_0.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='dbo'"
            elif ("table" in question_lower and target_database):
                return f"SELECT TABLE_NAME FROM {target_database}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='dbo'"
            elif ("how many database" in question_lower or "list database" in question_lower or
                "count database" in question_lower or "show database" in question_lower):
                return "SELECT name as database_name FROM sys.databases WHERE state_desc='ONLINE' ORDER BY name"
            elif ("how many tables" in question_lower or "count tables" in question_lower or 
                "number of tables" in question_lower):
                if target_database:
                    return f"SELECT COUNT(*) as table_count FROM {target_database}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='dbo'"
                return f"SELECT COUNT(*) as table_count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='dbo'"
            elif ("how many databases" in question_lower or "list database" in question_lower):
                return "SELECT DB_NAME() as database_name"
            elif "count" in question_lower or "how many" in question_lower:
                return f"SELECT COUNT(*) as record_count FROM [{table_name}]"
            elif "sum" in question_lower or "total" in question_lower:
                return f"SELECT SUM(CAST(C1 AS FLOAT)) as total FROM [{table_name}]"
            elif "average" in question_lower or "avg" in question_lower:
                return f"SELECT AVG(CAST(C1 AS FLOAT)) as average FROM [{table_name}]"
            elif "max" in question_lower:
                return f"SELECT MAX(CAST(C1 AS FLOAT)) as max_value FROM [{table_name}]"
            elif "min" in question_lower:
                return f"SELECT MIN(CAST(C1 AS FLOAT)) as min_value FROM [{table_name}]"
            elif "distinct" in question_lower or "unique" in question_lower:
                return f"SELECT DISTINCT * FROM [{table_name}]"
            elif "database" in question_lower and "table" not in question_lower:
                return "SELECT DB_NAME() as database_name"
            elif "table" in question_lower and "count" not in question_lower and "how many" not in question_lower:
                return f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='dbo'"
            else:
                # Default: return limited rows
                return f"SELECT TOP 10 * FROM [{table_name}]"
        
        logger.error("No OpenAI client and no relevant tables")
        return None
    
    def analyze_question(self, user_question: str) -> Dict[str, Any]:
        """Analyze question without executing SQL"""
        try:
            relevant_tables = self.embeddings.retrieve_similar_tables(user_question, n_results=3)
            
            return {
                "success": True,
                "question": user_question,
                "relevant_tables": [
                    {
                        "table_name": t["table_name"],
                        "similarity_score": t["similarity"],
                        "columns": t["metadata"].get("columns", "")
                    }
                    for t in relevant_tables
                ]
            }
        except Exception as e:
            logger.error(f"Error analyzing question: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ============ METADATA MANAGEMENT REQUESTS ============
    
    def _is_show_databases_request(self, user_question: str) -> bool:
        """Check if user is asking to show/list databases"""
        patterns = [
            r'\bshow\s+databases\b',
            r'\blist\s+databases\b',
            r'\bget\s+all\s+databases\b',
            r'\ball\s+databases\b',
            r'\bwhat\s+databases\b',
            r'\bwhich\s+databases\b'
        ]
        return any(re.search(p, user_question.lower()) for p in patterns)
    
    def _handle_show_databases_request(self, user_question: str) -> Dict[str, Any]:
        """Handle show databases request"""
        try:
            result = self.db.list_databases()
            return {
                "success": True,
                "user_question": user_question,
                "action": "list_databases",
                "message": f"Found {result['count']} databases",
                "databases": result["databases"],
                "database_count": result["count"]
            }
        except Exception as e:
            logger.error(f"Error listing databases: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_show_tables_request(self, user_question: str) -> bool:
        """Check if user is asking to show/list tables in a database"""
        patterns = [
            r'(?:show|list|get|display)\s+(?:all\s+)?tables',
            r'what\s+tables\s+(?:are\s+)?(?:in\s+)?',
            r'which\s+tables\s+(?:in\s+)?',
            r'tables\s+in\s+',
            r'(?:all|list)\s+tables'
        ]
        return any(re.search(p, user_question.lower()) for p in patterns)
    
    def _handle_show_tables_request(self, user_question: str) -> Dict[str, Any]:
        """Handle show tables request"""
        try:
            # Extract database name if specified
            database = None
            db_patterns = [
                r'in\s+([a-zA-Z0-9_]+)',
                r'from\s+([a-zA-Z0-9_]+)',
                r'(?:database|db)\s+([a-zA-Z0-9_]+)'
            ]
            for pattern in db_patterns:
                match = re.search(pattern, user_question.lower())
                if match:
                    database = match.group(1)
                    break
            
            result = self.db.list_tables(database)
            return {
                "success": True,
                "user_question": user_question,
                "action": "list_tables",
                "message": f"Found {result['count']} tables in {result['database']}",
                "database": result["database"],
                "tables": result["tables"],
                "table_count": result["count"]
            }
        except Exception as e:
            logger.error(f"Error listing tables: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_show_schema_request(self, user_question: str) -> bool:
        """Check if user is asking for table schema/columns"""
        patterns = [
            r'(?:show|display|get|describe)\s+(?:schema|columns|structure)\s+',
            r'columns\s+(?:in|of|for)\s+',
            r'(?:table\s+)?schema\s+(?:of|for)\s+',
            r'(?:describe|desc)\s+(?:table\s+)?',
            r'structure\s+of\s+'
        ]
        return any(re.search(p, user_question.lower()) for p in patterns)
    
    def _handle_show_schema_request(self, user_question: str) -> Dict[str, Any]:
        """Handle show schema request"""
        try:
            # Extract table name
            table_name = None
            patterns = [
                r'(?:schema|columns|structure)\s+(?:of\s+)?(?:table\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)',
                r'(?:describe|desc)\s+(?:table\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)',
                r'columns\s+(?:in|of|for)\s+(?:table\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)'
            ]
            
            database = None
            for pattern in patterns:
                match = re.search(pattern, user_question.lower())
                if match:
                    db_table = match.group(1)
                    if '.' in db_table:
                        database, table_name = db_table.split('.')
                    else:
                        table_name = db_table
                    break
            
            if not table_name:
                raise ValueError("Could not extract table name from request")
            
            result = self.db.get_table_schema(table_name, database)
            return {
                "success": True,
                "user_question": user_question,
                "action": "show_schema",
                "message": f"Schema for {result['table_name']} in {result['database']}",
                "table_name": result["table_name"],
                "database": result["database"],
                "columns": result["columns"],
                "column_count": result["column_count"]
            }
        except Exception as e:
            logger.error(f"Error getting table schema: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_show_indexes_request(self, user_question: str) -> bool:
        """Check if user is asking for table indexes"""
        patterns = [
            r'(?:show|display|get|list)\s+indexes',
            r'indexes\s+(?:on|for)\s+',
            r'(?:table\s+)?indexes\b',
            r'(?:index|indices)\s+of\s+'
        ]
        return any(re.search(p, user_question.lower()) for p in patterns)
    
    def _handle_show_indexes_request(self, user_question: str) -> Dict[str, Any]:
        """Handle show indexes request"""
        try:
            # Extract table name
            table_name = None
            patterns = [
                r'indexes\s+(?:on|for)\s+(?:table\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)',
                r'(?:table\s+)?indexes\s+(?:on|for)\s+([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)',
                r'(?:index|indices)\s+of\s+(?:table\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)'
            ]
            
            database = None
            for pattern in patterns:
                match = re.search(pattern, user_question.lower())
                if match:
                    db_table = match.group(1)
                    if '.' in db_table:
                        database, table_name = db_table.split('.')
                    else:
                        table_name = db_table
                    break
            
            if not table_name:
                raise ValueError("Could not extract table name from request")
            
            result = self.db.get_table_indexes(table_name, database)
            return {
                "success": True,
                "user_question": user_question,
                "action": "show_indexes",
                "message": f"Indexes for {result['table_name']} in {result['database']}",
                "table_name": result["table_name"],
                "database": result["database"],
                "indexes": result["indexes"],
                "index_count": result["index_count"]
            }
        except Exception as e:
            logger.error(f"Error getting table indexes: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_show_constraints_request(self, user_question: str) -> bool:
        """Check if user is asking for table constraints"""
        patterns = [
            r'(?:show|display|get|list)\s+constraints',
            r'constraints\s+(?:on|for|in)\s+',
            r'(?:table\s+)?constraints\b',
            r'(?:primary\s+key|foreign\s+key|constraint)',
        ]
        return any(re.search(p, user_question.lower()) for p in patterns)
    
    def _handle_show_constraints_request(self, user_question: str) -> Dict[str, Any]:
        """Handle show constraints request"""
        try:
            # Extract table name
            table_name = None
            patterns = [
                r'constraints\s+(?:on|for|in)\s+(?:table\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)',
                r'(?:table\s+)?constraints\s+(?:on|for|in)\s+([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)',
                r'(?:primary|foreign)\s+(?:key|keys)\s+(?:on|for|in)\s+(?:table\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)'
            ]
            
            database = None
            for pattern in patterns:
                match = re.search(pattern, user_question.lower())
                if match:
                    db_table = match.group(1)
                    if '.' in db_table:
                        database, table_name = db_table.split('.')
                    else:
                        table_name = db_table
                    break
            
            if not table_name:
                raise ValueError("Could not extract table name from request")
            
            result = self.db.get_table_constraints(table_name, database)
            return {
                "success": True,
                "user_question": user_question,
                "action": "show_constraints",
                "message": f"Constraints for {result['table_name']} in {result['database']}",
                "table_name": result["table_name"],
                "database": result["database"],
                "constraints": result["constraints"],
                "constraint_count": result["constraint_count"]
            }
        except Exception as e:
            logger.error(f"Error getting table constraints: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_show_relationships_request(self, user_question: str) -> bool:
        """Check if user is asking for foreign key relationships"""
        patterns = [
            r'(?:show|display|get|list)\s+(?:foreign\s+key|relationship)',
            r'relationships?\s+(?:in|for|of)',
            r'foreign\s+keys?\s+(?:in|on|for)',
            r'(?:relationship|linked?)\s+(?:table|to)',
            r'(?:reference|referenc)',
        ]
        return any(re.search(p, user_question.lower()) for p in patterns)
    
    def _handle_show_relationships_request(self, user_question: str) -> Dict[str, Any]:
        """Handle show relationships request"""
        try:
            # Extract table name if specified
            table_name = None
            patterns = [
                r'(?:foreign\s+key|relationship)s?\s+(?:of|for|in)\s+(?:table\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)',
                r'(?:relationships?|reference)\s+(?:in|for)\s+(?:table\s+)?([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)',
            ]
            
            database = None
            for pattern in patterns:
                match = re.search(pattern, user_question.lower())
                if match:
                    db_table = match.group(1)
                    if '.' in db_table:
                        database, table_name = db_table.split('.')
                    else:
                        table_name = db_table
                    break
            
            result = self.db.get_foreign_keys(table_name, database)
            return {
                "success": True,
                "user_question": user_question,
                "action": "show_relationships",
                "message": f"Relationships for {result.get('table_name', 'all tables')}",
                "table_name": result.get("table_name"),
                "database": result["database"],
                "relationships": result["relationships"],
                "relationship_count": result["count"]
            }
        except Exception as e:
            logger.error(f"Error getting relationships: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_database_stats_request(self, user_question: str) -> bool:
        """Check if user is asking for database statistics"""
        patterns = [
            r'database\s+(?:stat|info|size|summary)',
            r'(?:get|show|display)\s+database\s+stat',
            r'how\s+many\s+tables\s+(?:in\s+)?(?:the\s+)?database',
            r'database\s+(?:info|information|detail|overview)',
        ]
        return any(re.search(p, user_question.lower()) for p in patterns)
    
    def _handle_database_stats_request(self, user_question: str) -> Dict[str, Any]:
        """Handle database stats request"""
        try:
            # Extract database name if specified
            database = None
            db_patterns = [
                r'(?:in|for)\s+(?:database|db)\s+([a-zA-Z0-9_]+)',
                r'database\s+([a-zA-Z0-9_]+)\s+stat',
            ]
            for pattern in db_patterns:
                match = re.search(pattern, user_question.lower())
                if match:
                    database = match.group(1)
                    break
            
            result = self.db.get_database_stats(database)
            return {
                "success": True,
                "user_question": user_question,
                "action": "database_stats",
                "message": f"Statistics for {result['database']}",
                "database": result["database"],
                "table_count": result.get("table_count"),
                "created": result.get("created"),
                "status": result.get("status")
            }
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {
                "success": False,
                "error": str(e)
            }
