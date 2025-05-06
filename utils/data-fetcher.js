class DataFetcher {
    constructor() {
        this.cache = new Map();
        this.pendingRequests = new Map();
        this.retryAttempts = new Map();
        this.maxRetries = 2; // Reduced retries for faster fallback
        this.cacheTTL = 5 * 60 * 1000; // 5 minutes
        this.preloadQueue = new Set();
        this.isPreloading = false;
        
        // Initialize with default data
        this.initializeDefaultData();
    }

    initializeDefaultData() {
        // Pre-populate cache with default values
        const defaultData = {
            '^VIX': { dataset_data: { data: [[new Date().toISOString(), 20]] } },
            'SPY': { dataset_data: { data: [[new Date().toISOString(), 400]] } },
            'GC=F': { dataset_data: { data: [[new Date().toISOString(), 2000]] } },
            'DX-Y.NYB': { dataset_data: { data: [[new Date().toISOString(), 100]] } }
        };

        Object.entries(defaultData).forEach(([symbol, data]) => {
            this.cache.set(`nasdaq_${symbol}`, {
                data,
                timestamp: Date.now()
            });
        });
    }

    async fetch(url, options = {}) {
        const cacheKey = this.getCacheKey(url, options);
        
        // Return cached data immediately if available
        if (this.cache.has(cacheKey)) {
            const cachedData = this.cache.get(cacheKey);
            if (Date.now() - cachedData.timestamp < this.cacheTTL) {
                return cachedData.data;
            }
        }

        // Return default data immediately while fetching
        const defaultData = this.getDefaultData(url);
        if (defaultData) {
            // Start background fetch
            this.backgroundFetch(url, options, cacheKey);
            return defaultData;
        }

        // If no default data, wait for actual fetch
        return this.makeRequest(url, options);
    }

    async backgroundFetch(url, options, cacheKey) {
        if (this.pendingRequests.has(cacheKey)) {
            return this.pendingRequests.get(cacheKey);
        }

        const request = this.makeRequest(url, options);
        this.pendingRequests.set(cacheKey, request);

        try {
            const data = await request;
            this.cache.set(cacheKey, {
                data,
                timestamp: Date.now()
            });
            return data;
        } finally {
            this.pendingRequests.delete(cacheKey);
        }
    }

    getDefaultData(url) {
        // Return default data based on URL pattern
        if (url.includes('^VIX')) return { dataset_data: { data: [[new Date().toISOString(), 20]] } };
        if (url.includes('SPY')) return { dataset_data: { data: [[new Date().toISOString(), 400]] } };
        if (url.includes('GC=F')) return { dataset_data: { data: [[new Date().toISOString(), 2000]] } };
        if (url.includes('DX-Y.NYB')) return { dataset_data: { data: [[new Date().toISOString(), 100]] } };
        return null;
    }

    async makeRequest(url, options = {}) {
        const retryCount = this.retryAttempts.get(url) || 0;
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

            const response = await fetch(url, {
                ...options,
                signal: controller.signal,
                headers: {
                    'Accept': 'application/json',
                    ...options.headers
                }
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            this.retryAttempts.delete(url);
            return data;
        } catch (error) {
            if (retryCount < this.maxRetries) {
                this.retryAttempts.set(url, retryCount + 1);
                await new Promise(resolve => setTimeout(resolve, Math.pow(2, retryCount) * 500)); // Faster retries
                return this.makeRequest(url, options);
            }
            // Return default data on final failure
            return this.getDefaultData(url);
        }
    }

    // Optimized market data fetch
    async fetchMarketData() {
        const symbols = ['^VIX', 'SPY', 'GC=F', 'DX-Y.NYB'];
        
        // Return cached data immediately if available
        const cachedData = {};
        let hasAllCached = true;
        
        symbols.forEach(symbol => {
            const cacheKey = `nasdaq_${symbol}`;
            if (this.cache.has(cacheKey)) {
                const cached = this.cache.get(cacheKey);
                if (Date.now() - cached.timestamp < this.cacheTTL) {
                    cachedData[symbol] = cached.data;
                } else {
                    hasAllCached = false;
                }
            } else {
                hasAllCached = false;
            }
        });

        if (hasAllCached) {
            return cachedData;
        }

        // Start background fetch for missing data
        const promises = symbols.map(symbol => {
            if (!cachedData[symbol]) {
                return this.fetchNasdaqData(symbol, { limit: 1 })
                    .then(data => {
                        cachedData[symbol] = data;
                        return data;
                    })
                    .catch(() => {
                        // Use default data on error
                        cachedData[symbol] = this.getDefaultData(symbol);
                    });
            }
            return Promise.resolve();
        });

        await Promise.allSettled(promises);
        return cachedData;
    }

    getCacheKey(url, options) {
        return `${url}-${JSON.stringify(options)}`;
    }

    clearCache() {
        this.cache.clear();
    }

    // Specific API methods
    async fetchFredData(seriesId) {
        const url = `${config.API_ENDPOINTS.FRED}/series/observations?` +
            `series_id=${seriesId}&` +
            `api_key=${config.FRED_API_KEY}&` +
            `file_type=json&` +
            `sort_order=desc&` +
            `limit=2`;

        return this.fetch(url);
    }

    async fetchNasdaqData(dataset, params = {}) {
        const url = `${config.API_ENDPOINTS.NASDAQ}/datasets/${dataset}?` +
            `api_key=${config.NASDAQ_API_KEY}&` +
            Object.entries(params)
                .map(([key, value]) => `${key}=${value}`)
                .join('&');

        return this.fetch(url);
    }

    async fetchNewsData() {
        const url = `${config.API_ENDPOINTS.NEWS}/top-headlines?` +
            `country=us&` +
            `apiKey=${config.NEWS_API_KEY}`;

        return this.fetch(url);
    }
}

// Export for both Node.js and browser environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DataFetcher;
} else {
    window.DataFetcher = DataFetcher;
} 