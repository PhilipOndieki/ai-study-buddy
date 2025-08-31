from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from intasend import APIService
import os
import random
import uuid
import requests
import json
import logging
import re
from collections import Counter
from dotenv import load_dotenv

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

# AI Question Generation Logic
class EnhancedQuestionGenerator:
    def __init__(self, hf_token=None):
        self.hf_token = hf_token or os.getenv('HF_API_TOKEN')
        
        # Validate token
        if not self.hf_token:
            logger.error("No HF_API_TOKEN found in environment variables")
            self.api_available = False
            return
        
        if not self.hf_token.startswith('hf_') or len(self.hf_token) < 30:
            logger.error(f"Invalid HF token format. Token should start with 'hf_' and be ~37 characters")
            self.api_available = False
            return
        
        logger.info(f"HF token loaded successfully: hf_***{self.hf_token[-8:]}")
        
        # Use the serverless inference API (most reliable)
        self.api_base = "https://api-inference.huggingface.co/models"
        
        # Reliable models as of 2025
        self.models = {
            'text_generation': 'microsoft/DialoGPT-medium',
            'question_generation': 'valhalla/t5-small-qg-hl',  # Specialized for question generation
            'summarization': 'facebook/bart-large-cnn',
            'fill_mask': 'bert-base-uncased'
        }
        
        self.headers = {
            "Authorization": f"Bearer {self.hf_token}",
            "Content-Type": "application/json"
        }
        
        self.api_available = self.test_api_connection()
        random.seed()
    
    def test_api_connection(self):
        """Test if the HF API is accessible and working"""
        try:
            # Use a simple, reliable model for testing
            url = f"{self.api_base}/microsoft/DialoGPT-medium"
            
            test_payload = {
                "inputs": "Hello",
                "parameters": {
                    "max_new_tokens": 5,
                    "temperature": 0.1
                }
            }
            
            response = requests.post(
                url, 
                headers=self.headers, 
                json=test_payload, 
                timeout=10
            )
            
            logger.info(f"API test response: {response.status_code}")
            
            if response.status_code == 200:
                logger.info("HF API connection successful")
                return True
            elif response.status_code == 503:
                logger.warning("Model is loading, this is normal for first use")
                return True  # Model loading is still a valid connection
            else:
                logger.error(f"API test failed: {response.status_code} - {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"API connection test failed: {str(e)}")
            return False
    
    def generate_questions(self, notes_text, num_questions=5):
        """Main method to generate questions from study notes"""
        logger.info(f"Generating {num_questions} questions from {len(notes_text)} characters of notes")
        
        try:
            # Clean and validate input
            notes_text = self._clean_notes(notes_text)
            if len(notes_text) < 50:
                logger.warning("Notes too short for meaningful question generation")
                return self._generate_basic_fallback_questions(notes_text, num_questions)
            
            # Extract key concepts
            concepts = self._extract_key_concepts(notes_text)
            logger.info(f"Extracted {len(concepts)} key concepts")
            
            questions = []
            question_types = ['multiple-choice', 'true-false', 'short-answer']
            
            # Try AI generation for each question
            for i in range(num_questions):
                question_type = question_types[i % len(question_types)]
                concept = concepts[i % len(concepts)] if concepts else f"topic_{i+1}"
                
                logger.info(f"Generating question {i+1}: {question_type} about {concept}")
                
                if self.api_available:
                    ai_question = self._generate_ai_question(notes_text, concept, question_type)
                    if ai_question:
                        questions.append(ai_question)
                        logger.info(f"Successfully generated AI question {i+1}")
                        continue
                
                # Fallback to rule-based generation
                logger.info(f"Using fallback for question {i+1}")
                fallback_question = self._generate_intelligent_fallback(notes_text, concept, question_type)
                questions.append(fallback_question)
            
            logger.info(f"Generated {len(questions)} questions total")
            return questions
            
        except Exception as e:
            logger.error(f"Question generation failed: {str(e)}")
            return self._generate_basic_fallback_questions(notes_text, num_questions)
    
    def _clean_notes(self, text):
        """Clean and prepare notes text for processing"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        # Remove special characters that might interfere with API
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-]', '', text)
        return text
    
    def _extract_key_concepts(self, text):
        """Extract meaningful concepts from the text"""
        try:
            # Convert to lowercase for processing
            text_lower = text.lower()
            
            # Find all words (3+ characters)
            words = re.findall(r'\b[a-z]{3,}\b', text_lower)
            
            # Common stop words to exclude
            stop_words = {
                'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 
                'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 
                'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 
                'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use', 'this', 'that', 
                'with', 'have', 'will', 'from', 'they', 'know', 'want', 'been', 'good', 
                'much', 'some', 'time', 'very', 'when', 'come', 'here', 'just', 'like', 
                'long', 'make', 'many', 'over', 'such', 'take', 'than', 'them', 'well', 
                'were', 'what', 'where', 'which', 'while', 'would', 'could', 'should'
            }
            
            # Filter meaningful words
            meaningful_words = [word for word in words if word not in stop_words and len(word) > 3]
            
            # Count frequency
            word_freq = Counter(meaningful_words)
            
            # Get top concepts
            top_concepts = [word for word, freq in word_freq.most_common(15)]
            
            # Also extract capitalized words (likely important terms)
            capitalized = re.findall(r'\b[A-Z][a-z]+\b', text)
            capitalized_lower = [word.lower() for word in capitalized if word.lower() not in stop_words]
            
            # Combine and deduplicate
            all_concepts = list(dict.fromkeys(top_concepts + capitalized_lower))
            
            # Ensure we have at least some concepts
            if not all_concepts:
                all_concepts = ['concept', 'topic', 'subject', 'information', 'material']
            
            return all_concepts[:20]  # Limit to top 20
            
        except Exception as e:
            logger.warning(f"Concept extraction failed: {str(e)}")
            return ['concept', 'topic', 'subject', 'information', 'material']
    
    def _generate_ai_question(self, notes_text, concept, question_type):
        """Generate a question using HF API"""
        try:
            # Truncate notes to prevent API limits
            truncated_notes = notes_text[:1500]
            
            # Try question generation model first
            question = self._try_question_generation_model(truncated_notes, concept, question_type)
            if question:
                return question
            
            # Fallback to text generation
            question = self._try_text_generation_model(truncated_notes, concept, question_type)
            if question:
                return question
            
            return None
            
        except Exception as e:
            logger.warning(f"AI question generation failed: {str(e)}")
            return None
    
    def _try_question_generation_model(self, notes_text, concept, question_type):
        """Try using a specialized question generation model"""
        try:
            url = f"{self.api_base}/{self.models['question_generation']}"
            
            # Format input for question generation model
            if question_type == 'multiple-choice':
                prompt = f"generate question: {concept} context: {notes_text[:800]}"
            else:
                prompt = f"question: {concept} answer: {notes_text[:800]}"
            
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 100,
                    "temperature": 0.7,
                    "do_sample": True
                }
            }
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get('generated_text', '')
                    return self._parse_generated_question(generated_text, concept, question_type, notes_text)
            
            elif response.status_code == 503:
                logger.info("Question generation model is loading, trying alternative...")
                return None
            
            else:
                logger.warning(f"Question generation API failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"Question generation model failed: {str(e)}")
            return None
    
    def _try_text_generation_model(self, notes_text, concept, question_type):
        """Try using general text generation model"""
        try:
            url = f"{self.api_base}/{self.models['text_generation']}"
            
            # Create focused prompts
            if question_type == 'multiple-choice':
                prompt = f"Create a multiple choice question about {concept}. Question:"
            elif question_type == 'true-false':
                prompt = f"True or false statement about {concept}:"
            else:
                prompt = f"Question about {concept}:"
            
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 80,
                    "temperature": 0.6,
                    "do_sample": True,
                    "return_full_text": False
                }
            }
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get('generated_text', '')
                    if generated_text.strip():
                        return self._create_structured_question(generated_text, concept, question_type, notes_text)
            
            return None
            
        except Exception as e:
            logger.warning(f"Text generation model failed: {str(e)}")
            return None
    
    def _parse_generated_question(self, generated_text, concept, question_type, notes_text):
        """Parse and structure the AI-generated question"""
        try:
            generated_text = generated_text.strip()
            
            if not generated_text:
                return None
            
            # Look for question patterns
            question_match = re.search(r'(?:Question:|Q:)?\s*([^?]+\?)', generated_text, re.IGNORECASE)
            
            if question_match:
                question_text = question_match.group(1).strip()
                if not question_text.endswith('?'):
                    question_text += '?'
            else:
                # Use the generated text as inspiration for the question
                question_text = f"Based on the study material, {generated_text[:100]}?" if not generated_text.endswith('?') else generated_text[:100]
            
            return self._create_structured_question(question_text, concept, question_type, notes_text)
            
        except Exception as e:
            logger.warning(f"Question parsing failed: {str(e)}")
            return None
    
    def _create_structured_question(self, question_text, concept, question_type, notes_text):
        """Create a properly structured question object"""
        try:
            if question_type == 'multiple-choice':
                # Extract or create meaningful options
                correct_answer = self._extract_correct_answer(notes_text, concept)
                distractors = self._generate_distractors(concept, correct_answer)
                
                options = [correct_answer] + distractors
                random.shuffle(options)
                
                return {
                    'question': question_text,
                    'type': 'multiple-choice',
                    'options': options,
                    'correct_answer': correct_answer,
                    'explanation': f"This question tests understanding of {concept} from your study material.",
                    'difficulty_level': 'medium',
                    'topic': concept
                }
            
            elif question_type == 'true-false':
                # Convert question to a statement
                statement = self._convert_to_statement(question_text, concept, notes_text)
                is_true = self._verify_statement_accuracy(statement, notes_text, concept)
                
                return {
                    'question': statement,
                    'type': 'true-false',
                    'options': ['True', 'False'],
                    'correct_answer': 'True' if is_true else 'False',
                    'explanation': f"This statement is based on information about {concept} in your study material.",
                    'difficulty_level': 'easy',
                    'topic': concept
                }
            
            else:  # short-answer
                return {
                    'question': question_text,
                    'type': 'short-answer',
                    'options': [],
                    'correct_answer': self._generate_sample_answer(concept, notes_text),
                    'explanation': f"A good answer should demonstrate understanding of {concept} with specific details from the material.",
                    'difficulty_level': 'hard',
                    'topic': concept
                }
            
        except Exception as e:
            logger.warning(f"Question structuring failed: {str(e)}")
            return None
    
    def _extract_correct_answer(self, notes_text, concept):
        """Extract a correct answer about the concept from notes"""
        try:
            # Find sentences mentioning the concept
            sentences = re.split(r'[.!?]+', notes_text)
            concept_sentences = [s.strip() for s in sentences if concept.lower() in s.lower()]
            
            if concept_sentences:
                # Use the first relevant sentence as basis for correct answer
                sentence = concept_sentences[0]
                # Clean and truncate
                clean_sentence = re.sub(r'\s+', ' ', sentence).strip()
                if len(clean_sentence) > 80:
                    clean_sentence = clean_sentence[:77] + "..."
                return clean_sentence
            else:
                return f"{concept.title()} is an important concept discussed in the study material"
                
        except Exception as e:
            return f"{concept.title()} is covered in the study material"
    
    def _generate_distractors(self, concept, correct_answer):
        """Generate plausible wrong answers"""
        distractors = [
            f"{concept.title()} is not mentioned in the study material",
            f"{concept.title()} is only briefly referenced without explanation",
            f"{concept.title()} is presented as an outdated approach"
        ]
        
        # Ensure distractors are different from correct answer
        distractors = [d for d in distractors if d.lower() != correct_answer.lower()]
        
        return distractors[:3]
    
    def _convert_to_statement(self, question_text, concept, notes_text):
        """Convert a question to a true/false statement"""
        try:
            # Remove question words and punctuation
            statement = re.sub(r'^(what|how|why|when|where|who)\s+', '', question_text.lower())
            statement = statement.replace('?', '').strip()
            
            # If we can't convert properly, create a factual statement
            if len(statement) < 10:
                # Find a fact about the concept from notes
                sentences = re.split(r'[.!?]+', notes_text)
                concept_sentences = [s.strip() for s in sentences if concept.lower() in s.lower()]
                
                if concept_sentences:
                    statement = concept_sentences[0].strip()
                else:
                    statement = f"{concept.title()} is discussed as an important topic in the study material"
            
            return statement.strip()
            
        except Exception as e:
            return f"{concept.title()} is mentioned in the study material"
    
    def _verify_statement_accuracy(self, statement, notes_text, concept):
        """Check if a statement is likely true based on the notes"""
        try:
            # Simple heuristic: if key words from statement appear in notes, likely true
            statement_words = set(re.findall(r'\b\w{4,}\b', statement.lower()))
            notes_words = set(re.findall(r'\b\w{4,}\b', notes_text.lower()))
            
            # Calculate overlap
            overlap = len(statement_words.intersection(notes_words))
            overlap_ratio = overlap / len(statement_words) if statement_words else 0
            
            # If more than 50% of statement words are in notes, likely true
            return overlap_ratio > 0.5
            
        except Exception as e:
            return True  # Default to true for safety
    
    def _generate_sample_answer(self, concept, notes_text):
        """Generate a sample answer for short-answer questions"""
        try:
            # Find relevant content about the concept
            sentences = re.split(r'[.!?]+', notes_text)
            relevant_sentences = [s.strip() for s in sentences if concept.lower() in s.lower()]
            
            if relevant_sentences:
                sample = relevant_sentences[0]
                if len(sample) > 150:
                    sample = sample[:147] + "..."
                return f"A comprehensive answer should explain that {sample} Additional details about {concept} should be included based on the study material."
            else:
                return f"A good answer should define {concept}, explain its significance, and provide specific examples or details from the study material."
                
        except Exception as e:
            return f"Explain what {concept} is and why it's important based on your study material."
    
    def _generate_intelligent_fallback(self, notes_text, concept, question_type):
        """Generate high-quality fallback questions using rule-based approach"""
        try:
            if question_type == 'multiple-choice':
                # Create question based on actual content
                question = f"According to the study material, what is true about {concept}?"
                correct_answer = self._extract_correct_answer(notes_text, concept)
                distractors = self._generate_distractors(concept, correct_answer)
                
                options = [correct_answer] + distractors
                random.shuffle(options)
                
                return {
                    'question': question,
                    'type': 'multiple-choice',
                    'options': options,
                    'correct_answer': correct_answer,
                    'explanation': f"This question is based on content analysis of {concept} in your study material.",
                    'difficulty_level': 'medium',
                    'topic': concept
                }
            
            elif question_type == 'true-false':
                # Create a factual statement
                statement = self._create_factual_statement(notes_text, concept)
                
                return {
                    'question': statement,
                    'type': 'true-false',
                    'options': ['True', 'False'],
                    'correct_answer': 'True',
                    'explanation': f"This statement reflects information about {concept} found in your study material.",
                    'difficulty_level': 'easy',
                    'topic': concept
                }
            
            else:  # short-answer
                question = f"Explain the significance of {concept} based on your study material."
                sample_answer = self._generate_sample_answer(concept, notes_text)
                
                return {
                    'question': question,
                    'type': 'short-answer',
                    'options': [],
                    'correct_answer': sample_answer,
                    'explanation': f"Focus on key aspects of {concept} discussed in the material.",
                    'difficulty_level': 'hard',
                    'topic': concept
                }
            
        except Exception as e:
            logger.warning(f"Intelligent fallback failed: {str(e)}")
            return self._generate_basic_question(concept, question_type)
    
    def _create_factual_statement(self, notes_text, concept):
        """Create a factual statement about the concept"""
        try:
            # Find sentences containing the concept
            sentences = re.split(r'[.!?]+', notes_text)
            concept_sentences = [s.strip() for s in sentences if concept.lower() in s.lower()]
            
            if concept_sentences:
                # Use the first sentence as basis
                statement = concept_sentences[0].strip()
                if len(statement) > 120:
                    statement = statement[:117] + "..."
                return statement
            else:
                return f"{concept.title()} is an important topic covered in the study material"
                
        except Exception as e:
            return f"{concept.title()} is discussed in the study material"
    
    def _generate_basic_question(self, concept, question_type):
        """Generate basic question when all else fails"""
        if question_type == 'multiple-choice':
            return {
                'question': f"What can be said about {concept}?",
                'type': 'multiple-choice',
                'options': [
                    f"{concept.title()} is an important concept in the material",
                    f"{concept.title()} is not relevant to the topic",
                    f"{concept.title()} is mentioned only in passing",
                    f"{concept.title()} contradicts the main theme"
                ],
                'correct_answer': f"{concept.title()} is an important concept in the material",
                'explanation': f"Review your study material for information about {concept}.",
                'difficulty_level': 'medium',
                'topic': concept
            }
        elif question_type == 'true-false':
            return {
                'question': f"{concept.title()} is discussed in the study material.",
                'type': 'true-false',
                'options': ['True', 'False'],
                'correct_answer': 'True',
                'explanation': f"The concept {concept} appears in your study material.",
                'difficulty_level': 'easy',
                'topic': concept
            }
        else:
            return {
                'question': f"Describe what you learned about {concept}.",
                'type': 'short-answer',
                'options': [],
                'correct_answer': f"A complete answer should define {concept} and explain its relevance based on the study material.",
                'explanation': f"Use specific information from your notes about {concept}.",
                'difficulty_level': 'hard',
                'topic': concept
            }
    
    def _generate_basic_fallback_questions(self, notes_text, num_questions):
        """Generate basic questions when API is completely unavailable"""
        logger.info("Generating basic fallback questions")
        
        concepts = self._extract_key_concepts(notes_text)
        questions = []
        question_types = ['multiple-choice', 'true-false', 'short-answer']
        
        for i in range(num_questions):
            question_type = question_types[i % len(question_types)]
            concept = concepts[i % len(concepts)] if concepts else f"concept_{i+1}"
            
            question = self._generate_intelligent_fallback(notes_text, concept, question_type)
            questions.append(question)
        
        return questions
    
    def get_api_status(self):
        """Get current API status for debugging"""
        return {
            'token_available': bool(self.hf_token),
            'token_valid_format': self.hf_token and self.hf_token.startswith('hf_') and len(self.hf_token) > 30 if self.hf_token else False,
            'api_accessible': self.api_available,
            'models': self.models
        }
        
# Initialize the question generator
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
    """Handle premium upgrade with IntaSend integration"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        payment_method = data.get('payment_method', 'card')
        subscription_type = data.get('subscription_type', 'monthly')
        phone_number = data.get('phone_number')  # For M-Pesa
        email = data.get('email')
        
        # Get user details
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Initialize IntaSend service
        service = APIService(
            token=os.getenv('INTASEND_SECRET_KEY'),
            publishable_key=os.getenv('INTASEND_PUBLIC_KEY'),
            test=os.getenv('INTASEND_TEST_MODE', 'True').lower() == 'true'
        )
        
        # Set subscription amount based on type
        amount = 999 if subscription_type == 'monthly' else 9999  # KES
        
        # Create payment request based on method
        if payment_method == 'mpesa':
            if not phone_number:
                return jsonify({'error': 'Phone number required for M-Pesa'}), 400
            
            # STK Push for M-Pesa
            response = service.collect.mpesa_stk_push(
                phone_number=phone_number,
                email=email or user.email,
                amount=amount,
                narrative=f"Premium Subscription - {subscription_type.title()}"
            )
            
        elif payment_method == 'card':
            # Create checkout session for card payment
            response = service.collect.checkout(
                email=email or user.email,
                amount=amount,
                currency='KES',
                method=['CARD'],
                redirect_url=f"{request.host_url}payment/success",
                api_ref=f"premium_{user_id}_{int(datetime.utcnow().timestamp())}"
            )
            
        else:
            return jsonify({'error': 'Invalid payment method'}), 400
        
        # Handle IntaSend response
        if response.get('invoice'):
            # Store payment reference for verification
            payment_ref = response['invoice']['invoice_id']
            
            # Store pending payment in database (you might want to create a Payment model)
            # This is optional but recommended for tracking
            
            if payment_method == 'card':
                return jsonify({
                    'payment_url': response['invoice']['payment_link'],
                    'payment_ref': payment_ref,
                    'message': 'Redirect to payment page'
                })
            else:
                # For M-Pesa, return status
                return jsonify({
                    'payment_ref': payment_ref,
                    'message': 'M-Pesa payment initiated. Check your phone for STK push.',
                    'status': 'pending'
                })
        else:
            logger.error(f"IntaSend API error: {response}")
            return jsonify({'error': 'Payment initialization failed'}), 500
            
    except Exception as e:
        logger.error(f"Error upgrading to premium: {str(e)}")
        return jsonify({'error': 'Failed to process payment'}), 500

@app.route('/api/payment/verify', methods=['POST']) 
def verify_payment():
    """Verify payment and activate premium subscription"""
    try:
        data = request.get_json()
        payment_ref = data.get('payment_ref')
        
        if not payment_ref:
            return jsonify({'error': 'Payment reference required'}), 400
        
        # Initialize IntaSend service
        service = APIService(
            token=os.getenv('INTASEND_SECRET_KEY'),
            publishable_key=os.getenv('INTASEND_PUBLIC_KEY'),
            test=os.getenv('INTASEND_TEST_MODE', 'True').lower() == 'true'
        )
        
        # Check payment status
        payment_status = service.collect.status(invoice_id=payment_ref)
        
        if payment_status.get('invoice', {}).get('state') == 'COMPLETE':
            # Payment successful, activate premium
            user_id = session.get('user_id')
            user = User.query.get(user_id)
            
            # Determine subscription length from payment amount or store it separately
            amount = payment_status['invoice']['amount']
            subscription_type = 'yearly' if float(amount) >= 9999 else 'monthly'
            
            user.is_premium = True
            
            if subscription_type == 'yearly':
                user.premium_expires_at = datetime.utcnow() + timedelta(days=365)
            else:
                user.premium_expires_at = datetime.utcnow() + timedelta(days=30)
            
            db.session.commit()
            
            return jsonify({
                'message': 'Payment verified and premium activated',
                'is_premium': True,
                'premium_expires_at': user.premium_expires_at.isoformat(),
                'subscription_type': subscription_type
            })
        else:
            return jsonify({
                'message': 'Payment not completed',
                'status': payment_status.get('invoice', {}).get('state', 'UNKNOWN')
            })
            
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        return jsonify({'error': 'Payment verification failed'}), 500

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