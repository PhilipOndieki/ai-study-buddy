#!/usr/bin/env python3
"""
AI Study Buddy Flask Application Runner
"""

import os
from app import app, db
from config import config

def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app.config.from_object(config[config_name])
    
    # Initialize database
    with app.app_context():
        try:
            db.create_all()
            print(f"✅ Database tables created successfully")
            print(f"🚀 AI Study Buddy backend running in {config_name} mode")
        except Exception as e:
            print(f"❌ Database initialization failed: {str(e)}")
            print("💡 Make sure MySQL is running and credentials are correct")
    
    return app

if __name__ == '__main__':
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Create and run app
    application = create_app()
    
    # Development server settings
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"🌐 Server starting on http://{host}:{port}")
    print(f"📊 Debug mode: {debug}")
    print(f"🗄️  Database: {application.config['SQLALCHEMY_DATABASE_URI']}")
    
    application.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )