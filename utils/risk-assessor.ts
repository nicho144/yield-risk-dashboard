// Types for risk assessment
export interface MarketData {
    treasury2Y: number;
    treasury5Y: number;
    treasury10Y: number;
    treasury30Y: number;
    corporateYield: number;
    highYieldSpread: number;
    vix?: number;
    spy?: number;
    spyPrevious?: number;
    realRates?: {
        '2Y': number;
        '5Y': number;
        '10Y': number;
        '30Y': number;
    };
    impliedRates?: {
        '1M': number;
        '3M': number;
    };
}

export interface RiskMetrics {
    riskScore: number;
    riskStatus: 'Risk On' | 'Risk Off' | 'Neutral';
    yieldCurveSlope: number;
    realRatesAverage: number;
    volatilityStatus: 'High' | 'Low' | 'Normal';
    marketTrend: 'Up' | 'Down' | 'Stable';
}

export class RiskAssessor {
    private static readonly RISK_THRESHOLDS = {
        HIGH: 70,
        LOW: 30,
        VIX_HIGH: 25,
        VIX_LOW: 15
    };

    private static readonly COMPONENT_WEIGHTS = {
        YIELD_CURVE: 0.4,
        HIGH_YIELD: 0.3,
        CORPORATE: 0.3,
        VOLATILITY: 0.2,
        MARKET_TREND: 0.2
    };

    public static calculateRiskMetrics(data: MarketData): RiskMetrics {
        const yieldCurveSlope = data.treasury10Y - data.treasury2Y;
        const riskScore = this.calculateRiskScore(data);
        const realRatesAverage = this.calculateRealRatesAverage(data);
        const volatilityStatus = this.determineVolatilityStatus(data.vix);
        const marketTrend = this.determineMarketTrend(data);
        const riskStatus = this.determineRiskStatus(riskScore, yieldCurveSlope, data);

        return {
            riskScore,
            riskStatus,
            yieldCurveSlope,
            realRatesAverage,
            volatilityStatus,
            marketTrend
        };
    }

    private static calculateRiskScore(data: MarketData): number {
        // Yield Curve Component (40% weight)
        const yieldCurveComponent = ((data.treasury10Y - data.treasury2Y) + 2) * 25;
        
        // High Yield Spread Component (30% weight)
        const highYieldComponent = (data.highYieldSpread / 10) * 100;
        
        // Corporate Spread Component (30% weight)
        const corporateComponent = ((data.corporateYield - data.treasury10Y) / 5) * 100;
        
        // Market Volatility Component (20% weight)
        const volatilityComponent = data.vix ? (100 - (data.vix / 40) * 100) : 50;
        
        // Market Trend Component (20% weight)
        const marketTrendComponent = data.spy && data.spyPrevious ? 
            ((data.spy - data.spyPrevious) / data.spyPrevious) * 100 : 0;

        return (
            yieldCurveComponent * this.COMPONENT_WEIGHTS.YIELD_CURVE +
            highYieldComponent * this.COMPONENT_WEIGHTS.HIGH_YIELD +
            corporateComponent * this.COMPONENT_WEIGHTS.CORPORATE +
            volatilityComponent * this.COMPONENT_WEIGHTS.VOLATILITY +
            marketTrendComponent * this.COMPONENT_WEIGHTS.MARKET_TREND
        );
    }

    private static calculateRealRatesAverage(data: MarketData): number {
        if (!data.realRates) return 0;
        const rates = Object.values(data.realRates);
        return rates.reduce((sum, rate) => sum + rate, 0) / rates.length;
    }

    private static determineVolatilityStatus(vix?: number): 'High' | 'Low' | 'Normal' {
        if (!vix) return 'Normal';
        if (vix > this.RISK_THRESHOLDS.VIX_HIGH) return 'High';
        if (vix < this.RISK_THRESHOLDS.VIX_LOW) return 'Low';
        return 'Normal';
    }

    private static determineMarketTrend(data: MarketData): 'Up' | 'Down' | 'Stable' {
        if (!data.spy || !data.spyPrevious) return 'Stable';
        const change = ((data.spy - data.spyPrevious) / data.spyPrevious) * 100;
        if (Math.abs(change) < 0.1) return 'Stable';
        return change > 0 ? 'Up' : 'Down';
    }

    private static determineRiskStatus(
        riskScore: number, 
        yieldCurveSlope: number, 
        data: MarketData
    ): 'Risk On' | 'Risk Off' | 'Neutral' {
        // Base risk status on score and yield curve
        let baseStatus: 'Risk On' | 'Risk Off' | 'Neutral' = 'Neutral';
        if (riskScore > this.RISK_THRESHOLDS.HIGH && yieldCurveSlope > 0) {
            baseStatus = 'Risk On';
        } else if (riskScore < this.RISK_THRESHOLDS.LOW || yieldCurveSlope < 0) {
            baseStatus = 'Risk Off';
        }

        // Adjust for market volatility
        if (data.vix) {
            if (data.vix > this.RISK_THRESHOLDS.VIX_HIGH) {
                baseStatus = 'Risk Off';
            } else if (data.vix < this.RISK_THRESHOLDS.VIX_LOW) {
                baseStatus = 'Risk On';
            }
        }

        // Adjust for real rates
        const realRatesAverage = this.calculateRealRatesAverage(data);
        if (realRatesAverage < 0) {
            baseStatus = 'Risk Off';
        } else if (realRatesAverage > 0 && baseStatus === 'Neutral') {
            baseStatus = 'Risk On';
        }

        return baseStatus;
    }
} 