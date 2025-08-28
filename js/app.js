// Main Application Controller
class AIStudyBuddyApp {
    constructor() {
        this.currentScreen = 'welcome';
        this.currentDeck = null;
        this.currentCardIndex = 0;
        this.studyProgress = {
            easy: 0,
            medium: 0,
            hard: 0
        };
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadScreen('welcome');
    }

    bindEvents() {
        // Navigation events
        document.getElementById('start-btn')?.addEventListener('click', () => {
            this.loadScreen('input');
        });

        document.getElementById('back-to-welcome')?.addEventListener('click', () => {
            this.loadScreen('welcome');
        });

        document.getElementById('my-decks-btn')?.addEventListener('click', () => {
            this.loadMyDecks();
        });

        document.getElementById('upgrade-btn')?.addEventListener('click', () => {
            this.showPremiumModal();
        });

        // Input screen events
        const notesInput = document.getElementById('notes-input');
        const generateBtn = document.getElementById('generate-btn');
        const charCount = document.getElementById('char-count');

        if (notesInput) {
            notesInput.addEventListener('input', (e) => {
                const length = e.target.value.length;
                charCount.textContent = length;
                
                generateBtn.disabled = length < 100 || length > 5000;
                
                if (length > 5000) {
                    this.showError('Maximum 5000 characters allowed');
                } else if (length > 0 && length < 100) {
                    this.showError('Minimum 100 characters required');
                } else {
                    this.hideError();
                }
            });
        }

        if (generateBtn) {
            generateBtn.addEventListener('click', () => {
                this.generateFlashcards(notesInput.value);
            });
        }

        // Deck management events
        document.getElementById('create-new-deck')?.addEventListener('click', () => {
            this.loadScreen('input');
        });

        document.getElementById('create-first-deck')?.addEventListener('click', () => {
            this.loadScreen('input');
        });

        // Premium modal events
        document.getElementById('close-premium')?.addEventListener('click', () => {
            this.hidePremiumModal();
        });

        document.getElementById('subscribe-btn')?.addEventListener('click', () => {
            this.handleSubscription();
        });

        // Click outside modal to close
        document.getElementById('premium-modal')?.addEventListener('click', (e) => {
            if (e.target.id === 'premium-modal') {
                this.hidePremiumModal();
            }
        });

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (this.currentScreen === 'flashcards') {
                switch(e.code) {
                    case 'Space':
                        e.preventDefault();
                        this.toggleCard();
                        break;
                    case 'ArrowLeft':
                        e.preventDefault();
                        this.previousCard();
                        break;
                    case 'ArrowRight':
                        e.preventDefault();
                        this.nextCard();
                        break;
                    case 'Digit1':
                        e.preventDefault();
                        this.rateCard('easy');
                        break;
                    case 'Digit2':
                        e.preventDefault();
                        this.rateCard('medium');
                        break;
                    case 'Digit3':
                        e.preventDefault();
                        this.rateCard('hard');
                        break;
                }
            }
        });
    }

    loadScreen(screenName) {
        // Hide all screens
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });

        // Show target screen
        const targetScreen = document.getElementById(`${screenName}-screen`);
        if (targetScreen) {
            targetScreen.classList.add('active');
            this.currentScreen = screenName;
        }

        // Update page title
        this.updatePageTitle(screenName);
    }

    updatePageTitle(screenName) {
        const titles = {
            'welcome': 'AI Study Buddy - Transform Notes into Smart Flashcards',
            'input': 'AI Study Buddy - Add Your Notes',
            'loading': 'AI Study Buddy - Generating Flashcards',
            'flashcards': 'AI Study Buddy - Study Session',
            'decks': 'AI Study Buddy - My Decks'
        };
        
        document.title = titles[screenName] || 'AI Study Buddy';
    }

    async generateFlashcards(notes) {
        if (!notes || notes.length < 100) {
            this.showError('Please enter at least 100 characters of study notes');
            return;
        }

        // Show loading state
        const generateBtn = document.getElementById('generate-btn');
        generateBtn.classList.add('loading');
        generateBtn.disabled = true;

        try {
            // Switch to loading screen
            this.loadScreen('loading');
            
            // Simulate AI processing with realistic timing
            await this.simulateAIGeneration();
            
            // Generate mock flashcards (in production, this would call the Hugging Face API)
            const flashcards = this.generateMockFlashcards(notes);
            
            // Create and save deck
            const deck = {
                id: Date.now().toString(),
                title: this.generateDeckTitle(notes),
                cards: flashcards,
                created: new Date().toISOString(),
                lastStudied: null,
                progress: 0
            };

            // Save to storage
            StorageManager.saveDeck(deck);
            
            // Load flashcards screen
            this.currentDeck = deck;
            this.currentCardIndex = 0;
            this.resetStudyProgress();
            
            setTimeout(() => {
                this.loadScreen('flashcards');
                FlashcardManager.loadDeck(deck);
            }, 1000);

        } catch (error) {
            console.error('Error generating flashcards:', error);
            this.showError('Failed to generate flashcards. Please try again.');
            this.loadScreen('input');
        } finally {
            generateBtn.classList.remove('loading');
            generateBtn.disabled = false;
        }
    }

    async simulateAIGeneration() {
        const progressBar = document.querySelector('.progress-fill');
        const questionsGenerated = document.getElementById('questions-generated');
        const progressPercent = document.getElementById('progress-percent');
        
        let progress = 0;
        let questions = 0;
        
        return new Promise((resolve) => {
            const interval = setInterval(() => {
                progress += Math.random() * 15 + 5; // Random progress increments
                questions = Math.min(5, Math.floor(progress / 20));
                
                if (progress >= 100) {
                    progress = 100;
                    questions = 5;
                    clearInterval(interval);
                    setTimeout(resolve, 500);
                }
                
                progressBar.style.width = `${progress}%`;
                questionsGenerated.textContent = questions;
                progressPercent.textContent = `${Math.floor(progress)}%`;
            }, 400);
        });
    }

    generateMockFlashcards(notes) {
        // This is a mock implementation. In production, this would use the Hugging Face API
        const topics = this.extractTopics(notes);
        const flashcards = [];

        const questionTypes = ['multiple-choice', 'true-false', 'short-answer'];
        
        for (let i = 0; i < 5; i++) {
            const type = questionTypes[Math.floor(Math.random() * questionTypes.length)];
            const topic = topics[Math.floor(Math.random() * topics.length)];
            
            flashcards.push(this.createMockCard(type, topic, notes));
        }

        return flashcards;
    }

    extractTopics(notes) {
        // Simple topic extraction (in production, use NLP)
        const words = notes.toLowerCase().split(/\W+/);
        const commonWords = new Set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must', 'shall', 'this', 'that', 'these', 'those']);
        
        const topics = words
            .filter(word => word.length > 3 && !commonWords.has(word))
            .slice(0, 10);

        return topics.length > 0 ? topics : ['concept', 'topic', 'subject'];
    }

    createMockCard(type, topic, notes) {
        const templates = {
            'multiple-choice': {
                question: `What is the main concept related to ${topic}?`,
                options: [
                    `${topic} is the primary focus`,
                    `${topic} is secondary`,
                    `${topic} is not mentioned`,
                    `${topic} is irrelevant`
                ],
                correct: 0,
                explanation: `Based on the notes, ${topic} appears to be a key concept that requires understanding.`
            },
            'true-false': {
                question: `${topic} is an important concept in this study material.`,
                options: ['True', 'False'],
                correct: 0,
                explanation: `This statement is true because ${topic} appears in the context of the study material.`
            },
            'short-answer': {
                question: `Explain the significance of ${topic} in your own words.`,
                options: [],
                correct: 0,
                explanation: `${topic} is significant because it relates to the main themes discussed in the study material.`
            }
        };

        const template = templates[type];
        return {
            id: `card_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            type: type,
            question: template.question,
            options: template.options,
            correctAnswer: template.correct,
            explanation: template.explanation,
            difficulty: null,
            attempts: 0,
            correct: 0
        };
    }

    generateDeckTitle(notes) {
        const words = notes.split(/\s+/).slice(0, 5);
        return words.join(' ').substring(0, 50) + (notes.length > 50 ? '...' : '');
    }

    loadMyDecks() {
        this.loadScreen('decks');
        const decks = StorageManager.getAllDecks();
        const decksGrid = document.getElementById('decks-grid');
        const emptyState = document.getElementById('empty-decks');

        if (decks.length === 0) {
            decksGrid.style.display = 'none';
            emptyState.style.display = 'block';
        } else {
            decksGrid.style.display = 'grid';
            emptyState.style.display = 'none';
            this.renderDecks(decks);
        }
    }

    renderDecks(decks) {
        const decksGrid = document.getElementById('decks-grid');
        decksGrid.innerHTML = '';

        decks.forEach(deck => {
            const deckCard = document.createElement('div');
            deckCard.className = 'deck-card';
            deckCard.innerHTML = `
                <div class="deck-title">${deck.title}</div>
                <div class="deck-meta">
                    <span>${deck.cards.length} cards</span>
                    <span>${this.formatDate(deck.created)}</span>
                </div>
                <div class="deck-preview">${this.getFirstQuestion(deck)}</div>
                <div class="deck-actions">
                    <div class="deck-progress">
                        <div class="progress-bar-fill" style="width: ${deck.progress || 0}%"></div>
                    </div>
                    <span>${Math.round(deck.progress || 0)}%</span>
                </div>
            `;

            deckCard.addEventListener('click', () => {
                this.loadDeck(deck);
            });

            decksGrid.appendChild(deckCard);
        });
    }

    loadDeck(deck) {
        this.currentDeck = deck;
        this.currentCardIndex = 0;
        this.resetStudyProgress();
        this.loadScreen('flashcards');
        FlashcardManager.loadDeck(deck);
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric',
            year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
        });
    }

    getFirstQuestion(deck) {
        if (deck.cards && deck.cards.length > 0) {
            return deck.cards[0].question.substring(0, 100) + '...';
        }
        return 'No questions available';
    }

    resetStudyProgress() {
        this.studyProgress = { easy: 0, medium: 0, hard: 0 };
        this.updateProgressDisplay();
    }

    updateProgressDisplay() {
        document.getElementById('easy-count').textContent = this.studyProgress.easy;
        document.getElementById('medium-count').textContent = this.studyProgress.medium;
        document.getElementById('hard-count').textContent = this.studyProgress.hard;
    }

    rateCard(difficulty) {
        this.studyProgress[difficulty]++;
        this.updateProgressDisplay();
        
        if (this.currentDeck && this.currentDeck.cards[this.currentCardIndex]) {
            this.currentDeck.cards[this.currentCardIndex].difficulty = difficulty;
        }
        
        // Auto-advance to next card after rating
        setTimeout(() => {
            this.nextCard();
        }, 500);
    }

    nextCard() {
        if (this.currentCardIndex < this.currentDeck.cards.length - 1) {
            this.currentCardIndex++;
            FlashcardManager.showCard(this.currentCardIndex);
        }
    }

    previousCard() {
        if (this.currentCardIndex > 0) {
            this.currentCardIndex--;
            FlashcardManager.showCard(this.currentCardIndex);
        }
    }

    toggleCard() {
        FlashcardManager.toggleCard();
    }

    showError(message) {
        const errorElement = document.getElementById('input-error');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.add('show');
        }
    }

    hideError() {
        const errorElement = document.getElementById('input-error');
        if (errorElement) {
            errorElement.classList.remove('show');
        }
    }

    showPremiumModal() {
        const modal = document.getElementById('premium-modal');
        modal.classList.add('active');
    }

    hidePremiumModal() {
        const modal = document.getElementById('premium-modal');
        modal.classList.remove('active');
    }

    async handleSubscription() {
        // In production, this would integrate with IntaSend API
        alert('Subscription feature coming soon! IntaSend integration will be available in the next update.');
        
        // Mock successful subscription for demo
        setTimeout(() => {
            this.hidePremiumModal();
            this.showSuccessMessage('Welcome to Premium! All features unlocked.');
        }, 1000);
    }

    showSuccessMessage(message) {
        // Create and show success notification
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--success-500);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 0.5rem;
            box-shadow: var(--shadow-lg);
            z-index: 1001;
            animation: slideIn 0.3s ease-out;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new AIStudyBuddyApp();
});

// Service Worker registration for PWA
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(() => console.log('SW registered'))
            .catch(() => console.log('SW registration failed'));
    });
}