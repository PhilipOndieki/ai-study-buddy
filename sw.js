// Service Worker for AI Study Buddy
const CACHE_NAME = 'ai-study-buddy-v1.0.0';
const STATIC_RESOURCES = [
    '/',
    '/index.html',
    '/styles/main.css',
    '/js/app.js',
    '/js/flashcards.js',
    '/js/storage.js',
    '/manifest.json'
];

// Installation event - cache static resources
self.addEventListener('install', (event) => {
    console.log('SW: Install event');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('SW: Caching static resources');
                return cache.addAll(STATIC_RESOURCES);
            })
            .catch((error) => {
                console.error('SW: Failed to cache resources:', error);
            })
    );
    self.skipWaiting();
});

// Activation event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('SW: Activate event');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('SW: Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Fetch event - serve cached resources with network fallback
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Skip external domains
    if (url.origin !== location.origin) {
        return;
    }

    event.respondWith(
        caches.match(request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    console.log('SW: Serving from cache:', request.url);
                    return cachedResponse;
                }

                console.log('SW: Fetching from network:', request.url);
                return fetch(request)
                    .then((response) => {
                        // Don't cache non-successful responses
                        if (!response || response.status !== 200 || response.type !== 'basic') {
                            return response;
                        }

                        // Cache successful responses for static resources
                        if (STATIC_RESOURCES.includes(url.pathname) || url.pathname.match(/\.(css|js|png|jpg|jpeg|gif|ico|svg)$/)) {
                            const responseToCache = response.clone();
                            caches.open(CACHE_NAME)
                                .then((cache) => {
                                    cache.put(request, responseToCache);
                                })
                                .catch((error) => {
                                    console.error('SW: Failed to cache response:', error);
                                });
                        }

                        return response;
                    })
                    .catch((error) => {
                        console.error('SW: Network request failed:', error);
                        
                        // Return offline page for navigation requests
                        if (request.destination === 'document') {
                            return caches.match('/index.html');
                        }
                        
                        throw error;
                    });
            })
    );
});

// Background sync for data persistence (when online)
self.addEventListener('sync', (event) => {
    console.log('SW: Background sync triggered');
    
    if (event.tag === 'sync-study-data') {
        event.waitUntil(syncStudyData());
    }
});

// Push notifications (for study reminders)
self.addEventListener('push', (event) => {
    console.log('SW: Push notification received');
    
    const options = {
        body: event.data ? event.data.text() : 'Time to study! Check your flashcards.',
        icon: '/images/icon-192x192.png',
        badge: '/images/badge-72x72.png',
        vibrate: [200, 100, 200],
        tag: 'study-reminder',
        actions: [
            {
                action: 'study-now',
                title: 'Study Now',
                icon: '/images/action-study.png'
            },
            {
                action: 'dismiss',
                title: 'Dismiss',
                icon: '/images/action-dismiss.png'
            }
        ],
        data: {
            url: '/',
            timestamp: Date.now()
        }
    };

    event.waitUntil(
        self.registration.showNotification('AI Study Buddy', options)
    );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
    console.log('SW: Notification click received');
    
    event.notification.close();

    if (event.action === 'study-now') {
        event.waitUntil(
            self.clients.openWindow('/')
        );
    } else if (event.action === 'dismiss') {
        // Just close the notification
        return;
    } else {
        // Default click - open app
        event.waitUntil(
            self.clients.openWindow('/')
        );
    }
});

// Handle share target
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    if (url.pathname === '/share-notes' && event.request.method === 'POST') {
        event.respondWith(
            (async () => {
                const formData = await event.request.formData();
                const sharedText = formData.get('text') || formData.get('title') || '';
                
                // Redirect to main app with shared content
                const redirectUrl = `/?shared=${encodeURIComponent(sharedText)}`;
                return Response.redirect(redirectUrl, 302);
            })()
        );
    }
});

// Utility functions
async function syncStudyData() {
    try {
        // In a full implementation, this would sync with backend
        console.log('SW: Syncing study data...');
        
        // For now, just log the action
        // In production, this would:
        // 1. Get pending changes from IndexedDB
        // 2. Send to server API
        // 3. Update local data with server response
        // 4. Clear pending changes
        
        return Promise.resolve();
    } catch (error) {
        console.error('SW: Failed to sync study data:', error);
        throw error;
    }
}

// Periodic background sync (if supported)
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'daily-sync') {
        event.waitUntil(syncStudyData());
    }
});

// Error handling
self.addEventListener('error', (event) => {
    console.error('SW: Error occurred:', event.error);
});

self.addEventListener('unhandledrejection', (event) => {
    console.error('SW: Unhandled promise rejection:', event.reason);
    event.preventDefault();
});

// Communication with main thread
self.addEventListener('message', (event) => {
    console.log('SW: Message received:', event.data);
    
    if (event.data && event.data.type) {
        switch (event.data.type) {
            case 'SKIP_WAITING':
                self.skipWaiting();
                break;
            case 'GET_VERSION':
                event.ports[0].postMessage({ version: CACHE_NAME });
                break;
            case 'CLEAR_CACHE':
                caches.delete(CACHE_NAME).then(() => {
                    event.ports[0].postMessage({ success: true });
                });
                break;
            default:
                console.log('SW: Unknown message type:', event.data.type);
        }
    }
});

// Log service worker lifecycle
console.log('SW: Service Worker script loaded');