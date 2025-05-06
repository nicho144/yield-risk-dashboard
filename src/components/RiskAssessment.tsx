import React from 'react';
import { RiskMetrics } from '../../utils/risk-assessor';
import {
    Card,
    CardContent,
    Typography,
    Box,
    CircularProgress,
    Grid,
    Chip
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import WarningIcon from '@mui/icons-material/Warning';

interface RiskAssessmentProps {
    metrics: RiskMetrics;
}

export const RiskAssessment: React.FC<RiskAssessmentProps> = ({ metrics }) => {
    const getRiskColor = (status: string) => {
        switch (status) {
            case 'Risk On':
                return 'success';
            case 'Risk Off':
                return 'error';
            default:
                return 'warning';
        }
    };

    const getTrendIcon = (trend: string) => {
        switch (trend) {
            case 'Up':
                return <TrendingUpIcon color="success" />;
            case 'Down':
                return <TrendingDownIcon color="error" />;
            default:
                return <WarningIcon color="warning" />;
        }
    };

    return (
        <Card sx={{ 
            bgcolor: metrics.riskStatus === 'Risk On' ? '#e8f5e9' : 
                    metrics.riskStatus === 'Risk Off' ? '#ffebee' : '#fff3e0',
            position: 'relative',
            overflow: 'visible'
        }}>
            <CardContent>
                <Grid container spacing={2}>
                    <Grid item xs={12}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Typography variant="h5">
                                Current Risk Status: {metrics.riskStatus}
                            </Typography>
                            {getTrendIcon(metrics.marketTrend)}
                        </Box>
                    </Grid>

                    <Grid item xs={12} md={6}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Typography variant="h6">
                                Risk Score:
                            </Typography>
                            <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                                <CircularProgress 
                                    variant="determinate" 
                                    value={metrics.riskScore} 
                                    size={60}
                                    color={getRiskColor(metrics.riskStatus) as any}
                                />
                                <Box
                                    sx={{
                                        top: 0,
                                        left: 0,
                                        bottom: 0,
                                        right: 0,
                                        position: 'absolute',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                    }}
                                >
                                    <Typography variant="caption" component="div" color="text.secondary">
                                        {`${Math.round(metrics.riskScore)}%`}
                                    </Typography>
                                </Box>
                            </Box>
                        </Box>
                    </Grid>

                    <Grid item xs={12} md={6}>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                            <Typography>
                                Yield Curve Slope (10Y-2Y): {metrics.yieldCurveSlope.toFixed(2)}%
                            </Typography>
                            <Typography>
                                Real Rates Average: {metrics.realRatesAverage.toFixed(2)}%
                            </Typography>
                        </Box>
                    </Grid>

                    <Grid item xs={12}>
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                            <Chip 
                                label={`Volatility: ${metrics.volatilityStatus}`}
                                color={metrics.volatilityStatus === 'High' ? 'error' : 
                                       metrics.volatilityStatus === 'Low' ? 'success' : 'default'}
                            />
                            <Chip 
                                label={`Market Trend: ${metrics.marketTrend}`}
                                color={metrics.marketTrend === 'Up' ? 'success' : 
                                       metrics.marketTrend === 'Down' ? 'error' : 'default'}
                            />
                        </Box>
                    </Grid>
                </Grid>
            </CardContent>
        </Card>
    );
}; 