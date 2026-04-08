import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// --- Golfers ---
export const getGolfers = () => api.get('/golfers').then((r) => r.data);
export const getGolfer = (id) => api.get(`/golfers/${id}`).then((r) => r.data);
export const getRankings = () => api.get('/golfers/rankings').then((r) => r.data);
export const getValueBoard = () => api.get('/golfers/value').then((r) => r.data);

// --- Auction ---
export const getAuctionState = () => api.get('/auction/state').then((r) => r.data);
export const configureAuction = (config) =>
  api.post('/auction/configure', config).then((r) => r.data);
export const recordBid = (bid) =>
  api.post('/auction/bid', bid).then((r) => r.data);
export const undoBid = () => api.post('/auction/undo').then((r) => r.data);
export const resetAuction = () => api.post('/auction/reset').then((r) => r.data);
export const getAlerts = () => api.get('/auction/alerts').then((r) => r.data);

// --- Strategy ---
export const getRecommendations = () =>
  api.get('/strategy/recommendations').then((r) => r.data);
export const getMaxBid = (golferId) =>
  api.get(`/strategy/${golferId}/max-bid`).then((r) => r.data);
export const getAntiConsensus = () =>
  api.get('/strategy/anti-consensus').then((r) => r.data);
export const priceCheck = (golfer_id, current_price) =>
  api.post('/strategy/price-check', { golfer_id, current_price }).then((r) => r.data);
export const getQuickSheet = () =>
  api.get('/strategy/quick-sheet').then((r) => r.data);

// --- Portfolio ---
export const getPortfolio = () => api.get('/portfolio').then((r) => r.data);
export const getPortfolioOptimization = () =>
  api.get('/portfolio/optimization').then((r) => r.data);
export const getExpectedPayout = () =>
  api.get('/portfolio/expected-payout').then((r) => r.data);

// --- Backtest ---
export const getBacktestYears = () =>
  api.get('/backtest/years').then((r) => r.data);
export const runBacktest = (params) =>
  api.post('/backtest/run', params).then((r) => r.data);

// --- Scorecard ---
export const calculateScorecard = (results) =>
  api.post('/scorecard/calculate', { results }).then((r) => r.data);
export const getCompetitors = () =>
  api.get('/auction/competitors').then((r) => r.data);
export const getFieldValue = () =>
  api.get('/auction/field-value').then((r) => r.data);

// --- Odds ---
export const refreshOdds = (apiKey) =>
  api.post('/odds/refresh', { api_key: apiKey || undefined }).then((r) => r.data);

export default api;
