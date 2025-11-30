"""
Simple migration script to add new columns to existing database
Run this once to update your database schema
"""
from sqlalchemy import text
from database import engine

def migrate():
    """Add new columns to users table if they don't exist"""
    with engine.connect() as conn:
        # Check if columns exist and add them if they don't
        try:
            # SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN
            # So we'll try to add them and catch the error if they already exist
            conn.execute(text("ALTER TABLE users ADD COLUMN display_name VARCHAR"))
            print("Added display_name column")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("display_name column already exists")
            else:
                print(f"Error adding display_name: {e}")
        
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN bio TEXT"))
            print("Added bio column")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("bio column already exists")
            else:
                print(f"Error adding bio: {e}")
        
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN profile_picture_url VARCHAR"))
            print("Added profile_picture_url column")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("profile_picture_url column already exists")
            else:
                print(f"Error adding profile_picture_url: {e}")
        
        conn.commit()
        print("\nMigration completed!")

if __name__ == "__main__":
    migrate()

