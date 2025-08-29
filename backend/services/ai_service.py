import requests
import json
import logging
from typing import List, Dict, Any
import re
from collections import Counter

logger = logging.getLogger(__name__)

class AIQuestionGenerator:
    """Service for generating questions using AI models"""
    
    def __init__(self, hf_token: str = None):
        self.hf_token = hf_token
        self.hf_headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}
        
        # Question generation models
        self.qa_model_url = "https://api-inference.huggingface.co/models/deepset/roberta-base-squad2"
        self.text_gen_url = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"
        
    def generate_questions(self, notes_text: str, num_questions: int = 5) -> List[Dict[str, Any]]:
        """Generate diverse questions from study notes"""
        try:
            # Clean and prepare text
            cleaned_notes = self._clean_text(notes_text)
            
            # Extract key concepts and topics
            concepts = self._extract_key_concepts(cleaned_notes)
            sentences = self._extract_key_sentences(cleaned_notes)
            
            questions = []
            question_types = ['multiple-choice', 'true-false', 'short-answer']
            
            for i in range(num_questions):
                question_type = question_types[i % len(question_types)]
                
                if i < len(concepts):
                    concept = concepts[i]
                    context_sentence = sentences[i % len(sentences)] if sentences else cleaned_notes[:200]
                else:
                    concept = f"concept_{i+1}"
                    context_sentence = cleaned_notes[:200]
                
                if question_type == 'multiple-choice':
                    question = self._generate_multiple_choice_question(concept, context_sentence, cleaned_notes)
                elif question_type == 'true-false':
                    question = self._generate_true_false_question(concept, context_sentence)
                else:
                    question = self._generate_short_answer_question(concept, context_sentence)
                
                questions.append(question)
            
            return questions
            
        except Exception as e:
            logger.error(f"Error in AI question generation: {str(e)}")
            return self._generate_fallback_questions(notes_text, num_questions)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize input text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove special characters that might interfere with processing
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', '', text)
        
        return text
    
    def _extract_key_concepts(self, text: str) -> List[str]:
        """Extract important concepts from text using NLP techniques"""
        # Simple approach - in production, use more sophisticated NLP
        words = re.findall(r'\b[A-Z][a-z]+\b|\b[a-z]{4,}\b', text)
        
        # Filter out common words
        stop_words = {
            'this', 'that', 'with', 'have', 'will', 'from', 'they', 'know', 
            'want', 'been', 'good', 'much', 'some', 'time', 'very', 'when', 
            'come', 'here', 'just', 'like', 'long', 'make', 'many', 'over', 
            'such', 'take', 'than', 'them', 'well', 'were', 'what'
        }
        
        # Count word frequency
        word_freq = Counter([word.lower() for word in words if word.lower() not in stop_words])
        
        # Return top concepts
        return [word for word, freq in word_freq.most_common(10)]
    
    def _extract_key_sentences(self, text: str) -> List[str]:
        """Extract important sentences from text"""
        sentences = re.split(r'[.!?]+', text)
        
        # Filter sentences by length and content
        key_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if 20 <= len(sentence) <= 200 and not sentence.startswith(('http', 'www')):
                key_sentences.append(sentence)
        
        return key_sentences[:10]
    
    def _generate_multiple_choice_question(self, concept: str, context: str, full_text: str) -> Dict[str, Any]:
        """Generate a multiple choice question"""
        # Create question based on concept
        question_templates = [
            f"What is the primary role of {concept} in this context?",
            f"Which statement best describes {concept}?",
            f"How does {concept} relate to the main topic?",
            f"What can be concluded about {concept} from the material?"
        ]
        
        question = question_templates[hash(concept) % len(question_templates)]
        
        # Generate plausible options
        correct_option = f"{concept} is a key element that plays an important role in the subject matter"
        
        distractor_templates = [
            f"{concept} is mentioned only briefly and has minimal importance",
            f"{concept} is used as a contrasting example to the main topic",
            f"{concept} is an outdated approach that is no longer relevant"
        ]
        
        options = [correct_option] + distractor_templates
        
        # Shuffle options but remember correct index
        import random
        correct_index = 0
        random.shuffle(options)
        correct_index = options.index(correct_option)
        
        return {
            'question': question,
            'type': 'multiple-choice',
            'options': options,
            'correct_answer': correct_option,
            'correct_index': correct_index,
            'explanation': f"Based on the study material, {concept} is clearly identified as an important concept that requires understanding.",
            'difficulty_level': 'medium',
            'topic': concept
        }
    
    def _generate_true_false_question(self, concept: str, context: str) -> Dict[str, Any]:
        """Generate a true/false question"""
        # Randomly choose true or false statement
        import random
        is_true = random.choice([True, False])
        
        if is_true:
            statement = f"{concept} is discussed as an important element in the study material"
            correct_answer = "True"
            explanation = f"This statement is true because {concept} appears in the context of the study material and is relevant to understanding the topic."
        else:
            statement = f"{concept} is completely unrelated to the main topic of study"
            correct_answer = "False"
            explanation = f"This statement is false because {concept} is actually mentioned and relevant to the study material."
        
        return {
            'question': statement,
            'type': 'true-false',
            'options': ['True', 'False'],
            'correct_answer': correct_answer,
            'explanation': explanation,
            'difficulty_level': 'easy',
            'topic': concept
        }
    
    def _generate_short_answer_question(self, concept: str, context: str) -> Dict[str, Any]:
        """Generate a short answer question"""
        question_templates = [
            f"Explain the importance of {concept} in your own words.",
            f"Describe how {concept} relates to the main topic.",
            f"What would happen if {concept} was not considered?",
            f"Compare {concept} with other elements discussed in the material."
        ]
        
        question = question_templates[hash(concept) % len(question_templates)]
        
        return {
            'question': question,
            'type': 'short-answer',
            'options': [],
            'correct_answer': f"A comprehensive answer should demonstrate understanding of {concept} and its relationship to the broader topic discussed in the study material.",
            'explanation': f"Good answers will show how {concept} fits into the overall context and why it's significant for understanding the subject matter.",
            'difficulty_level': 'hard',
            'topic': concept
        }
    
    def _generate_fallback_questions(self, notes_text: str, num_questions: int) -> List[Dict[str, Any]]:
        """Generate basic questions when AI processing fails"""
        questions = []
        
        # Split notes into sections
        sections = notes_text.split('\n\n') if '\n\n' in notes_text else [notes_text]
        
        for i in range(num_questions):
            section_index = i % len(sections)
            section = sections[section_index][:100]
            
            questions.append({
                'question': f"What is the main point discussed in this section: '{section}...'?",
                'type': 'short-answer',
                'options': [],
                'correct_answer': "Answer should summarize the key points from the specified section.",
                'explanation': "Review the relevant section of your notes to identify the main concepts and their relationships.",
                'difficulty_level': 'medium',
                'topic': f"section_{i+1}"
            })
        
        return questions

class SpacedRepetitionService:
    """Service for implementing spaced repetition algorithm"""
    
    @staticmethod
    def calculate_next_review(card, performance_rating: str) -> Dict[str, Any]:
        """Calculate next review date using spaced repetition algorithm"""
        # SM-2 algorithm implementation
        current_interval = card.review_interval or 1
        current_ease = card.ease_factor or 2.5
        
        if performance_rating == 'easy':
            quality = 5
        elif performance_rating == 'medium':
            quality = 3
        else:  # hard
            quality = 1
        
        if quality < 3:
            # Reset interval for difficult cards
            new_interval = 1
            new_ease = current_ease
        else:
            if current_interval == 1:
                new_interval = 6
            elif current_interval == 6:
                new_interval = 6
            else:
                new_interval = round(current_interval * current_ease)
            
            # Update ease factor
            new_ease = current_ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            new_ease = max(1.3, new_ease)  # Minimum ease factor
        
        # Calculate next review date
        from datetime import datetime, timedelta
        next_review = datetime.utcnow() + timedelta(days=new_interval)
        
        return {
            'next_review': next_review,
            'review_interval': new_interval,
            'ease_factor': new_ease
        }