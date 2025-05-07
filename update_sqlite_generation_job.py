"""
Migration script to add raw_data column to GenerationJob table for SQLite
"""
import os
import sqlite3

# SQLite database path
DB_PATH = 'salesforce_app.db'

def run_migration():
    """Add raw_data column to GenerationJob table in SQLite"""
    print(f"Using SQLite database at {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='generation_job'")
        if not cursor.fetchone():
            print("Table 'generation_job' does not exist, skipping migration")
            return True
            
        # Check if column already exists
        cursor.execute("PRAGMA table_info(generation_job)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]  # column[1] contains the column name
        
        if 'raw_data' not in column_names:
            print("Adding raw_data column to generation_job table...")
            cursor.execute("ALTER TABLE generation_job ADD COLUMN raw_data TEXT")
            conn.commit()
            print("Column added successfully")
        else:
            print("Column raw_data already exists, no changes made")
        
        cursor.close()
        conn.close()
        print("Migration completed")
        
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        return False
        
    return True

if __name__ == "__main__":
    run_migration()