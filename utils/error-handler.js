class ErrorHandler {
    constructor() {
        this.errors = [];
        this.maxErrors = 100;
        this.listeners = new Set();
    }

    // Add error to the list and notify listeners
    handleError(error, context = '') {
        const errorObj = {
            timestamp: new Date().toISOString(),
            message: error.message || 'Unknown error',
            context,
            stack: error.stack,
            type: error.name || 'Error'
        };

        this.errors.unshift(errorObj);
        if (this.errors.length > this.maxErrors) {
            this.errors.pop();
        }

        // Notify all listeners
        this.notifyListeners(errorObj);

        // Log to console in development
        if (process.env.NODE_ENV !== 'production') {
            console.error(`[${errorObj.timestamp}] ${errorObj.context}: ${errorObj.message}`);
        }

        return errorObj;
    }

    // Add error listener
    addListener(callback) {
        this.listeners.add(callback);
        return () => this.listeners.delete(callback);
    }

    // Notify all listeners
    notifyListeners(error) {
        this.listeners.forEach(callback => {
            try {
                callback(error);
            } catch (e) {
                console.error('Error in error listener:', e);
            }
        });
    }

    // Get all errors
    getErrors() {
        return [...this.errors];
    }

    // Clear all errors
    clearErrors() {
        this.errors = [];
    }

    // Create user-friendly error message
    createUserMessage(error) {
        const messages = {
            'NetworkError': 'Unable to connect to the server. Please check your internet connection.',
            'TimeoutError': 'The request took too long to complete. Please try again.',
            'APIError': 'There was an error fetching data. Please try again later.',
            'ValidationError': 'The data received was invalid. Please try again.',
            'default': 'An unexpected error occurred. Please try again later.'
        };

        return messages[error.type] || messages.default;
    }

    // Handle API errors
    handleApiError(error, api) {
        const context = `API Error (${api})`;
        const errorObj = this.handleError(error, context);

        // Add specific handling for different API errors
        switch (api) {
            case 'FRED':
                if (error.message.includes('API key')) {
                    return this.handleError(new Error('Invalid FRED API key'), context);
                }
                break;
            case 'NASDAQ':
                if (error.message.includes('rate limit')) {
                    return this.handleError(new Error('Nasdaq API rate limit exceeded'), context);
                }
                break;
            case 'NEWS':
                if (error.message.includes('unauthorized')) {
                    return this.handleError(new Error('Invalid News API key'), context);
                }
                break;
        }

        return errorObj;
    }

    // Handle WebSocket errors
    handleWebSocketError(error) {
        const context = 'WebSocket Error';
        const errorObj = this.handleError(error, context);

        // Add specific handling for WebSocket errors
        if (error.message.includes('connection refused')) {
            return this.handleError(new Error('Unable to connect to real-time updates'), context);
        }

        return errorObj;
    }
}

// Create singleton instance
const errorHandler = new ErrorHandler();

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = errorHandler;
} else {
    window.errorHandler = errorHandler;
} 