from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from huggingface_hub import InferenceClient
from intasend import APIService as IntaSendAPIService
import os
import random
import uuid
import requests
import json
import logging
import re
import secrets
from collections import Counter
from dotenv import load_dotenv
from typing import List, Dict, Optional

load_dotenv()   

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure CORS for frontend connection
# CRITICAL: Add CORS configuration
CORS(app, 
     origins=["http://127.0.0.1:5500", "http://localhost:5500", "http://127.0.0.1:3000", "http://localhost:3000"],
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Session configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS

# Add explicit OPTIONS handler for all routes
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization")
        response.headers.add('Access-Control-Allow-Methods', "GET,PUT,POST,DELETE,OPTIONS")
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    'mysql+pymysql://ai_study_user:secure_password_here@localhost:3306/ai_study_buddy'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'pool_size': 10,
    'max_overflow': 20
}

# Initialize extensions
db = SQLAlchemy(app)
CORS(app, supports_credentials=True, origins=['http://localhost:5173', 'http://127.0.0.1:5173'])

# Hugging Face Configuration
HF_API_TOKEN = os.environ.get('HF_API_TOKEN')

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    is_premium = db.Column(db.Boolean, default=False, nullable=False)
    premium_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Profile information
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    timezone = db.Column(db.String(50), default='UTC')
    language = db.Column(db.String(10), default='en')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Study statistics
    study_sessions = db.Column(db.Integer, default=0)
    total_cards = db.Column(db.Integer, default=0)
    total_decks = db.Column(db.Integer, default=0)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    total_study_time = db.Column(db.Integer, default=0)  # in minutes
    
    # Relationships
    decks = db.relationship('Deck', backref='user', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('StudySession', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'is_premium': self.is_premium,
            'premium_expires_at': self.premium_expires_at.isoformat() if self.premium_expires_at else None,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'created_at': self.created_at.isoformat(),
            'study_sessions': self.study_sessions,
            'total_cards': self.total_cards,
            'total_decks': self.total_decks,
            'current_streak': self.current_streak,
            'longest_streak': self.longest_streak
        }

class Deck(db.Model):
    __tablename__ = 'decks'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Deck information
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    subject = db.Column(db.String(100))
    tags = db.Column(db.JSON)  # Array of tags
    
    # Content
    original_notes = db.Column(db.Text, nullable=False)
    notes_hash = db.Column(db.String(64))  # For detecting changes
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_studied = db.Column(db.DateTime)
    
    # Progress tracking
    progress = db.Column(db.Float, default=0.0)  # Percentage completed
    total_cards = db.Column(db.Integer, default=0)
    mastered_cards = db.Column(db.Integer, default=0)
    
    # Study statistics
    total_studies = db.Column(db.Integer, default=0)
    average_accuracy = db.Column(db.Float, default=0.0)
    total_study_time = db.Column(db.Integer, default=0)  # in minutes
    
    # Settings
    is_public = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    
    # Relationships
    cards = db.relationship('Flashcard', backref='deck', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('StudySession', backref='deck', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self, include_cards=False):
        result = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'subject': self.subject,
            'tags': self.tags or [],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_studied': self.last_studied.isoformat() if self.last_studied else None,
            'progress': self.progress,
            'total_cards': self.total_cards,
            'mastered_cards': self.mastered_cards,
            'total_studies': self.total_studies,
            'average_accuracy': self.average_accuracy,
            'is_public': self.is_public,
            'is_archived': self.is_archived
        }
        
        if include_cards:
            result['cards'] = [card.to_dict() for card in self.cards]
        
        return result

class Flashcard(db.Model):
    __tablename__ = 'flashcards'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deck_id = db.Column(db.String(36), db.ForeignKey('decks.id'), nullable=False, index=True)
    
    # Question content
    question = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(50), nullable=False)  # multiple-choice, true-false, short-answer
    options = db.Column(db.JSON)  # For multiple choice questions
    correct_answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text)
    
    # Metadata
    difficulty_level = db.Column(db.String(20), default='medium')  # easy, medium, hard
    topic = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Study tracking
    times_studied = db.Column(db.Integer, default=0)
    times_correct = db.Column(db.Integer, default=0)
    last_studied = db.Column(db.DateTime)
    mastery_level = db.Column(db.Float, default=0.0)  # 0-1 scale
    
    # Spaced repetition
    next_review = db.Column(db.DateTime)
    review_interval = db.Column(db.Integer, default=1)  # days
    ease_factor = db.Column(db.Float, default=2.5)
    
    def to_dict(self):
        return {
            'id': self.id,
            'question': self.question,
            'type': self.question_type,
            'options': self.options or [],
            'correct_answer': self.correct_answer,
            'explanation': self.explanation,
            'difficulty_level': self.difficulty_level,
            'topic': self.topic,
            'times_studied': self.times_studied,
            'times_correct': self.times_correct,
            'accuracy': (self.times_correct / self.times_studied * 100) if self.times_studied > 0 else 0,
            'mastery_level': self.mastery_level,
            'last_studied': self.last_studied.isoformat() if self.last_studied else None,
            'next_review': self.next_review.isoformat() if self.next_review else None
        }

