class WebSocketManager {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.listeners = new Map();
        this.isConnecting = false;
        this.lastPing = null;
    }

    // Initialize WebSocket connection
    connect() {
        if (this.socket || this.isConnecting) return;

        this.isConnecting = true;
        const wsUrl = config.API_ENDPOINTS.BACKEND.replace('http', 'ws');

        try {
            this.socket = new WebSocket(wsUrl);
            this.setupEventHandlers();
        } catch (error) {
            errorHandler.handleWebSocketError(error);
            this.handleReconnect();
        }
    }

    // Set up WebSocket event handlers
    setupEventHandlers() {
        this.socket.onopen = () => {
            this.isConnecting = false;
            this.reconnectAttempts = 0;
            this.lastPing = Date.now();
            this.startPingInterval();
            this.notifyListeners('connect');
        };

        this.socket.onclose = () => {
            this.isConnecting = false;
            this.notifyListeners('disconnect');
            this.handleReconnect();
        };

        this.socket.onerror = (error) => {
            errorHandler.handleWebSocketError(error);
            this.notifyListeners('error', error);
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.notifyListeners('message', data);
            } catch (error) {
                errorHandler.handleError(error, 'WebSocket message parsing');
            }
        };
    }

    // Handle reconnection
    handleReconnect() {
        if (this.reconnectAttempts >= config.WS_CONFIG.RECONNECT_ATTEMPTS) {
            errorHandler.handleError(
                new Error('Maximum reconnection attempts reached'),
                'WebSocket reconnection'
            );
            return;
        }

        this.reconnectAttempts++;
        setTimeout(() => {
            this.connect();
        }, config.WS_CONFIG.RECONNECT_INTERVAL * this.reconnectAttempts);
    }

    // Start ping interval
    startPingInterval() {
        setInterval(() => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.socket.send(JSON.stringify({ type: 'ping' }));
                this.lastPing = Date.now();
            }
        }, config.WS_CONFIG.PING_INTERVAL);
    }

    // Add event listener
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(callback);
        return () => this.off(event, callback);
    }

    // Remove event listener
    off(event, callback) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).delete(callback);
        }
    }

    // Notify all listeners for an event
    notifyListeners(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    errorHandler.handleError(error, 'WebSocket listener');
                }
            });
        }
    }

    // Send message
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        } else {
            errorHandler.handleError(
                new Error('WebSocket is not connected'),
                'WebSocket send'
            );
        }
    }

    // Close connection
    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }

    // Get connection status
    getStatus() {
        if (!this.socket) return 'disconnected';
        switch (this.socket.readyState) {
            case WebSocket.CONNECTING: return 'connecting';
            case WebSocket.OPEN: return 'connected';
            case WebSocket.CLOSING: return 'closing';
            case WebSocket.CLOSED: return 'disconnected';
            default: return 'unknown';
        }
    }

    // Check if connection is healthy
    isHealthy() {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            return false;
        }

        // Check if we've received a ping recently
        if (this.lastPing && Date.now() - this.lastPing > config.WS_CONFIG.PING_INTERVAL * 2) {
            return false;
        }

        return true;
    }
}

// Create singleton instance
const wsManager = new WebSocketManager();

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = wsManager;
} else {
    window.wsManager = wsManager;
} 