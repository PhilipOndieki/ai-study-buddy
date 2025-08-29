from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

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
    payments = db.relationship('Payment', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email or self.id}>'
    
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
    
    def __repr__(self):
        return f'<Deck {self.title}>'
    
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
    options = db.Column(db.JSON)  # Array of options for multiple choice
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
    
    def __repr__(self):
        return f'<Flashcard {self.question[:50]}...>'
    
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
    
    def __repr__(self):
        return f'<StudySession {self.id}>'
    
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

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Payment details
    amount = db.Column(db.Decimal(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='KES')
    payment_method = db.Column(db.String(50))  # mpesa, card, airtel_money
    
    # IntaSend integration
    intasend_transaction_id = db.Column(db.String(100), unique=True)
    intasend_reference = db.Column(db.String(100))
    
    # Status tracking
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)
    
    # Subscription details
    subscription_type = db.Column(db.String(20))  # monthly, yearly
    subscription_start = db.Column(db.DateTime)
    subscription_end = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<Payment {self.amount} {self.currency}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'amount': float(self.amount),
            'currency': self.currency,
            'payment_method': self.payment_method,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'subscription_type': self.subscription_type
        }

# Database utility functions
def init_db(app):
    """Initialize database with app context"""
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")

def reset_db(app):
    """Reset database (use with caution!)"""
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database reset completed")