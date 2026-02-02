"""
Quick fix script to remove old constraint and add new one

Run this once to fix the database constraint issue:
    python fix_cache_constraint.py
"""

from postgis_raster import PostGISRasterHandler
import sys

def main():
    print("=" * 60)
    print("Fixing Pixel Cache Table Constraint")
    print("=" * 60)
    print()
    
    handler = PostGISRasterHandler()
    
    if not handler.connect():
        print("❌ Failed to connect to database")
        return False
    
    try:
        # Drop old unique constraint/index
        print("🗑️  Removing old constraint...")
        drop_commands = [
            "ALTER TABLE pixel_cache DROP CONSTRAINT IF EXISTS pixel_cache_year_bounds_type_key CASCADE;",
            "DROP INDEX IF EXISTS pixel_cache_year_bounds_type_key CASCADE;",
            "ALTER TABLE pixel_cache DROP CONSTRAINT IF EXISTS pixel_cache_year_bounds_type_unique CASCADE;",
            "DROP INDEX IF EXISTS pixel_cache_year_bounds_type_unique CASCADE;",
            "DROP INDEX IF EXISTS pixel_cache_year_bounds_unique CASCADE;"
        ]
        
        dropped = False
        for cmd in drop_commands:
            try:
                handler.cursor.execute(cmd)
                handler.connection.commit()
                print(f"✅ Executed: {cmd.split()[0]} {cmd.split()[1]}")
                dropped = True
            except Exception as e:
                pass
        
        if not dropped:
            print("ℹ️  No old constraints found (this is OK)")
        
        # Create new unique index
        print()
        print("📝 Creating new unique index on (year, bounds_data)...")
        try:
            handler.cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS pixel_cache_year_bounds_unique 
                ON pixel_cache(year, md5(COALESCE(bounds_data, '')));
            """)
            handler.connection.commit()
            print("✅ Created unique index using md5 hash")
        except Exception as e:
            try:
                handler.cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS pixel_cache_year_bounds_unique 
                    ON pixel_cache(year, bounds_data);
                """)
                handler.connection.commit()
                print("✅ Created unique index on bounds_data")
            except Exception as e2:
                print(f"❌ Failed to create index: {e2}")
                return False
        
        print()
        print("=" * 60)
        print("✅ Migration complete!")
        print("=" * 60)
        print()
        print("The table now supports multiple cache entries per year.")
        print("Each unique bounds_data will be cached separately.")
        print()
        return True
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        handler.disconnect()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)



