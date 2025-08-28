// Local Storage Management System
class StorageManager {
    static DECK_KEY = 'ai_study_buddy_decks';
    static USER_KEY = 'ai_study_buddy_user';
    static SETTINGS_KEY = 'ai_study_buddy_settings';

    // Deck Management
    static saveDeck(deck) {
        try {
            const decks = this.getAllDecks();
            
            // Check if deck already exists
            const existingIndex = decks.findIndex(d => d.id === deck.id);
            
            if (existingIndex >= 0) {
                decks[existingIndex] = { ...decks[existingIndex], ...deck };
            } else {
                decks.push(deck);
            }
            
            localStorage.setItem(this.DECK_KEY, JSON.stringify(decks));
            return true;
        } catch (error) {
            console.error('Failed to save deck:', error);
            return false;
        }
    }

    static getAllDecks() {
        try {
            const decks = localStorage.getItem(this.DECK_KEY);
            return decks ? JSON.parse(decks) : [];
        } catch (error) {
            console.error('Failed to load decks:', error);
            return [];
        }
    }

    static getDeckById(id) {
        const decks = this.getAllDecks();
        return decks.find(deck => deck.id === id);
    }

    static updateDeck(updatedDeck) {
        return this.saveDeck(updatedDeck);
    }

    static deleteDeck(deckId) {
        try {
            const decks = this.getAllDecks();
            const filteredDecks = decks.filter(deck => deck.id !== deckId);
            localStorage.setItem(this.DECK_KEY, JSON.stringify(filteredDecks));
            return true;
        } catch (error) {
            console.error('Failed to delete deck:', error);
            return false;
        }
    }

    // User Data Management
    static saveUserData(userData) {
        try {
            const existingData = this.getUserData();
            const mergedData = { ...existingData, ...userData };
            localStorage.setItem(this.USER_KEY, JSON.stringify(mergedData));
            return true;
        } catch (error) {
            console.error('Failed to save user data:', error);
            return false;
        }
    }

    static getUserData() {
        try {
            const userData = localStorage.getItem(this.USER_KEY);
            return userData ? JSON.parse(userData) : {
                id: this.generateUserId(),
                createdAt: new Date().toISOString(),
                studySessions: 0,
                totalCards: 0,
                totalDecks: 0,
                averageAccuracy: 0,
                longestStreak: 0,
                currentStreak: 0,
                isPremium: false,
                lastActivity: new Date().toISOString()
            };
        } catch (error) {
            console.error('Failed to load user data:', error);
            return this.getDefaultUserData();
        }
    }

    static getDefaultUserData() {
        return {
            id: this.generateUserId(),
            createdAt: new Date().toISOString(),
            studySessions: 0,
            totalCards: 0,
            totalDecks: 0,
            averageAccuracy: 0,
            longestStreak: 0,
            currentStreak: 0,
            isPremium: false,
            lastActivity: new Date().toISOString()
        };
    }

