#!/usr/bin/env python3
"""
Test MySQL connection before running the main application
"""
import os
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

def test_mysql_connection():
    """Test MySQL connection with your credentials"""
    
    # Your database credentials from the setup script
    config = {
        'host': 'localhost',
        'user': 'ai_study_user',
        'password': 'secure_password_here',  # Replace with actual password
        'database': 'ai_study_buddy',
        'charset': 'utf8mb4'
    }
    
    print("🔍 Testing MySQL connection...")
    print(f"   Host: {config['host']}")
    print(f"   User: {config['user']}")
    print(f"   Database: {config['database']}")
    print("")
    
    # Test 1: Raw PyMySQL connection
    try:
        connection = pymysql.connect(**config)
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"✅ Raw PyMySQL connection successful")
            print(f"   MySQL version: {version[0]}")
        connection.close()
    except Exception as e:
        print(f"❌ Raw PyMySQL connection failed: {e}")
        return False
    
    # Test 2: SQLAlchemy connection
    try:
        database_url = f"mysql+pymysql://{config['user']}:{config['password']}@{config['host']}/{config['database']}"
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ SQLAlchemy connection successful")
            
        # Test table creation
        with engine.connect() as conn:
            result = conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result]
            print(f"   Existing tables: {tables if tables else 'None (will be created by Flask)'}")
            
    except OperationalError as e:
        print(f"❌ SQLAlchemy connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    print("")
    print("🎉 All connection tests passed!")
    print("")
    print("📝 Use these settings in your .env file:")
    print(f"DATABASE_URL={database_url}")
    
    return True

def check_mysql_service():
    """Check if MySQL service is running"""
    import subprocess
    
    try:
        result = subprocess.run(['systemctl', 'is-active', 'mysql'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ MySQL service is running")
            return True
        else:
            print("❌ MySQL service is not running")
            print("💡 Run: sudo systemctl start mysql")
            return False
    except FileNotFoundError:
        print("⚠️  systemctl not found, cannot check MySQL service status")
        return True  # Assume it's running

if __name__ == '__main__':
    print("🔧 AI Study Buddy - MySQL Connection Test")
    print("=" * 50)
    
    # Check if MySQL service is running
    if not check_mysql_service():
        exit(1)
    
    # Test connection
    if test_mysql_connection():
        print("✅ Ready to run your Flask application!")
    else:
        print("❌ Fix the connection issues before running your app")
        exit(1)