// API Service for backend communication
class APIService {
    constructor() {
        this.baseURL = 'http://127.0.0.1:5000/api';
        this.headers = {
            'Content-Type': 'application/json',
        };
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            credentials: 'include', // Include cookies for session management
            headers: this.headers,
            ...options
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    }

    // User Management
    async createUser(userData = {}) {
        return this.request('/users', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    }

    async getUserStats() {
        return this.request('/user/stats');
    }

    // Flashcard Generation
    async generateFlashcards(notes) {
        return this.request('/generate-flashcards', {
            method: 'POST',
            body: JSON.stringify({ notes })
        });
    }

    // Deck Management
    async getUserDecks() {
        return this.request('/decks');
    }

    async getDeck(deckId) {
        return this.request(`/decks/${deckId}`);
    }

    async updateDeck(deckId, updates) {
        return this.request(`/decks/${deckId}`, {
            method: 'PUT',
            body: JSON.stringify(updates)
        });
    }

    // Study Sessions
    async startStudySession(deckId, deviceType = 'web') {
        return this.request('/study-session', {
            method: 'POST',
            body: JSON.stringify({ 
                deck_id: deckId,
                device_type: deviceType
            })
        });
    }

    async completeStudySession(sessionId, sessionData) {
        return this.request(`/study-session/${sessionId}/complete`, {
            method: 'POST',
            body: JSON.stringify(sessionData)
        });
    }

    async recordCardStudy(cardId, isCorrect, difficulty) {
        return this.request(`/cards/${cardId}/study`, {
            method: 'POST',
            body: JSON.stringify({
                is_correct: isCorrect,
                difficulty: difficulty
            })
        });
    }

    // Premium Features
    async upgradeToPremium(paymentMethod = 'card', subscriptionType = 'monthly') {
        return this.request('/premium/upgrade', {
            method: 'POST',
            body: JSON.stringify({
                payment_method: paymentMethod,
                subscription_type: subscriptionType
            })
        });
    }

    // Health Check
    async healthCheck() {
        return this.request('/health');
    }
}

// Create global API instance
window.apiService = new APIService();

// Test backend connectivity on load
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const health = await window.apiService.healthCheck();
        console.log('✅ Backend connected:', health);
        
        // Create user session if none exists
        try {
            await window.apiService.createUser();
            console.log('✅ User session initialized');
        } catch (error) {
            console.log('ℹ️ User session already exists or creation failed:', error.message);
        }
    } catch (error) {
        console.error('❌ Backend connection failed:', error);
        console.log('💡 Make sure Flask backend is running on port 5000');
        
        // Show connection error to user
        const errorBanner = document.createElement('div');
        errorBanner.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #fee2e2;
            color: #dc2626;
            padding: 1rem;
            text-align: center;
            z-index: 1000;
            border-bottom: 1px solid #fecaca;
        `;
        errorBanner.innerHTML = `
            <strong>Backend Offline:</strong> 
            Some features may not work. Please start the Flask backend server.
        `;
        document.body.prepend(errorBanner);
    }
});