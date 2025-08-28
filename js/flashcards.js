// Flashcard Management System
class FlashcardManager {
    static currentDeck = null;
    static currentCardIndex = 0;
    static isFlipped = false;

    static loadDeck(deck) {
        this.currentDeck = deck;
        this.currentCardIndex = 0;
        this.isFlipped = false;
        
        this.updateDeckInfo();
        this.showCard(0);
        this.bindEvents();
    }

    static updateDeckInfo() {
        document.getElementById('deck-title').textContent = this.currentDeck.title;
        document.getElementById('total-cards').textContent = this.currentDeck.cards.length;
        this.updateProgress();
    }

    static showCard(index) {
        if (!this.currentDeck || !this.currentDeck.cards[index]) return;

        this.currentCardIndex = index;
        const card = this.currentDeck.cards[index];
        
        // Reset card flip state
        this.isFlipped = false;
        const flashcard = document.getElementById('flashcard');
        flashcard.classList.remove('flipped');

        // Update progress indicator
        document.getElementById('current-card').textContent = index + 1;

        // Update navigation buttons
        this.updateNavigationButtons();

        // Populate card content
        this.populateCard(card);
    }

    static populateCard(card) {
        // Front of card (question)
        document.getElementById('question-type').textContent = this.formatQuestionType(card.type);
        document.getElementById('question-text').textContent = card.question;
        
        // Handle options for multiple choice questions
        const optionsContainer = document.getElementById('options-container');
        optionsContainer.innerHTML = '';

        if (card.type === 'multiple-choice' && card.options.length > 0) {
            card.options.forEach((option, index) => {
                const optionElement = document.createElement('div');
                optionElement.className = 'option';
                optionElement.textContent = option;
                optionElement.addEventListener('click', () => this.selectOption(index));
                optionsContainer.appendChild(optionElement);
            });
        } else if (card.type === 'true-false' && card.options.length > 0) {
            card.options.forEach((option, index) => {
                const optionElement = document.createElement('div');
                optionElement.className = 'option';
                optionElement.textContent = option;
                optionElement.addEventListener('click', () => this.selectOption(index));
                optionsContainer.appendChild(optionElement);
            });
        }

        // Back of card (answer)
        const correctAnswer = card.options.length > 0 ? 
            card.options[card.correctAnswer] : 
            'Answer will vary based on your understanding';
            
        document.getElementById('answer-text').textContent = correctAnswer;
        document.getElementById('explanation').textContent = card.explanation;
    }

    static formatQuestionType(type) {
        const typeMap = {
            'multiple-choice': 'Multiple Choice',
            'true-false': 'True/False',
            'short-answer': 'Short Answer'
        };
        return typeMap[type] || 'Question';
    }

    static selectOption(index) {
        // Clear previous selections
        document.querySelectorAll('.option').forEach(option => {
            option.classList.remove('selected');
        });

        // Select clicked option
        const options = document.querySelectorAll('.option');
        if (options[index]) {
            options[index].classList.add('selected');
        }
    }

    static toggleCard() {
        const flashcard = document.getElementById('flashcard');
        this.isFlipped = !this.isFlipped;
        
        if (this.isFlipped) {
            flashcard.classList.add('flipped');
        } else {
            flashcard.classList.remove('flipped');
        }
    }

    static updateNavigationButtons() {
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');

        prevBtn.disabled = this.currentCardIndex === 0;
        nextBtn.disabled = this.currentCardIndex === this.currentDeck.cards.length - 1;

        // Update button text for last card
        if (this.currentCardIndex === this.currentDeck.cards.length - 1) {
            nextBtn.innerHTML = 'Finish <span>✓</span>';
        } else {
            nextBtn.innerHTML = 'Next <span>→</span>';
        }
    }

    static updateProgress() {
        const progress = ((this.currentCardIndex + 1) / this.currentDeck.cards.length) * 100;
        this.currentDeck.progress = progress;
        
        // Save updated progress
        StorageManager.updateDeck(this.currentDeck);
    }

    static bindEvents() {
        // Remove existing event listeners to prevent duplicates
        this.unbindEvents();

        // Card flip event
        document.getElementById('reveal-btn').addEventListener('click', () => {
            this.toggleCard();
        });

        // Navigation events
        document.getElementById('prev-btn').addEventListener('click', () => {
            this.previousCard();
        });

        document.getElementById('next-btn').addEventListener('click', () => {
            this.nextCard();
        });

        // Difficulty rating events
        document.getElementById('easy-btn').addEventListener('click', () => {
            this.rateCard('easy');
        });

        document.getElementById('medium-btn').addEventListener('click', () => {
            this.rateCard('medium');
        });

        document.getElementById('hard-btn').addEventListener('click', () => {
            this.rateCard('hard');
        });

        // Deck action events
        document.getElementById('restart-deck').addEventListener('click', () => {
            this.restartDeck();
        });

        document.getElementById('save-deck').addEventListener('click', () => {
            this.saveDeck();
        });

        // Click card to flip
        document.getElementById('flashcard').addEventListener('click', (e) => {
            // Don't flip if clicking on interactive elements
            if (!e.target.closest('.option') && !e.target.closest('button')) {
                this.toggleCard();
            }
        });
    }

