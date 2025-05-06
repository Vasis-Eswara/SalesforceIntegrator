"""
Migration script to add raw_data column to GenerationJob table
"""
import os
import psycopg2
from psycopg2 import sql

# Get the database connection string from environment
DB_URL = os.environ.get("DATABASE_URL")

def run_migration():
    """Add raw_data column to GenerationJob table"""
    print(f"Using database at {DB_URL}")
    
    # Connect to PostgreSQL
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'generation_job' AND column_name = 'raw_data'"
        )
        result = cursor.fetchone()
        
        if not result:
            print("Adding raw_data column to generation_job table...")
            # Add the column safely using SQL identifier quoting
            cursor.execute(
                sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} TEXT").format(
                    sql.Identifier("generation_job"),
                    sql.Identifier("raw_data")
                )
            )
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