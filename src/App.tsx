import React, { useState, useEffect } from 'react';
import { 
  Container, 
  Paper, 
  Typography, 
  TextField, 
  Box,
  Grid,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  IconButton,
  Tooltip as MuiTooltip
} from '@mui/material';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend,
  BarChart,
  Bar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar
} from 'recharts';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import WarningIcon from '@mui/icons-material/Warning';

interface YieldData {
  date: string;
  fedFundsRate: number;
  treasury2Y: number;
  treasury5Y: number;
  treasury10Y: number;
  treasury30Y: number;
  corporateYield: number;
  highYieldSpread: number;
}

interface RiskMetrics {
  yieldCurveSlope: number;
  riskScore: number;
  riskStatus: 'Risk On' | 'Risk Off' | 'Neutral';
  trend: 'Up' | 'Down' | 'Stable';
}

function App() {
  const [yieldData, setYieldData] = useState<YieldData>({
    date: new Date().toLocaleDateString(),
    fedFundsRate: 0,
    treasury2Y: 0,
    treasury5Y: 0,
    treasury10Y: 0,
    treasury30Y: 0,
    corporateYield: 0,
    highYieldSpread: 0
  });

  const [historicalData, setHistoricalData] = useState<YieldData[]>([]);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics>({
    yieldCurveSlope: 0,
    riskScore: 0,
    riskStatus: 'Neutral',
    trend: 'Stable'
  });

  // Calculate risk metrics whenever yield data changes
  useEffect(() => {
    const calculateRiskMetrics = () => {
      const yieldCurveSlope = yieldData.treasury10Y - yieldData.treasury2Y;
      const riskScore = calculateRiskScore(yieldData);
      const riskStatus = determineRiskStatus(riskScore, yieldCurveSlope);
      const trend = determineTrend(historicalData, yieldData);
      
      setRiskMetrics({
        yieldCurveSlope,
        riskScore,
        riskStatus,
        trend
      });

      setHistoricalData(prev => [...prev, yieldData].slice(-20));
    };

    calculateRiskMetrics();
  }, [yieldData, historicalData]);

  const calculateRiskScore = (data: YieldData): number => {
    const yieldCurveComponent = ((data.treasury10Y - data.treasury2Y) + 2) * 25;
    const highYieldComponent = (data.highYieldSpread / 10) * 100;
    const corporateComponent = ((data.corporateYield - data.treasury10Y) / 5) * 100;
    return (yieldCurveComponent * 0.4 + highYieldComponent * 0.3 + corporateComponent * 0.3);
  };

  const determineRiskStatus = (riskScore: number, yieldCurveSlope: number): 'Risk On' | 'Risk Off' | 'Neutral' => {
    if (riskScore > 70 && yieldCurveSlope > 0) return 'Risk On';
    if (riskScore < 30 || yieldCurveSlope < 0) return 'Risk Off';
    return 'Neutral';
  };

  const determineTrend = (historical: YieldData[], current: YieldData): 'Up' | 'Down' | 'Stable' => {
    if (historical.length < 2) return 'Stable';
    const prev = historical[historical.length - 1];
    const diff = current.treasury10Y - prev.treasury10Y;
    if (Math.abs(diff) < 0.1) return 'Stable';
    return diff > 0 ? 'Up' : 'Down';
  };

  const handleYieldChange = (field: keyof YieldData) => (event: React.ChangeEvent<HTMLInputElement>) => {
    setYieldData(prev => ({
      ...prev,
      [field]: Number(event.target.value)
    }));
  };

  // Prepare data for radar chart
  const radarData = [
    { subject: 'Yield Curve', value: riskMetrics.yieldCurveSlope * 10 },
    { subject: 'High Yield', value: yieldData.highYieldSpread * 10 },
    { subject: 'Corporate', value: (yieldData.corporateYield - yieldData.treasury10Y) * 10 },
    { subject: 'Risk Score', value: riskMetrics.riskScore }
  ];

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Yield-Based Risk Analysis Dashboard
      </Typography>
      
      <Grid container spacing={3}>
        {/* Risk Status Card */}
        <Grid item xs={12}>
          <Card sx={{ 
            bgcolor: riskMetrics.riskStatus === 'Risk On' ? '#e8f5e9' : 
                    riskMetrics.riskStatus === 'Risk Off' ? '#ffebee' : '#fff3e0',
            position: 'relative',
            overflow: 'visible'
          }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="h5">
                  Current Risk Status: {riskMetrics.riskStatus}
                </Typography>
                {riskMetrics.trend === 'Up' ? 
                  <TrendingUpIcon color="success" /> : 
                  riskMetrics.trend === 'Down' ? 
                  <TrendingDownIcon color="error" /> : 
                  <WarningIcon color="warning" />
                }
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 2 }}>
                <Typography variant="h6">
                  Risk Score:
                </Typography>
                <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                  <CircularProgress 
                    variant="determinate" 
                    value={riskMetrics.riskScore} 
                    size={60}
                    color={riskMetrics.riskStatus === 'Risk On' ? 'success' : 
                           riskMetrics.riskStatus === 'Risk Off' ? 'error' : 'warning'}
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
                      {`${Math.round(riskMetrics.riskScore)}%`}
                    </Typography>
                  </Box>
                </Box>
              </Box>
              <Typography sx={{ mt: 2 }}>
                Yield Curve Slope (10Y-2Y): {riskMetrics.yieldCurveSlope.toFixed(2)}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Yield Inputs */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Yield Inputs
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Fed Funds Rate (%)"
                    type="number"
                    value={yieldData.fedFundsRate}
                    onChange={handleYieldChange('fedFundsRate')}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="2Y Treasury (%)"
                    type="number"
                    value={yieldData.treasury2Y}
                    onChange={handleYieldChange('treasury2Y')}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="5Y Treasury (%)"
                    type="number"
                    value={yieldData.treasury5Y}
                    onChange={handleYieldChange('treasury5Y')}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="10Y Treasury (%)"
                    type="number"
                    value={yieldData.treasury10Y}
                    onChange={handleYieldChange('treasury10Y')}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="30Y Treasury (%)"
                    type="number"
                    value={yieldData.treasury30Y}
                    onChange={handleYieldChange('treasury30Y')}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Corporate Yield (%)"
                    type="number"
                    value={yieldData.corporateYield}
                    onChange={handleYieldChange('corporateYield')}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="High Yield Spread (%)"
                    type="number"
                    value={yieldData.highYieldSpread}
                    onChange={handleYieldChange('highYieldSpread')}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Risk Analysis Radar Chart */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Risk Analysis
              </Typography>
              <Box sx={{ height: 400 }}>
                <RadarChart outerRadius={150} width={500} height={400} data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="subject" />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} />
                  <Radar
                    name="Risk Metrics"
                    dataKey="value"
                    stroke="#8884d8"
                    fill="#8884d8"
                    fillOpacity={0.6}
                  />
                </RadarChart>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Yield Curve Chart */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Yield Curve
            </Typography>
            <Box sx={{ height: 400 }}>
              <LineChart
                width={800}
                height={400}
                data={historicalData}
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="treasury2Y" stroke="#8884d8" name="2Y Treasury" />
                <Line type="monotone" dataKey="treasury5Y" stroke="#82ca9d" name="5Y Treasury" />
                <Line type="monotone" dataKey="treasury10Y" stroke="#ffc658" name="10Y Treasury" />
                <Line type="monotone" dataKey="treasury30Y" stroke="#ff8042" name="30Y Treasury" />
              </LineChart>
            </Box>
          </Paper>
        </Grid>

        {/* Spread Analysis Chart */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Spread Analysis
            </Typography>
            <Box sx={{ height: 400 }}>
              <BarChart
                width={800}
                height={400}
                data={historicalData}
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="highYieldSpread" fill="#8884d8" name="High Yield Spread" />
                <Bar dataKey="corporateYield" fill="#82ca9d" name="Corporate Yield" />
              </BarChart>
            </Box>
          </Paper>
        </Grid>

        {/* Historical Data Table */}
        <Grid item xs={12}>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Fed Funds</TableCell>
                  <TableCell>2Y</TableCell>
                  <TableCell>5Y</TableCell>
                  <TableCell>10Y</TableCell>
                  <TableCell>30Y</TableCell>
                  <TableCell>Corp Yield</TableCell>
                  <TableCell>HY Spread</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {historicalData.map((row: YieldData, index: number) => (
                  <TableRow key={index}>
                    <TableCell>{row.date}</TableCell>
                    <TableCell>{row.fedFundsRate.toFixed(2)}</TableCell>
                    <TableCell>{row.treasury2Y.toFixed(2)}</TableCell>
                    <TableCell>{row.treasury5Y.toFixed(2)}</TableCell>
                    <TableCell>{row.treasury10Y.toFixed(2)}</TableCell>
                    <TableCell>{row.treasury30Y.toFixed(2)}</TableCell>
                    <TableCell>{row.corporateYield.toFixed(2)}</TableCell>
                    <TableCell>{row.highYieldSpread.toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Grid>
      </Grid>
    </Container>
  );
}

export default App; 