class StudySession(db.Model):
    __tablename__ = 'study_sessions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    deck_id = db.Column(db.String(36), db.ForeignKey('decks.id'), nullable=False, index=True)
    
    # Session timing
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer, default=0)
    
    # Performance metrics
    cards_studied = db.Column(db.Integer, default=0)
    cards_correct = db.Column(db.Integer, default=0)
    accuracy = db.Column(db.Float, default=0.0)
    
    # Session metadata
    session_type = db.Column(db.String(50), default='study')  # study, review, test
    device_type = db.Column(db.String(50))  # mobile, desktop, tablet
    
    def to_dict(self):
        return {
            'id': self.id,
            'deck_id': self.deck_id,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_minutes': self.duration_minutes,
            'cards_studied': self.cards_studied,
            'cards_correct': self.cards_correct,
            'accuracy': self.accuracy,
            'session_type': self.session_type
        }
class EnhancedQuestionGenerator:
    """
    A class to generate questions and perform other NLP tasks using OpenRouter API.
    OpenRouter provides access to multiple AI models with free tier options.
    Designed to work with Flask API that expects proper exception handling.
    """
    def __init__(self, api_token=None):
        self.api_token = api_token or os.getenv('OPENROUTER_API_KEY')
        self.api_available = False
        
        # OpenRouter API configuration
        self.base_url = "https://openrouter.ai/api/v1"
        self.model = "meta-llama/llama-3.2-3b-instruct:free"
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "AI Study Buddy"
        }
        
        logger.info(f"Initializing EnhancedQuestionGenerator with OpenRouter...")
        logger.info(f"Token from env: {'Yes' if os.getenv('OPENROUTER_API_KEY') else 'No'}")
        logger.info(f"Token provided: {'Yes' if api_token else 'No'}")
        logger.info(f"Using model: {self.model}")
        
        if not self.api_token:
            logger.error("No OPENROUTER_API_KEY found. Please set the environment variable.")
            logger.info("You can get a free API key at: https://openrouter.ai/keys")
            return
            
        if len(self.api_token) < 20:
            logger.error("OPENROUTER_API_KEY appears to be too short. Please check your token.")
            return
            
        self.api_available = self._validate_token()
        
    def _validate_token(self) -> bool:
        """Validate the API token by making a simple test request"""
        try:
            test_payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=test_payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("API token validation successful")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API token validation failed: {str(e)}")
            return False

    def generate_questions(self, notes: str, num_questions: int = 5) -> Optional[List[Dict]]:
        """
        Generate study questions from provided notes
        
        Args:
            notes: Text content to generate questions from
            num_questions: Number of questions to generate (default: 5)
            
        Returns:
            List of question dictionaries or None if generation fails
        """
        if not self.api_available:
            logger.error("API not available. Check your API key and initialization.")
            return None

        prompt = f"""Create {num_questions} multiple-choice questions based on these notes.
        Format each question as JSON with:
        - question: the question text
        - options: list of 4 possible answers
        - answer: index of correct answer (0-3)
        
        Notes:
        {notes[:3000]}  # Truncate to avoid token limits
        
        Return only valid JSON array without any additional text."""

        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
                "temperature": 0.7
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            # Clean response and extract JSON
            if content.startswith('```json'):
                content = content.split('```json')[1].split('```')[0]
            elif content.startswith('```'):
                content = content.split('```')[1].split('```')[0]
                
            questions = json.loads(content)
            logger.info(f"Successfully generated {len(questions)} questions")
            return questions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response as JSON: {str(e)}")
            logger.debug(f"Raw response: {content}")
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
        except KeyError as e:
            logger.error(f"Unexpected response format: {str(e)}")
            logger.debug(f"Full response: {result}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            
        return None

    def create_deck(self, notes: str, deck_name: str, num_questions: int = 5) -> Optional[Dict]:
        """Create a full study deck with metadata and questions"""
        questions = self.generate_questions(notes, num_questions)
        
        if not questions:
            return None
            
        return {
            "deck_name": deck_name,
            "created_at": datetime.datetime.now().isoformat(),
            "questions": questions,
            "statistics": {
                "total_questions": len(questions),
                "estimated_study_time": f"{len(questions) * 2} minutes"
            }
        }

# Initialize question generator
question_generator = EnhancedQuestionGenerator()


# API Routes
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'database': 'connected' if db.engine else 'disconnected'
    })

