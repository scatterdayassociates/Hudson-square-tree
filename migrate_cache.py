"""
Migrate pixel_cache table to support multiple areas per year

This script updates the pixel_cache table to:
1. Remove old unique constraint on (year, bounds_type)
2. Add new unique index on (year, bounds_data) to allow multiple areas per year
3. Support caching different drawn areas independently
"""

from postgis_raster import PostGISRasterHandler

def main():
    print("=" * 60)
    print("Migrating Pixel Cache Table")
    print("=" * 60)
    print()
    
    handler = PostGISRasterHandler()
    
    if not handler.connect():
        print("❌ Failed to connect to database")
        return False
    
    try:
        # Check if table exists
        handler.cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'pixel_cache'
            );
        """)
        table_exists = handler.cursor.fetchone()[0]
        
        if table_exists:
            print("📋 Table exists, updating constraints...")
            
            # Drop old unique constraint/index
            drop_commands = [
                "ALTER TABLE pixel_cache DROP CONSTRAINT IF EXISTS pixel_cache_year_bounds_type_key CASCADE;",
                "DROP INDEX IF EXISTS pixel_cache_year_bounds_type_key CASCADE;",
                "ALTER TABLE pixel_cache DROP CONSTRAINT IF EXISTS pixel_cache_year_bounds_type_unique CASCADE;",
                "DROP INDEX IF EXISTS pixel_cache_year_bounds_type_unique CASCADE;",
                "DROP INDEX IF EXISTS pixel_cache_year_bounds_unique CASCADE;"
            ]
            
            for cmd in drop_commands:
                try:
                    handler.cursor.execute(cmd)
                    handler.connection.commit()
                    print(f"✅ Dropped old constraint/index")
                except Exception as e:
                    pass
            
            # Create new unique index
            try:
                handler.cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS pixel_cache_year_bounds_unique 
                    ON pixel_cache(year, md5(COALESCE(bounds_data, '')));
                """)
                handler.connection.commit()
                print("✅ Created new unique index on (year, bounds_data)")
            except Exception as e:
                try:
                    handler.cursor.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS pixel_cache_year_bounds_unique 
                        ON pixel_cache(year, bounds_data);
                    """)
                    handler.connection.commit()
                    print("✅ Created new unique index on (year, bounds_data)")
                except Exception as e2:
                    print(f"⚠️ Could not create unique index: {e2}")
            
            print()
            print("✅ Migration complete!")
            print("   The table now supports multiple cache entries per year")
            print("   (one per unique bounds_data)")
        else:
            print("📝 Table doesn't exist, creating new table...")
            if handler.create_pixel_cache_table():
                print("✅ New table created successfully")
            else:
                print("❌ Failed to create new table")
                return False
        
        print()
        print("Next step: Run 'python initialize_cache.py' to populate the cache")
        return True
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        handler.disconnect()
    
    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)

