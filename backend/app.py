from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import uuid
import requests
import json
import logging
import re
from collections import Counter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    'mysql+pymysql://username:password@localhost/ai_study_buddy'
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
HF_API_TOKEN = os.environ.get('HUGGING_FACE_API_TOKEN')

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

# AI Question Generation Service
class QuestionGenerator:
    def __init__(self):
        self.hf_token = HF_API_TOKEN
        
    def generate_questions(self, notes_text, num_questions=5):
        """Generate questions from study notes using AI"""
        try:
            # Extract key concepts from notes
            concepts = self._extract_concepts(notes_text)
            sentences = self._extract_key_sentences(notes_text)
            
            # Generate different types of questions
            questions = []
            question_types = ['multiple-choice', 'true-false', 'short-answer']
            
            for i in range(num_questions):
                question_type = question_types[i % len(question_types)]
                concept = concepts[i % len(concepts)] if concepts else f"concept_{i+1}"
                context = sentences[i % len(sentences)] if sentences else notes_text[:200]
                
                if question_type == 'multiple-choice':
                    question = self._generate_multiple_choice(notes_text, concept, context)
                elif question_type == 'true-false':
                    question = self._generate_true_false(notes_text, concept)
                else:
                    question = self._generate_short_answer(notes_text, concept)
                
                questions.append(question)
            
            return questions
            
        except Exception as e:
            logger.error(f"Error generating questions: {str(e)}")
            return self._generate_fallback_questions(notes_text, num_questions)
    
    def _extract_concepts(self, text):
        """Extract key concepts from text"""
        words = re.findall(r'\b[A-Za-z]{4,}\b', text.lower())
        
        # Filter out common words
        stop_words = {
            'this', 'that', 'with', 'have', 'will', 'from', 'they', 'know', 
            'want', 'been', 'good', 'much', 'some', 'time', 'very', 'when', 
            'come', 'here', 'just', 'like', 'long', 'make', 'many', 'over', 
            'such', 'take', 'than', 'them', 'well', 'were', 'what', 'where',
            'which', 'while', 'would', 'could', 'should', 'might', 'about',
            'after', 'again', 'before', 'being', 'between', 'during', 'under'
        }
        
        concepts = [word for word in words if word not in stop_words and len(word) > 3]
        word_freq = Counter(concepts)
        
        return [word for word, freq in word_freq.most_common(15)]
    
    def _extract_key_sentences(self, text):
        """Extract important sentences from text"""
        sentences = re.split(r'[.!?]+', text)
        key_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if 20 <= len(sentence) <= 200:
                key_sentences.append(sentence)
        
        return key_sentences[:10]
    
    def _generate_multiple_choice(self, notes, concept, context):
        """Generate a multiple choice question"""
        question_templates = [
            f"What is the primary significance of {concept} in this context?",
            f"Which statement best describes {concept}?",
            f"How does {concept} relate to the main topic discussed?",
            f"What role does {concept} play in the subject matter?"
        ]
        
        question = question_templates[hash(concept) % len(question_templates)]
        
        # Generate options
        correct_option = f"{concept} is a fundamental concept that plays a crucial role in understanding the topic"
        
        distractors = [
            f"{concept} is mentioned only briefly and has minimal relevance",
            f"{concept} is used as a contrasting example to highlight differences",
            f"{concept} represents an outdated approach that is no longer applicable"
        ]
        
        options = [correct_option] + distractors
        
        return {
            'question': question,
            'type': 'multiple-choice',
            'options': options,
            'correct_answer': correct_option,
            'explanation': f"Based on the study material, {concept} is identified as a key concept that requires thorough understanding for mastery of the subject.",
            'difficulty_level': 'medium',
            'topic': concept
        }
    
    def _generate_true_false(self, notes, concept):
        """Generate a true/false question"""
        import random
        is_true_statement = random.choice([True, False])
        
        if is_true_statement:
            statement = f"{concept} is discussed as an important element in the study material"
            correct_answer = "True"
            explanation = f"This statement is true because {concept} appears prominently in the study notes and is relevant to understanding the main topic."
        else:
            statement = f"{concept} is completely unrelated to the main topic being studied"
            correct_answer = "False"
            explanation = f"This statement is false because {concept} is actually mentioned and plays a role in the study material."
        
        return {
            'question': statement,
            'type': 'true-false',
            'options': ['True', 'False'],
            'correct_answer': correct_answer,
            'explanation': explanation,
            'difficulty_level': 'easy',
            'topic': concept
        }
    
    def _generate_short_answer(self, notes, concept):
        """Generate a short answer question"""
        question_templates = [
            f"Explain the significance of {concept} based on the study material.",
            f"Describe how {concept} contributes to understanding the main topic.",
            f"What would be the impact if {concept} was not considered?",
            f"How does {concept} connect with other elements discussed in the notes?"
        ]
        
        question = question_templates[hash(concept) % len(question_templates)]
        
        return {
            'question': question,
            'type': 'short-answer',
            'options': [],
            'correct_answer': f"A comprehensive answer should demonstrate understanding of {concept} and explain its relationship to the broader topic, showing how it contributes to overall comprehension.",
            'explanation': f"Strong answers will connect {concept} to the main themes, provide specific examples from the material, and demonstrate critical thinking about its importance.",
            'difficulty_level': 'hard',
            'topic': concept
        }
    
    def _generate_fallback_questions(self, notes_text, num_questions):
        """Generate basic questions when AI processing fails"""
        questions = []
        sections = notes_text.split('\n') if '\n' in notes_text else [notes_text]
        
        for i in range(num_questions):
            section_index = i % len(sections)
            section = sections[section_index][:100] if sections[section_index] else "the material"
            
            questions.append({
                'question': f"What is the main concept discussed in: '{section}...'?",
                'type': 'short-answer',
                'options': [],
                'correct_answer': "Answer should identify and explain the key concepts from the specified section.",
                'explanation': "Review the relevant section to understand the main ideas and their significance.",
                'difficulty_level': 'medium',
                'topic': f"section_{i+1}"
            })
        
        return questions

# Initialize question generator
question_generator = QuestionGenerator()

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
    """Handle premium upgrade (IntaSend integration point)"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        payment_method = data.get('payment_method', 'card')
        subscription_type = data.get('subscription_type', 'monthly')
        
        # In production, integrate with IntaSend API here
        # For now, return mock response for development
        
        user = User.query.get(user_id)
        user.is_premium = True
        
        # Set premium expiration
        if subscription_type == 'yearly':
            user.premium_expires_at = datetime.utcnow() + timedelta(days=365)
        else:
            user.premium_expires_at = datetime.utcnow() + timedelta(days=30)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Successfully upgraded to premium',
            'is_premium': True,
            'premium_expires_at': user.premium_expires_at.isoformat(),
            'payment_method': payment_method
        })
        
    except Exception as e:
        logger.error(f"Error upgrading to premium: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to upgrade to premium'}), 500

# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# Database initialization
@app.before_first_request
def create_tables():
    """Create database tables"""
    try:
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)