import React, { createContext, useState, useCallback, useEffect, useRef } from 'react';
import {
  getAuctionState,
  getAlerts,
  getPortfolio,
  getGolfers,
  recordBid as apiBid,
  undoBid as apiUndo,
  configureAuction as apiConfigure,
  resetAuction as apiReset,
} from '../api/client';

export const AuctionContext = createContext(null);

export function AuctionProvider({ children }) {
  const [auction, setAuction] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [portfolio, setPortfolio] = useState(null);
  const [golfers, setGolfers] = useState([]);
  const [bidHistory, setBidHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const golfersLoaded = useRef(false);

  // Poll-friendly refresh: only auction state + alerts each cycle
  const refresh = useCallback(async () => {
    try {
      const promises = [
        getAuctionState().catch(() => null),
        getAlerts().catch(() => []),
      ];
      // Load golfers only on first mount
      if (!golfersLoaded.current) {
        promises.push(getGolfers().catch(() => []));
      }
      const results = await Promise.all(promises);
      const [auctionData, alertsData] = results;
      if (auctionData) setAuction(auctionData);
      setAlerts(alertsData || []);
      if (!golfersLoaded.current && results[2]?.length) {
        setGolfers(results[2]);
        golfersLoaded.current = true;
      }
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const refreshPortfolio = useCallback(async () => {
    try {
      const portfolioData = await getPortfolio().catch(() => null);
      if (portfolioData) setPortfolio(portfolioData);
    } catch (_) {
      // ignore
    }
  }, []);

  const recordBid = useCallback(
    async (bid) => {
      const result = await apiBid(bid);
      // Add returned bid record to local history
      if (result) {
        setBidHistory((prev) => [...prev, result]);
      }
      // Refresh auction state and portfolio after bid
      await Promise.all([refresh(), refreshPortfolio()]);
      return result;
    },
    [refresh, refreshPortfolio]
  );

  const undoLastBid = useCallback(async () => {
    const result = await apiUndo();
    // Remove last bid from local history
    setBidHistory((prev) => prev.slice(0, -1));
    await Promise.all([refresh(), refreshPortfolio()]);
    return result;
  }, [refresh, refreshPortfolio]);

  const configure = useCallback(
    async (config) => {
      const result = await apiConfigure(config);
      await refresh();
      return result;
    },
    [refresh]
  );

  const reset = useCallback(async () => {
    const result = await apiReset();
    setBidHistory([]);
    await refresh();
    return result;
  }, [refresh]);

  const value = {
    auction,
    alerts,
    portfolio,
    golfers,
    bidHistory,
    loading,
    error,
    refresh,
    recordBid,
    undoLastBid,
    configure,
    reset,
  };

  return (
    <AuctionContext.Provider value={value}>{children}</AuctionContext.Provider>
  );
}
