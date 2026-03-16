"""
Mock pyodbc module for development without ODBC drivers installed.
This allows the application to start and be demonstrated even without database connectivity.
"""

class Error(Exception):
    """Base pyodbc error"""
    pass

class Cursor:
    """Mock cursor object"""
    def __init__(self, conn=None):
        self.conn = conn
        self.description = None
        self._results = []
    
    def execute(self, query, params=None):
        """Mock execute - returns empty results"""
        # Simulate successful execution
        self._results = []
        # Set description for SELECT queries
        if query.strip().upper().startswith('SELECT'):
            self.description = [('Column1',), ('Column2',)]
        return self
    
    def fetchall(self):
        """Return empty results"""
        return self._results
    
    def fetchone(self):
        """Return None (no results)"""
        return None
    
    def close(self):
        """Close cursor"""
        pass

class Connection:
    """Mock connection object"""
    def __init__(self, connection_string):
        self.connection_string = connection_string
    
    def cursor(self):
        """Get a cursor"""
        return Cursor(self)
    
    def close(self):
        """Close connection"""
        pass
    
    def commit(self):
        """Commit transaction"""
        pass
    
    def rollback(self):
        """Rollback transaction"""
        pass

def connect(connection_string):
    """Create a mock connection"""
    return Connection(connection_string)
