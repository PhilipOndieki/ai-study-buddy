import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20
    }
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # AI Configuration
    HUGGING_FACE_API_TOKEN = os.environ.get('HF_API_TOKEN')
    MAX_QUESTIONS_PER_DECK = 10
    MIN_NOTE_LENGTH = 100
    MAX_NOTE_LENGTH = 5000
    
    # Premium limits
    FREE_TIER_MONTHLY_DECKS = 5
    PREMIUM_TIER_MONTHLY_DECKS = -1  # Unlimited
    
    # IntaSend Configuration
    INTASEND_PUBLIC_KEY = os.environ.get('INTASEND_PUBLIC_KEY')
    INTASEND_SECRET_KEY = os.environ.get('INTASEND_SECRET_KEY')
    INTASEND_WEBHOOK_SECRET = os.environ.get('INTASEND_WEBHOOK_SECRET')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:password@localhost/ai_study_buddy_dev'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SESSION_COOKIE_SECURE = True

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}