    static generateUserId() {
        return 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // Settings Management
    static saveSettings(settings) {
        try {
            const existingSettings = this.getSettings();
            const mergedSettings = { ...existingSettings, ...settings };
            localStorage.setItem(this.SETTINGS_KEY, JSON.stringify(mergedSettings));
            return true;
        } catch (error) {
            console.error('Failed to save settings:', error);
            return false;
        }
    }

    static getSettings() {
        try {
            const settings = localStorage.getItem(this.SETTINGS_KEY);
            return settings ? JSON.parse(settings) : this.getDefaultSettings();
        } catch (error) {
            console.error('Failed to load settings:', error);
            return this.getDefaultSettings();
        }
    }

    static getDefaultSettings() {
        return {
            theme: 'light',
            language: 'en',
            autoAdvanceCards: false,
            showExplanations: true,
            studyReminders: false,
            soundEffects: true,
            keyboardNavigation: true,
            cardTransitionSpeed: 'normal',
            defaultDifficulty: 'medium',
            cardsPerSession: 5
        };
    }

    // Analytics and Stats
    static recordStudySession(deckId, sessionData) {
        try {
            const userData = this.getUserData();
            userData.studySessions++;
            userData.totalCards += sessionData.cardsStudied || 0;
            userData.lastActivity = new Date().toISOString();
            
            // Update accuracy
            if (sessionData.accuracy !== undefined) {
                const totalAccuracy = userData.averageAccuracy * (userData.studySessions - 1);
                userData.averageAccuracy = Math.round((totalAccuracy + sessionData.accuracy) / userData.studySessions);
            }
            
            // Update streak
            if (this.isConsecutiveDay(userData.lastActivity)) {
                userData.currentStreak++;
                userData.longestStreak = Math.max(userData.longestStreak, userData.currentStreak);
            } else {
                userData.currentStreak = 1;
            }
            
            this.saveUserData(userData);
            
            // Save session details
            this.saveSessionHistory({
                id: Date.now().toString(),
                deckId: deckId,
                timestamp: new Date().toISOString(),
                ...sessionData
            });
            
            return true;
        } catch (error) {
            console.error('Failed to record study session:', error);
            return false;
        }
    }

    static saveSessionHistory(session) {
        try {
            const sessions = this.getSessionHistory();
            sessions.push(session);
            
            // Keep only last 100 sessions to prevent storage bloat
            if (sessions.length > 100) {
                sessions.splice(0, sessions.length - 100);
            }
            
            localStorage.setItem('ai_study_buddy_sessions', JSON.stringify(sessions));
            return true;
        } catch (error) {
            console.error('Failed to save session history:', error);
            return false;
        }
    }

    static getSessionHistory() {
        try {
            const sessions = localStorage.getItem('ai_study_buddy_sessions');
            return sessions ? JSON.parse(sessions) : [];
        } catch (error) {
            console.error('Failed to load session history:', error);
            return [];
        }
    }

    static isConsecutiveDay(lastActivity) {
        const lastDate = new Date(lastActivity);
        const today = new Date();
        const diffTime = Math.abs(today - lastDate);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays <= 1;
    }

    // Data Export/Import
    static exportAllData() {
        try {
            return {
                decks: this.getAllDecks(),
                userData: this.getUserData(),
                settings: this.getSettings(),
                sessions: this.getSessionHistory(),
                exportDate: new Date().toISOString(),
                version: '1.0'
            };
        } catch (error) {
            console.error('Failed to export data:', error);
            return null;
        }
    }

    static importData(data) {
        try {
            if (data.decks) {
                localStorage.setItem(this.DECK_KEY, JSON.stringify(data.decks));
            }
            if (data.userData) {
                localStorage.setItem(this.USER_KEY, JSON.stringify(data.userData));
            }
            if (data.settings) {
                localStorage.setItem(this.SETTINGS_KEY, JSON.stringify(data.settings));
            }
            if (data.sessions) {
                localStorage.setItem('ai_study_buddy_sessions', JSON.stringify(data.sessions));
            }
            return true;
        } catch (error) {
            console.error('Failed to import data:', error);
            return false;
        }
    }

    // Storage Management
    static getStorageUsage() {
        let totalSize = 0;
        for (let key in localStorage) {
            if (localStorage.hasOwnProperty(key) && key.startsWith('ai_study_buddy')) {
                totalSize += localStorage[key].length;
            }
        }
        return {
            bytes: totalSize,
            kb: Math.round(totalSize / 1024 * 100) / 100,
            mb: Math.round(totalSize / (1024 * 1024) * 100) / 100
        };
    }

    static clearAllData() {
        try {
            const keys = Object.keys(localStorage).filter(key => key.startsWith('ai_study_buddy'));
            keys.forEach(key => localStorage.removeItem(key));
            return true;
        } catch (error) {
            console.error('Failed to clear data:', error);
            return false;
        }
    }

    static isStorageAvailable() {
        try {
            const test = '__storage_test__';
            localStorage.setItem(test, test);
            localStorage.removeItem(test);
            return true;
        } catch (error) {
            return false;
        }
    }

    // Data Migration
    static migrateData() {
        try {
            const currentVersion = this.getUserData().dataVersion || '1.0';
            
            // Add future migration logic here
            switch (currentVersion) {
                case '1.0':
                    // Current version, no migration needed
                    break;
                default:
                    console.log('Unknown data version:', currentVersion);
            }
            
            return true;
        } catch (error) {
            console.error('Data migration failed:', error);
            return false;
        }
    }

    // Backup and Sync (for future cloud integration)
    static createBackup() {
        const data = this.exportAllData();
        if (!data) return null;
        
        const backup = {
            ...data,
            backupId: Date.now().toString(),
            deviceId: this.getUserData().id
        };
        
        return JSON.stringify(backup);
    }

    static restoreFromBackup(backupString) {
        try {
            const backup = JSON.parse(backupString);
            return this.importData(backup);
        } catch (error) {
            console.error('Failed to restore from backup:', error);
            return false;
        }
    }
}

// Initialize storage and perform any necessary migrations
document.addEventListener('DOMContentLoaded', () => {
    if (StorageManager.isStorageAvailable()) {
        StorageManager.migrateData();
        
        // Update user activity
        const userData = StorageManager.getUserData();
        userData.lastActivity = new Date().toISOString();
        StorageManager.saveUserData(userData);
    } else {
        console.warn('Local storage is not available. Some features may not work properly.');
    }
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StorageManager;
}