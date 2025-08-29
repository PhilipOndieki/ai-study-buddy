from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import uuid
import requests
import json
from transformers import pipeline
import logging

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
    'pool_pre_ping': True
}

# Initialize extensions
db = SQLAlchemy(app)
CORS(app, supports_credentials=True)

# Hugging Face Configuration
HF_API_TOKEN = os.environ.get('HUGGING_FACE_API_TOKEN')
HF_API_URL = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    is_premium = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    study_sessions = db.Column(db.Integer, default=0)
    total_cards = db.Column(db.Integer, default=0)
    total_decks = db.Column(db.Integer, default=0)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    
    # Relationships
    decks = db.relationship('Deck', backref='user', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('StudySession', backref='user', lazy=True, cascade='all, delete-orphan')

class Deck(db.Model):
    __tablename__ = 'decks'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    original_notes = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_studied = db.Column(db.DateTime)
    progress = db.Column(db.Float, default=0.0)
    total_cards = db.Column(db.Integer, default=0)
    
    # Relationships
    cards = db.relationship('Flashcard', backref='deck', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('StudySession', backref='deck', lazy=True, cascade='all, delete-orphan')

class Flashcard(db.Model):
    __tablename__ = 'flashcards'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deck_id = db.Column(db.String(36), db.ForeignKey('decks.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(50), nullable=False)  # multiple-choice, true-false, short-answer
    options = db.Column(db.JSON)  # For multiple choice questions
    correct_answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text)
    difficulty_level = db.Column(db.String(20))  # easy, medium, hard
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Study tracking
    times_studied = db.Column(db.Integer, default=0)
    times_correct = db.Column(db.Integer, default=0)
    last_studied = db.Column(db.DateTime)

class StudySession(db.Model):
    __tablename__ = 'study_sessions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    deck_id = db.Column(db.String(36), db.ForeignKey('decks.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    cards_studied = db.Column(db.Integer, default=0)
    cards_correct = db.Column(db.Integer, default=0)
    accuracy = db.Column(db.Float, default=0.0)
    duration_minutes = db.Column(db.Integer, default=0)

# AI Question Generation Service
class QuestionGenerator:
    def __init__(self):
        self.hf_token = HF_API_TOKEN
        
    def generate_questions(self, notes_text, num_questions=5):
        """Generate questions from study notes using AI"""
        try:
            # Extract key concepts from notes
            concepts = self._extract_concepts(notes_text)
            
            # Generate different types of questions
            questions = []
            question_types = ['multiple-choice', 'true-false', 'short-answer']
            
            for i in range(num_questions):
                question_type = question_types[i % len(question_types)]
                concept = concepts[i % len(concepts)] if concepts else "main concept"
                
                if question_type == 'multiple-choice':
                    question = self._generate_multiple_choice(notes_text, concept)
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
        # Simple keyword extraction (in production, use more sophisticated NLP)
        words = text.lower().split()
        
        # Filter out common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        concepts = [word for word in words if len(word) > 3 and word not in stop_words]
        
        # Return unique concepts, limited to 10
        return list(set(concepts))[:10]
    
    def _generate_multiple_choice(self, notes, concept):
        """Generate a multiple choice question"""
        return {
            'question': f"What is the main concept related to {concept} in the study material?",
            'type': 'multiple-choice',
            'options': [
                f"{concept} is the primary focus of the material",
                f"{concept} is mentioned but not central",
                f"{concept} is used as an example only",
                f"{concept} is not relevant to the main topic"
            ],
            'correct_answer': f"{concept} is the primary focus of the material",
            'explanation': f"Based on the study notes, {concept} appears to be a key concept that requires understanding.",
            'difficulty_level': 'medium'
        }
    
    def _generate_true_false(self, notes, concept):
        """Generate a true/false question"""
        return {
            'question': f"{concept} is an important concept discussed in the study material.",
            'type': 'true-false',
            'options': ['True', 'False'],
            'correct_answer': 'True',
            'explanation': f"This statement is true because {concept} is mentioned in the context of the study material.",
            'difficulty_level': 'easy'
        }
    
    def _generate_short_answer(self, notes, concept):
        """Generate a short answer question"""
        return {
            'question': f"Explain the significance of {concept} based on your study notes.",
            'type': 'short-answer',
            'options': [],
            'correct_answer': f"{concept} is significant because it relates to the main themes discussed in the study material.",
            'explanation': f"A good answer should demonstrate understanding of how {concept} fits into the broader context of the material.",
            'difficulty_level': 'hard'
        }
    
    def _generate_fallback_questions(self, notes, num_questions):
        """Generate basic questions when AI fails"""
        questions = []
        for i in range(num_questions):
            questions.append({
                'question': f"What is the main point discussed in section {i+1} of your notes?",
                'type': 'short-answer',
                'options': [],
                'correct_answer': "Answer based on your understanding of the material.",
                'explanation': "Review the relevant section of your notes to formulate a comprehensive answer.",
                'difficulty_level': 'medium'
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
        'version': '1.0.0'
    })

@app.route('/api/users', methods=['POST'])
def create_user():
    """Create a new user (temporary or registered)"""
    try:
        data = request.get_json()
        
        # Create temporary user if no email provided
        user = User()
        
        if data and data.get('email'):
            # Check if user already exists
            existing_user = User.query.filter_by(email=data['email']).first()
            if existing_user:
                return jsonify({'error': 'User already exists'}), 400
            
            user.email = data['email']
            if data.get('password'):
                user.password_hash = generate_password_hash(data['password'])
        
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
        return jsonify({'error': 'Failed to create user'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            user.last_activity = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'user_id': user.id,
                'is_premium': user.is_premium,
                'email': user.email
            })
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

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
        
        # Check premium limits
        user = User.query.get(user_id)
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
                difficulty_level=question_data.get('difficulty_level', 'medium')
            )
            db.session.add(card)
            flashcards.append(card)
        
        # Update user stats
        user.total_decks += 1
        user.total_cards += len(questions)
        user.last_activity = datetime.utcnow()
        
        db.session.commit()
        
        # Return deck data
        return jsonify({
            'deck_id': deck.id,
            'title': deck.title,
            'cards': [{
                'id': card.id,
                'question': card.question,
                'type': card.question_type,
                'options': card.options,
                'correct_answer': card.correct_answer,
                'explanation': card.explanation,
                'difficulty_level': card.difficulty_level
            } for card in flashcards],
            'created_at': deck.created_at.isoformat()
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
        
        decks = Deck.query.filter_by(user_id=user_id).order_by(Deck.created_at.desc()).all()
        
        return jsonify({
            'decks': [{
                'id': deck.id,
                'title': deck.title,
                'description': deck.description,
                'total_cards': deck.total_cards,
                'progress': deck.progress,
                'created_at': deck.created_at.isoformat(),
                'last_studied': deck.last_studied.isoformat() if deck.last_studied else None
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
        
        cards = Flashcard.query.filter_by(deck_id=deck_id).all()
        
        return jsonify({
            'id': deck.id,
            'title': deck.title,
            'description': deck.description,
            'progress': deck.progress,
            'total_cards': deck.total_cards,
            'created_at': deck.created_at.isoformat(),
            'last_studied': deck.last_studied.isoformat() if deck.last_studied else None,
            'cards': [{
                'id': card.id,
                'question': card.question,
                'type': card.question_type,
                'options': card.options,
                'correct_answer': card.correct_answer,
                'explanation': card.explanation,
                'difficulty_level': card.difficulty_level,
                'times_studied': card.times_studied,
                'times_correct': card.times_correct
            } for card in cards]
        })
        
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
        
        deck.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Deck updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating deck: {str(e)}")
        return jsonify({'error': 'Failed to update deck'}), 500

@app.route('/api/decks/<deck_id>', methods=['DELETE'])
def delete_deck(deck_id):
    """Delete a deck and all its cards"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        deck = Deck.query.filter_by(id=deck_id, user_id=user_id).first()
        if not deck:
            return jsonify({'error': 'Deck not found'}), 404
        
        # Update user stats
        user = User.query.get(user_id)
        user.total_decks = max(0, user.total_decks - 1)
        user.total_cards = max(0, user.total_cards - deck.total_cards)
        
        db.session.delete(deck)
        db.session.commit()
        
        return jsonify({'message': 'Deck deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting deck: {str(e)}")
        return jsonify({'error': 'Failed to delete deck'}), 500

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
            deck_id=deck_id
        )
        
        db.session.add(study_session)
        db.session.commit()
        
        return jsonify({
            'session_id': study_session.id,
            'started_at': study_session.started_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error starting study session: {str(e)}")
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
        
        # Update deck
        deck = Deck.query.get(study_session.deck_id)
        deck.last_studied = datetime.utcnow()
        deck.progress = data.get('deck_progress', deck.progress)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Study session completed',
            'duration_minutes': study_session.duration_minutes,
            'accuracy': study_session.accuracy
        })
        
    except Exception as e:
        logger.error(f"Error completing study session: {str(e)}")
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
        
        db.session.commit()
        
        return jsonify({
            'times_studied': card.times_studied,
            'times_correct': card.times_correct,
            'accuracy': (card.times_correct / card.times_studied) * 100 if card.times_studied > 0 else 0
        })
        
    except Exception as e:
        logger.error(f"Error recording card study: {str(e)}")
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
        
        # In production, integrate with IntaSend API here
        # For now, return mock response
        
        user = User.query.get(user_id)
        user.is_premium = True
        db.session.commit()
        
        return jsonify({
            'message': 'Successfully upgraded to premium',
            'is_premium': True,
            'payment_method': payment_method
        })
        
    except Exception as e:
        logger.error(f"Error upgrading to premium: {str(e)}")
        return jsonify({'error': 'Failed to upgrade to premium'}), 500

@app.route('/api/analytics/dashboard', methods=['GET'])
def get_analytics_dashboard():
    """Get analytics data for dashboard"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Get recent study sessions
        recent_sessions = StudySession.query.filter(
            StudySession.user_id == user_id,
            StudySession.completed_at >= datetime.utcnow() - timedelta(days=30)
        ).order_by(StudySession.completed_at.desc()).limit(10).all()
        
        # Calculate trends
        daily_stats = {}
        for session in recent_sessions:
            date_key = session.completed_at.date().isoformat()
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    'sessions': 0,
                    'cards_studied': 0,
                    'accuracy': []
                }
            
            daily_stats[date_key]['sessions'] += 1
            daily_stats[date_key]['cards_studied'] += session.cards_studied
            daily_stats[date_key]['accuracy'].append(session.accuracy)
        
        # Format for frontend
        analytics_data = []
        for date, stats in daily_stats.items():
            avg_accuracy = sum(stats['accuracy']) / len(stats['accuracy']) if stats['accuracy'] else 0
            analytics_data.append({
                'date': date,
                'sessions': stats['sessions'],
                'cards_studied': stats['cards_studied'],
                'accuracy': round(avg_accuracy, 1)
            })
        
        return jsonify({
            'recent_activity': analytics_data,
            'total_sessions': len(recent_sessions),
            'avg_accuracy': round(sum(s.accuracy for s in recent_sessions) / len(recent_sessions), 1) if recent_sessions else 0
        })
        
    except Exception as e:
        logger.error(f"Error fetching analytics: {str(e)}")
        return jsonify({'error': 'Failed to fetch analytics'}), 500

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