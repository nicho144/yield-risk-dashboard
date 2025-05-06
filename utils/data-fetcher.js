class DataFetcher {
    constructor() {
        this.cache = new Map();
        this.pendingRequests = new Map();
        this.retryAttempts = new Map();
    }

    // Fetch data with caching and retry logic
    async fetch(url, options = {}) {
        const {
            cacheKey = url,
            ttl = config.CACHE.TTL * 1000,
            retries = 3,
            retryDelay = 1000,
            api = 'BACKEND'
        } = options;

        // Check cache first
        const cached = this.getCached(cacheKey);
        if (cached) {
            return cached;
        }

        // Check if there's a pending request
        if (this.pendingRequests.has(cacheKey)) {
            return this.pendingRequests.get(cacheKey);
        }

        // Create new request
        const request = this.makeRequest(url, options, retries, retryDelay, api);
        this.pendingRequests.set(cacheKey, request);

        try {
            const response = await request;
            this.setCached(cacheKey, response, ttl);
            return response;
        } finally {
            this.pendingRequests.delete(cacheKey);
        }
    }

    // Make HTTP request with retry logic
    async makeRequest(url, options, maxRetries, retryDelay, api) {
        let attempt = 0;
        
        while (attempt <= maxRetries) {
            try {
                // Check rate limit
                if (!this.checkRateLimit(api)) {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    continue;
                }

                const response = await fetch(url, {
                    ...options,
                    headers: {
                        'Content-Type': 'application/json',
                        ...options.headers
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                this.retryAttempts.delete(url);
                return data;

            } catch (error) {
                attempt++;
                this.retryAttempts.set(url, attempt);

                if (attempt > maxRetries) {
                    errorHandler.handleApiError(error, api);
                    throw error;
                }

                await new Promise(resolve => 
                    setTimeout(resolve, retryDelay * attempt)
                );
            }
        }
    }

    // Check rate limit for API
    checkRateLimit(api) {
        const limit = config.RATE_LIMITS[api];
        const now = Date.now();
        const requests = this.retryAttempts.get(api) || [];
        
        // Remove old requests
        const recentRequests = requests.filter(time => now - time < 60000);
        this.retryAttempts.set(api, recentRequests);

        return recentRequests.length < limit;
    }

    // Get cached data
    getCached(key) {
        const cached = this.cache.get(key);
        if (!cached) return null;

        if (Date.now() > cached.expiry) {
            this.cache.delete(key);
            return null;
        }

        return cached.data;
    }

    // Set cached data
    setCached(key, data, ttl) {
        this.cache.set(key, {
            data,
            expiry: Date.now() + ttl
        });

        // Clean up old cache entries
        this.cleanCache();
    }

    // Clean up old cache entries
    cleanCache() {
        const now = Date.now();
        for (const [key, value] of this.cache.entries()) {
            if (now > value.expiry) {
                this.cache.delete(key);
            }
        }
    }

    // Fetch FRED data
    async fetchFredData(seriesId, days = 1) {
        const url = `${config.API_ENDPOINTS.FRED}/series/observations?` +
            `series_id=${seriesId}&` +
            `api_key=${config.FRED_API_KEY}&` +
            `file_type=json&` +
            `sort_order=desc&` +
            `limit=${days + 1}`;

        return this.fetch(url, {
            cacheKey: `fred_${seriesId}`,
            api: 'FRED'
        });
    }

    // Fetch Nasdaq data
    async fetchNasdaqData(dataset, params = {}) {
        const url = `${config.API_ENDPOINTS.NASDAQ}/datasets/${dataset}?` +
            `api_key=${config.NASDAQ_API_KEY}&` +
            Object.entries(params)
                .map(([key, value]) => `${key}=${value}`)
                .join('&');

        return this.fetch(url, {
            cacheKey: `nasdaq_${dataset}`,
            api: 'NASDAQ'
        });
    }

    // Fetch news data
    async fetchNewsData(country = 'us') {
        const url = `${config.API_ENDPOINTS.NEWS}/top-headlines?` +
            `country=${country}&` +
            `apiKey=${config.NEWS_API_KEY}`;

        return this.fetch(url, {
            cacheKey: `news_${country}`,
            api: 'NEWS'
        });
    }

    // Fetch market data from backend
    async fetchMarketData() {
        const url = `${config.API_ENDPOINTS.BACKEND}/api/market-data`;
        return this.fetch(url, {
            cacheKey: 'market_data',
            ttl: 60000, // 1 minute
            api: 'BACKEND'
        });
    }
}

// Create singleton instance
const dataFetcher = new DataFetcher();

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = dataFetcher;
} else {
    window.dataFetcher = dataFetcher;
} 