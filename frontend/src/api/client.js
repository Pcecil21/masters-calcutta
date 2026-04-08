import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// --- Golfers ---
export const getGolfers = () => api.get('/golfers').then((r) => r.data);
export const getGolfer = (id) => api.get(`/golfers/${id}`).then((r) => r.data);
export const getRankings = () => api.get('/rankings').then((r) => r.data);
export const getValueBoard = () => api.get('/value-board').then((r) => r.data);

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
  api.get(`/strategy/max-bid/${golferId}`).then((r) => r.data);
export const getAntiConsensus = () =>
  api.get('/strategy/anti-consensus').then((r) => r.data);

// --- Portfolio ---
export const getPortfolio = () => api.get('/portfolio').then((r) => r.data);
export const getPortfolioOptimization = () =>
  api.get('/portfolio/optimization').then((r) => r.data);
export const getExpectedPayout = () =>
  api.get('/portfolio/expected-payout').then((r) => r.data);

// --- Backtest ---
export const runBacktest = (params) =>
  api.post('/backtest', params).then((r) => r.data);

export default api;
