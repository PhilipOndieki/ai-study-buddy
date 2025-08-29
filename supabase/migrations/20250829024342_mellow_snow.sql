-- AI Study Buddy Database Setup Script
-- Run this script to create the database and initial structure

-- Create database (run this as root user)
CREATE DATABASE IF NOT EXISTS ai_study_buddy 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

-- Create application user (recommended for security)
CREATE USER IF NOT EXISTS 'ai_study_user'@'localhost' IDENTIFIED BY 'secure_password_here';
GRANT ALL PRIVILEGES ON ai_study_buddy.* TO 'ai_study_user'@'localhost';
GRANT ALL PRIVILEGES ON ai_study_buddy_dev.* TO 'ai_study_user'@'localhost';
FLUSH PRIVILEGES;

-- Use the database
USE ai_study_buddy;

-- Enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

-- Create indexes for better performance
-- These will be created automatically by SQLAlchemy, but listed here for reference

-- Users table indexes
-- INDEX idx_users_email ON users(email)
-- INDEX idx_users_created_at ON users(created_at)
-- INDEX idx_users_last_activity ON users(last_activity)

-- Decks table indexes  
-- INDEX idx_decks_user_id ON decks(user_id)
-- INDEX idx_decks_created_at ON decks(created_at)
-- INDEX idx_decks_last_studied ON decks(last_studied)

-- Flashcards table indexes
-- INDEX idx_flashcards_deck_id ON flashcards(deck_id)
-- INDEX idx_flashcards_last_studied ON flashcards(last_studied)
-- INDEX idx_flashcards_next_review ON flashcards(next_review)

-- Study sessions table indexes
-- INDEX idx_study_sessions_user_id ON study_sessions(user_id)
-- INDEX idx_study_sessions_deck_id ON study_sessions(deck_id)
-- INDEX idx_study_sessions_started_at ON study_sessions(started_at)

-- Sample data for testing (optional)
-- INSERT INTO users (id, email, is_premium, created_at) 
-- VALUES ('test-user-1', 'test@example.com', false, NOW());

SHOW TABLES;
SELECT 'Database setup completed successfully!' as status;