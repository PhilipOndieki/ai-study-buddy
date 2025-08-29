// Main Application Controller
class AIStudyBuddyApp {
    constructor() {
        this.currentScreen = 'welcome';
        this.currentDeck = null;
        this.currentCardIndex = 0;
        this.currentSession = null;
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
            
            // Show progress animation
            this.simulateAIGeneration();
            
            // Generate flashcards using backend API
            const response = await window.apiService.generateFlashcards(notes);
            
            // Convert API response to frontend format
            const deck = {
                id: response.deck_id,
                title: response.title,
                cards: response.cards,
                created: response.created,
                lastStudied: response.lastStudied,
                progress: response.progress || 0
            };

            // Also save to local storage as backup
            StorageManager.saveDeck(deck);
            
            // Load flashcards screen
            this.currentDeck = deck;
            this.currentCardIndex = 0;
            this.resetStudyProgress();
            
            // Start study session
            try {
                const sessionResponse = await window.apiService.startStudySession(deck.id);
                this.currentSession = sessionResponse;
            } catch (error) {
                console.warn('Failed to start study session:', error);
            }
            
            setTimeout(() => {
                this.loadScreen('flashcards');
                FlashcardManager.loadDeck(deck);
            }, 1000);

        } catch (error) {
            console.error('Error generating flashcards:', error);
            
            // Check if it's a premium limit error
            if (error.message.includes('Free tier limit reached')) {
                this.showPremiumLimitError();
            } else {
                this.showError('Failed to generate flashcards. Please try again.');
            }
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

    async loadMyDecks() {
        this.loadScreen('decks');
        
        try {
            // Try to load from backend first
            const response = await window.apiService.getUserDecks();
            const decks = response.decks || [];
            
            // Merge with local storage as fallback
            const localDecks = StorageManager.getAllDecks();
            const allDecks = this.mergeDecks(decks, localDecks);
            
            const decksGrid = document.getElementById('decks-grid');
            const emptyState = document.getElementById('empty-decks');

            if (allDecks.length === 0) {
                decksGrid.style.display = 'none';
                emptyState.style.display = 'block';
            } else {
                decksGrid.style.display = 'grid';
                emptyState.style.display = 'none';
                this.renderDecks(allDecks);
            }
        } catch (error) {
            console.error('Failed to load decks from backend, using local storage:', error);
            
            // Fallback to local storage
            const localDecks = StorageManager.getAllDecks();
            const decksGrid = document.getElementById('decks-grid');
            const emptyState = document.getElementById('empty-decks');

            if (localDecks.length === 0) {
                decksGrid.style.display = 'none';
                emptyState.style.display = 'block';
            } else {
                decksGrid.style.display = 'grid';
                emptyState.style.display = 'none';
                this.renderDecks(localDecks);
            }
        }
    }

    mergeDecks(backendDecks, localDecks) {
        // Create a map of backend decks by ID
        const backendMap = new Map(backendDecks.map(deck => [deck.id, deck]));
        
        // Start with backend decks
        const merged = [...backendDecks];
        
        // Add local decks that aren't in backend
        localDecks.forEach(localDeck => {
            if (!backendMap.has(localDeck.id)) {
                merged.push(localDeck);
            }
        });
        
        return merged.sort((a, b) => new Date(b.created) - new Date(a.created));
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

    async rateCard(difficulty) {
        this.studyProgress[difficulty]++;
        this.updateProgressDisplay();
        
        if (this.currentDeck && this.currentDeck.cards[this.currentCardIndex]) {
            this.currentDeck.cards[this.currentCardIndex].difficulty = difficulty;
            
            // Record study attempt in backend
            try {
                const card = this.currentDeck.cards[this.currentCardIndex];
                const isCorrect = difficulty === 'easy'; // Simple heuristic
                
                await window.apiService.recordCardStudy(card.id, isCorrect, difficulty);
            } catch (error) {
                console.warn('Failed to record card study:', error);
            }
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

    showPremiumLimitError() {
        const errorElement = document.getElementById('input-error');
        if (errorElement) {
            errorElement.innerHTML = `
                <strong>Free tier limit reached!</strong> 
                You've created 5 decks this month. 
                <button onclick="window.app.showPremiumModal()" style="color: var(--primary-600); text-decoration: underline; background: none; border: none; cursor: pointer;">
                    Upgrade to Premium
                </button> for unlimited decks.
            `;
            errorElement.classList.add('show');
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
        try {
            const subscriptionType = document.querySelector('input[name="subscription"]:checked')?.value || 'monthly';
            const paymentMethod = 'card'; // Default for now
            
            const response = await window.apiService.upgradeToPremium(paymentMethod, subscriptionType);
            
            this.hidePremiumModal();
            this.showSuccessMessage('Welcome to Premium! All features unlocked.');
            
        } catch (error) {
            console.error('Subscription failed:', error);
            this.showError('Subscription failed. Please try again.');
        }
    }

    async completeDeck() {
        if (this.currentSession) {
            try {
                const sessionData = {
                    cards_studied: this.currentDeck.cards.length,
                    cards_correct: this.studyProgress.easy + Math.floor(this.studyProgress.medium * 0.7),
                    accuracy: this.calculateSessionAccuracy(),
                    deck_progress: 100
                };
                
                await window.apiService.completeStudySession(this.currentSession.session_id, sessionData);
                
                // Update deck progress in backend
                await window.apiService.updateDeck(this.currentDeck.id, {
                    progress: 100,
                    last_studied: new Date().toISOString()
                });
                
            } catch (error) {
                console.warn('Failed to complete study session:', error);
            }
        }
        
        // Continue with existing completion logic
        const totalCards = this.currentDeck.cards.length;
        const ratedCards = this.currentDeck.cards.filter(card => card.difficulty).length;
        const accuracy = this.calculateSessionAccuracy();
        
        // Update local deck
        this.currentDeck.lastStudied = new Date().toISOString();
        this.currentDeck.progress = 100;
        this.currentDeck.completions = (this.currentDeck.completions || 0) + 1;
        
        StorageManager.updateDeck(this.currentDeck);
        
        // Show completion modal
        this.showCompletionSummary(totalCards, ratedCards, accuracy);
    }

    calculateSessionAccuracy() {
        const total = this.studyProgress.easy + this.studyProgress.medium + this.studyProgress.hard;
        if (total === 0) return 0;
        
        const weightedScore = (this.studyProgress.easy * 100 + this.studyProgress.medium * 70 + this.studyProgress.hard * 30);
        return Math.round(weightedScore / total);
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

// Enhanced deck completion for FlashcardManager integration
window.addEventListener('deck-completed', async (event) => {
    if (window.app && window.app.completeDeck) {
        await window.app.completeDeck();
    }
});

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