    static unbindEvents() {
        // Create new elements to remove all event listeners
        const elementsToReset = [
            'reveal-btn', 'prev-btn', 'next-btn', 'easy-btn', 
            'medium-btn', 'hard-btn', 'restart-deck', 'save-deck', 'flashcard'
        ];

        elementsToReset.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                const newElement = element.cloneNode(true);
                element.parentNode.replaceChild(newElement, element);
            }
        });
    }

    static previousCard() {
        if (this.currentCardIndex > 0) {
            this.showCard(this.currentCardIndex - 1);
        }
    }

    static nextCard() {
        if (this.currentCardIndex < this.currentDeck.cards.length - 1) {
            this.showCard(this.currentCardIndex + 1);
        } else {
            // Finished deck
            this.completeDeck();
        }
    }

    static rateCard(difficulty) {
        const card = this.currentDeck.cards[this.currentCardIndex];
        card.difficulty = difficulty;
        card.attempts++;
        
        // Update app progress
        if (window.app) {
            window.app.rateCard(difficulty);
        }

        // Save deck with updated rating
        StorageManager.updateDeck(this.currentDeck);

        // Visual feedback
        this.showRatingFeedback(difficulty);
    }

    static showRatingFeedback(difficulty) {
        const button = document.getElementById(`${difficulty}-btn`);
        const originalBg = button.style.backgroundColor;
        
        // Flash the selected button
        button.style.backgroundColor = 'var(--primary-500)';
        button.style.color = 'white';
        
        setTimeout(() => {
            button.style.backgroundColor = originalBg;
            button.style.color = '';
        }, 300);
    }

    static restartDeck() {
        if (confirm('Are you sure you want to restart this deck? Your progress will be reset.')) {
            this.currentCardIndex = 0;
            this.isFlipped = false;
            
            // Reset all card ratings
            this.currentDeck.cards.forEach(card => {
                card.difficulty = null;
                card.attempts = 0;
            });
            
            this.currentDeck.progress = 0;
            StorageManager.updateDeck(this.currentDeck);
            
            // Reset app progress
            if (window.app) {
                window.app.resetStudyProgress();
            }
            
            this.showCard(0);
        }
    }

    static saveDeck() {
        StorageManager.updateDeck(this.currentDeck);
        
        // Show save confirmation
        const saveBtn = document.getElementById('save-deck');
        const originalContent = saveBtn.innerHTML;
        
        saveBtn.innerHTML = '<span>✓</span>';
        saveBtn.style.color = 'var(--success-500)';
        
        setTimeout(() => {
            saveBtn.innerHTML = originalContent;
            saveBtn.style.color = '';
        }, 1000);
    }

    static completeDeck() {
        const totalCards = this.currentDeck.cards.length;
        const ratedCards = this.currentDeck.cards.filter(card => card.difficulty).length;
        const accuracy = this.calculateAccuracy();
        
        // Update deck completion stats
        this.currentDeck.lastStudied = new Date().toISOString();
        this.currentDeck.progress = 100;
        this.currentDeck.completions = (this.currentDeck.completions || 0) + 1;
        
        StorageManager.updateDeck(this.currentDeck);
        
        // Show completion modal/message
        this.showCompletionSummary(totalCards, ratedCards, accuracy);
    }

    static calculateAccuracy() {
        const ratedCards = this.currentDeck.cards.filter(card => card.difficulty);
        if (ratedCards.length === 0) return 0;
        
        const easyCards = ratedCards.filter(card => card.difficulty === 'easy').length;
        const mediumCards = ratedCards.filter(card => card.difficulty === 'medium').length;
        
        // Calculate weighted accuracy (easy = 100%, medium = 70%, hard = 30%)
        const weightedScore = (easyCards * 100 + mediumCards * 70 + (ratedCards.length - easyCards - mediumCards) * 30);
        return Math.round(weightedScore / ratedCards.length);
    }

    static showCompletionSummary(total, rated, accuracy) {
        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>🎉 Deck Completed!</h3>
                    <button class="close-btn" onclick="this.closest('.modal').remove()">&times;</button>
                </div>
                <div class="modal-body">
                    <div style="text-align: center; margin-bottom: 2rem;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">🏆</div>
                        <h4>Great job studying!</h4>
                        <p>You've completed this flashcard deck.</p>
                    </div>
                    <div class="completion-stats" style="display: flex; justify-content: space-around; margin: 2rem 0;">
                        <div style="text-align: center;">
                            <div style="font-size: 2rem; font-weight: bold; color: var(--primary-600);">${total}</div>
                            <div style="font-size: 0.875rem; color: var(--gray-600);">Cards Studied</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 2rem; font-weight: bold; color: var(--success-500);">${accuracy}%</div>
                            <div style="font-size: 0.875rem; color: var(--gray-600);">Accuracy</div>
                        </div>
                    </div>
                </div>
                <div class="modal-actions">
                    <button class="primary-btn" onclick="this.closest('.modal').remove(); window.app?.loadMyDecks();" style="width: 100%;">
                        Back to My Decks
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Auto-remove after 5 seconds if not manually closed
        setTimeout(() => {
            if (modal.parentNode) {
                modal.remove();
            }
        }, 5000);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FlashcardManager;
}