@app.route('/api/users', methods=['POST'])
def create_user():
    """Create a new user (temporary or registered)"""
    try:
        data = request.get_json() or {}
        
        # Create user
        user = User()
        
        if data.get('email'):
            # Check if user already exists
            existing_user = User.query.filter_by(email=data['email']).first()
            if existing_user:
                return jsonify({'error': 'User already exists'}), 400
            
            user.email = data['email']
            if data.get('password'):
                user.password_hash = generate_password_hash(data['password'])
        
        if data.get('first_name'):
            user.first_name = data['first_name']
        if data.get('last_name'):
            user.last_name = data['last_name']
        
        db.session.add(user)
        db.session.commit()
        
        # Store user ID in session
        session['user_id'] = user.id
        
        return jsonify({
            'user_id': user.id,
            'is_premium': user.is_premium,
            'created_at': user.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create user'}), 500

@app.route('/api/generate-flashcards', methods=['POST'])
def generate_flashcards():
    """Generate flashcards from study notes"""
    try:
        data = request.get_json()
        notes = data.get('notes', '').strip()
        
        # Validation
        if not notes:
            return jsonify({'error': 'Notes are required'}), 400
        
        if len(notes) < 100:
            return jsonify({'error': 'Notes must be at least 100 characters'}), 400
        
        if len(notes) > 5000:
            return jsonify({'error': 'Notes must be less than 5000 characters'}), 400
        
        # Get or create user
        user_id = session.get('user_id')
        if not user_id:
            # Create temporary user
            user = User()
            db.session.add(user)
            db.session.commit()
            session['user_id'] = user.id
            user_id = user.id
        
        user = User.query.get(user_id)
        
        # Check premium limits
        if not user.is_premium:
            monthly_decks = Deck.query.filter(
                Deck.user_id == user_id,
                Deck.created_at >= datetime.utcnow() - timedelta(days=30)
            ).count()
            
            if monthly_decks >= 5:
                return jsonify({
                    'error': 'Free tier limit reached. Upgrade to premium for unlimited decks.',
                    'requires_premium': True
                }), 403
        
        # Generate questions using AI
        questions = question_generator.generate_questions(notes)
        
        # Create deck
        deck_title = notes[:50] + ('...' if len(notes) > 50 else '')
        deck = Deck(
            user_id=user_id,
            title=deck_title,
            original_notes=notes,
            total_cards=len(questions)
        )
        
        db.session.add(deck)
        db.session.flush()  # Get deck ID
        
        # Create flashcards
        flashcards = []
        for question_data in questions:
            card = Flashcard(
                deck_id=deck.id,
                question=question_data['question'],
                question_type=question_data['type'],
                options=question_data.get('options', []),
                correct_answer=question_data['correct_answer'],
                explanation=question_data.get('explanation', ''),
                difficulty_level=question_data.get('difficulty_level', 'medium'),
                topic=question_data.get('topic', 'general')
            )
            db.session.add(card)
            flashcards.append(card)
        
        # Update user stats
        user.total_decks += 1
        user.total_cards += len(questions)
        user.last_activity = datetime.utcnow()
        
        db.session.commit()
        
        # Return deck data in format expected by frontend
        return jsonify({
            'deck_id': deck.id,
            'title': deck.title,
            'cards': [{
                'id': card.id,
                'question': card.question,
                'type': card.question_type,
                'options': card.options or [],
                'correctAnswer': card.options.index(card.correct_answer) if card.options and card.correct_answer in card.options else 0,
                'explanation': card.explanation
            } for card in flashcards],
            'created': deck.created_at.isoformat(),
            'lastStudied': None,
            'progress': 0
        })
        
    except Exception as e:
        logger.error(f"Error generating flashcards: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to generate flashcards'}), 500

@app.route('/api/decks', methods=['GET'])
def get_user_decks():
    """Get all decks for the current user"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'decks': []})
        
        decks = Deck.query.filter_by(user_id=user_id, is_archived=False).order_by(Deck.created_at.desc()).all()
        
        return jsonify({
            'decks': [{
                'id': deck.id,
                'title': deck.title,
                'cards': [card.to_dict() for card in deck.cards],
                'created': deck.created_at.isoformat(),
                'lastStudied': deck.last_studied.isoformat() if deck.last_studied else None,
                'progress': deck.progress
            } for deck in decks]
        })
        
    except Exception as e:
        logger.error(f"Error fetching decks: {str(e)}")
        return jsonify({'error': 'Failed to fetch decks'}), 500

@app.route('/api/decks/<deck_id>', methods=['GET'])
def get_deck(deck_id):
    """Get a specific deck with all its cards"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        deck = Deck.query.filter_by(id=deck_id, user_id=user_id).first()
        if not deck:
            return jsonify({'error': 'Deck not found'}), 404
        
        return jsonify(deck.to_dict(include_cards=True))
        
    except Exception as e:
        logger.error(f"Error fetching deck: {str(e)}")
        return jsonify({'error': 'Failed to fetch deck'}), 500

@app.route('/api/decks/<deck_id>', methods=['PUT'])
def update_deck(deck_id):
    """Update deck information"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        deck = Deck.query.filter_by(id=deck_id, user_id=user_id).first()
        if not deck:
            return jsonify({'error': 'Deck not found'}), 404
        
        data = request.get_json()
        
        if 'title' in data:
            deck.title = data['title']
        if 'description' in data:
            deck.description = data['description']
        if 'progress' in data:
            deck.progress = data['progress']
        if 'last_studied' in data:
            deck.last_studied = datetime.utcnow()
        
        deck.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Deck updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating deck: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update deck'}), 500

@app.route('/api/study-session', methods=['POST'])
def start_study_session():
    """Start a new study session"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        deck_id = data.get('deck_id')
        
        if not deck_id:
            return jsonify({'error': 'Deck ID required'}), 400
        
        # Verify deck ownership
        deck = Deck.query.filter_by(id=deck_id, user_id=user_id).first()
        if not deck:
            return jsonify({'error': 'Deck not found'}), 404
        
        # Create study session
        study_session = StudySession(
            user_id=user_id,
            deck_id=deck_id,
            device_type=data.get('device_type', 'unknown')
        )
        
        db.session.add(study_session)
        db.session.commit()
        
        return jsonify({
            'session_id': study_session.id,
            'started_at': study_session.started_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error starting study session: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to start study session'}), 500

@app.route('/api/study-session/<session_id>/complete', methods=['POST'])
def complete_study_session(session_id):
    """Complete a study session with results"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        
        study_session = StudySession.query.filter_by(
            id=session_id, 
            user_id=user_id
        ).first()
        
        if not study_session:
            return jsonify({'error': 'Study session not found'}), 404
        
        # Update session data
        study_session.completed_at = datetime.utcnow()
        study_session.cards_studied = data.get('cards_studied', 0)
        study_session.cards_correct = data.get('cards_correct', 0)
        study_session.accuracy = data.get('accuracy', 0.0)
        
        # Calculate duration
        duration = study_session.completed_at - study_session.started_at
        study_session.duration_minutes = int(duration.total_seconds() / 60)
        
        # Update user stats
        user = User.query.get(user_id)
        user.study_sessions += 1
        user.last_activity = datetime.utcnow()
        user.total_study_time += study_session.duration_minutes
        
        # Update deck
        deck = Deck.query.get(study_session.deck_id)
        deck.last_studied = datetime.utcnow()
        deck.progress = data.get('deck_progress', deck.progress)
        deck.total_studies += 1
        
        db.session.commit()
        
        return jsonify({
            'message': 'Study session completed',
            'duration_minutes': study_session.duration_minutes,
            'accuracy': study_session.accuracy
        })
        
    except Exception as e:
        logger.error(f"Error completing study session: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to complete study session'}), 500

@app.route('/api/cards/<card_id>/study', methods=['POST'])
def record_card_study(card_id):
    """Record study attempt for a specific card"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        is_correct = data.get('is_correct', False)
        difficulty = data.get('difficulty', 'medium')
        
        card = Flashcard.query.get(card_id)
        if not card:
            return jsonify({'error': 'Card not found'}), 404
        
        # Verify user owns this card's deck
        deck = Deck.query.filter_by(id=card.deck_id, user_id=user_id).first()
        if not deck:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update card statistics
        card.times_studied += 1
        if is_correct:
            card.times_correct += 1
        card.last_studied = datetime.utcnow()
        card.difficulty_level = difficulty
        
        # Update mastery level
        accuracy = card.times_correct / card.times_studied if card.times_studied > 0 else 0
        card.mastery_level = min(1.0, accuracy * (card.times_studied / 5))  # Gradual mastery
        
        db.session.commit()
        
        return jsonify({
            'times_studied': card.times_studied,
            'times_correct': card.times_correct,
            'accuracy': accuracy * 100,
            'mastery_level': card.mastery_level
        })
        
    except Exception as e:
        logger.error(f"Error recording card study: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to record study attempt'}), 500

@app.route('/api/user/stats', methods=['GET'])
def get_user_stats():
    """Get user statistics and progress"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Calculate additional stats
        recent_sessions = StudySession.query.filter(
            StudySession.user_id == user_id,
            StudySession.completed_at >= datetime.utcnow() - timedelta(days=7)
        ).all()
        
        weekly_accuracy = 0
        if recent_sessions:
            total_accuracy = sum(session.accuracy for session in recent_sessions)
            weekly_accuracy = total_accuracy / len(recent_sessions)
        
        return jsonify({
            'user_id': user.id,
            'is_premium': user.is_premium,
            'study_sessions': user.study_sessions,
            'total_cards': user.total_cards,
            'total_decks': user.total_decks,
            'current_streak': user.current_streak,
            'longest_streak': user.longest_streak,
            'total_study_time': user.total_study_time,
            'weekly_accuracy': round(weekly_accuracy, 1),
            'created_at': user.created_at.isoformat(),
            'last_activity': user.last_activity.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error fetching user stats: {str(e)}")
        return jsonify({'error': 'Failed to fetch user stats'}), 500

@app.route('/api/premium/upgrade', methods=['POST'])
def upgrade_to_premium():
    """Handle premium upgrade with Paystack integration"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        subscription_type = data.get('subscription_type', 'monthly')
        email = data.get('email')
        
        # Get user details
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate Paystack configuration
        secret_key = os.getenv('PAYSTACK_SECRET_KEY')
        if not secret_key:
            logger.error("Missing Paystack secret key")
            return jsonify({'error': 'Payment service configuration error'}), 500
        
        # Set subscription amount (in kobo - Paystack uses kobo for NGN)
        # Adjust these amounts as needed for your pricing
        amount_kes = 29900 if subscription_type == 'monthly' else 299900  # KES in cents (299 KES = 29900 cents)
        
        # Use provided email or user's email or generate one
        customer_email = email or getattr(user, 'email', None) or f"user{user_id}@example.com"
        
        # Generate unique reference
        reference = f"premium_{user_id}_{int(datetime.utcnow().timestamp())}_{secrets.token_hex(4)}"
        
        # Prepare Paystack payment initialization
        paystack_url = "https://api.paystack.co/transaction/initialize"
        headers = {
            'Authorization': f'Bearer {secret_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'email': customer_email,
            'amount': amount_kes,
            'reference': reference,
            'currency': 'KES',
            'callback_url': f"{request.host_url}api/payment/callback",
            'metadata': {
                'user_id': user_id,
                'subscription_type': subscription_type,
                'custom_fields': [
                    {
                        'display_name': 'Premium Subscription',
                        'variable_name': 'subscription_type',
                        'value': subscription_type
                    }
                ]
            }
        }
        
        logger.info(f"Initializing Paystack payment - User: {user_id}, Amount: {amount_kes/100} KES")
        
        # Make request to Paystack
        response = requests.post(paystack_url, json=payload, headers=headers)
        response_data = response.json()
        
        logger.info(f"Paystack response status: {response.status_code}")
        logger.info(f"Paystack response: {response_data}")
        
        if response.status_code == 200 and response_data.get('status'):
            # Payment initialization successful
            payment_data = response_data['data']
            
            # Optionally store payment record in database
            # You might want to create a Payment model for this
            
            return jsonify({
                'payment_url': payment_data['authorization_url'],
                'reference': payment_data['reference'],
                'access_code': payment_data['access_code'],
                'message': 'Payment initialized successfully'
            })
        else:
            logger.error(f"Paystack initialization failed: {response_data}")
            return jsonify({
                'error': 'Payment initialization failed',
                'details': response_data.get('message', 'Unknown error')
            }), 400
            
    except Exception as e:
        logger.error(f"Error upgrading to premium: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to process payment'}), 500


@app.route('/api/payment/callback', methods=['GET', 'POST'])
def payment_callback():
    """Handle payment callback from Paystack"""
    try:
        # Get reference from query parameters
        reference = request.args.get('reference')
        
        if not reference:
            logger.error("No reference provided in callback")
            return redirect(f"{request.host_url}payment/failed")
        
        # Verify payment with Paystack
        verification_result = verify_payment(reference)
        
        if verification_result['success']:
            # Payment successful - upgrade user to premium
            user_id = verification_result['user_id']
            subscription_type = verification_result['subscription_type']
            
            # Update user's premium status
            user = User.query.get(user_id)
            if user:
                # Add premium fields to your User model
                user.is_premium = True
                user.premium_type = subscription_type
                user.premium_start_date = datetime.utcnow()
                
                # Calculate expiry date
                if subscription_type == 'monthly':
                    from dateutil.relativedelta import relativedelta
                    user.premium_expiry_date = datetime.utcnow() + relativedelta(months=1)
                else:
                    user.premium_expiry_date = datetime.utcnow() + relativedelta(years=1)
                
                db.session.commit()
                logger.info(f"User {user_id} upgraded to premium ({subscription_type})")
            
            return redirect(f"{request.host_url}payment/success")
        else:
            logger.error(f"Payment verification failed: {verification_result['error']}")
            return redirect(f"{request.host_url}payment/failed")
            
    except Exception as e:
        logger.error(f"Error in payment callback: {str(e)}")
        return redirect(f"{request.host_url}payment/failed")


@app.route('/api/payment/verify', methods=['POST'])
def verify_payment_endpoint():
    """Manual payment verification endpoint"""
    try:
        data = request.get_json()
        reference = data.get('reference')
        
        if not reference:
            return jsonify({'error': 'Payment reference required'}), 400
        
        result = verify_payment(reference)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': 'Payment verified successfully',
                'data': result
            })
        else:
            return jsonify({
                'status': 'failed', 
                'message': result['error']
            }), 400
            
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        return jsonify({'error': 'Payment verification failed'}), 500


def verify_payment(reference):
    """Verify payment with Paystack"""
    try:
        secret_key = os.getenv('PAYSTACK_SECRET_KEY')
        
        # Verify payment with Paystack
        verify_url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            'Authorization': f'Bearer {secret_key}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(verify_url, headers=headers)
        response_data = response.json()
        
        logger.info(f"Payment verification response: {response_data}")
        
        if response.status_code == 200 and response_data.get('status'):
            transaction_data = response_data['data']
            
            # Check if payment was successful
            if transaction_data['status'] == 'success':
                # Extract metadata
                metadata = transaction_data.get('metadata', {})
                user_id = metadata.get('user_id')
                subscription_type = metadata.get('subscription_type', 'monthly')
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'subscription_type': subscription_type,
                    'amount': transaction_data['amount'],
                    'reference': reference,
                    'transaction_data': transaction_data
                }
            else:
                return {
                    'success': False,
                    'error': f"Payment status: {transaction_data['status']}"
                }
        else:
            return {
                'success': False,
                'error': response_data.get('message', 'Verification failed')
            }
            
    except Exception as e:
        logger.error(f"Payment verification error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@app.route('/api/test-paystack', methods=['GET'])
def test_paystack():
    """Test Paystack configuration"""
    try:
        secret_key = os.getenv('PAYSTACK_SECRET_KEY')
        
        if not secret_key:
            return jsonify({'error': 'PAYSTACK_SECRET_KEY not configured'}), 500
        
        # Test API connection
        test_url = "https://api.paystack.co/bank"
        headers = {
            'Authorization': f'Bearer {secret_key}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(test_url, headers=headers)
        
        if response.status_code == 200:
            return jsonify({
                'status': 'Paystack configured successfully',
                'secret_key_prefix': secret_key[:10] + '...'
            })
        else:
            return jsonify({
                'error': 'Paystack API test failed',
                'status_code': response.status_code
            }), 500
            
    except Exception as e:
        logger.error(f"Paystack test failed: {str(e)}")
        return jsonify({'error': f'Paystack configuration error: {str(e)}'}), 500


# Add these routes for payment result pages
@app.route('/payment/success')
def payment_success():
    """Payment success page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Successful</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .success { color: green; font-size: 24px; margin-bottom: 20px; }
            .button { background: #007cba; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="success">✅ Payment Successful!</div>
        <p>Your premium subscription has been activated.</p>
        <a href="/" class="button">Return to App</a>
        <script>
            // Redirect back to app after 3 seconds
            setTimeout(() => {
                window.location.href = '/';
            }, 3000);
        </script>
    </body>
    </html>
    """

@app.route('/payment/failed')
def payment_failed():
    """Payment failed page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Failed</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .failed { color: red; font-size: 24px; margin-bottom: 20px; }
            .button { background: #007cba; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="failed">❌ Payment Failed</div>
        <p>There was an issue processing your payment. Please try again.</p>
        <a href="/" class="button">Return to App</a>
    </body>
    </html>
    """
# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# Database initialization
def create_tables():
    """Create database tables"""
    try:
        with app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    create_tables()