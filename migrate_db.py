"""
Database Migration Script
Adds photo_url column to existing reports table
Run this ONCE before starting the app if you have existing data
"""

import sqlite3
import os

DB_PATH = "instance/viperaid.db"

def migrate_database():
    """Add photo_url column to reports table if it doesn't exist"""
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print("✓ No existing database found - will be created on first run")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if photo_url column exists
        cursor.execute("PRAGMA table_info(report)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'photo_url' in columns:
            print("✓ photo_url column already exists - no migration needed")
        else:
            print("Adding photo_url column...")
            cursor.execute("ALTER TABLE report ADD COLUMN photo_url VARCHAR(300)")
            conn.commit()
            print("✓ photo_url column added successfully")
        
        # Show current reports
        cursor.execute("SELECT id, animal_type, urgency, created_at FROM report ORDER BY created_at DESC LIMIT 5")
        reports = cursor.fetchall()
        
        if reports:
            print(f"\n✓ Found {len(reports)} recent report(s):")
            for r in reports:
                print(f"  - {r[0]}: {r[1]} ({r[2]}) - {r[3]}")
        else:
            print("\n✓ No reports in database yet")
            
    except Exception as e:
        print(f"✗ Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("ViperAid Database Migration")
    print("=" * 50)
    migrate_database()
    print("\n✓ Migration complete! You can now run: python app.py")
