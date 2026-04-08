import React, { createContext, useState, useCallback, useEffect } from 'react';
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [auctionData, alertsData, portfolioData, golfersData] =
        await Promise.all([
          getAuctionState().catch(() => null),
          getAlerts().catch(() => []),
          getPortfolio().catch(() => null),
          getGolfers().catch(() => []),
        ]);
      if (auctionData) setAuction(auctionData);
      setAlerts(alertsData || []);
      if (portfolioData) setPortfolio(portfolioData);
      if (golfersData?.length) setGolfers(golfersData);
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

  const recordBid = useCallback(
    async (bid) => {
      const result = await apiBid(bid);
      await refresh();
      return result;
    },
    [refresh]
  );

  const undoLastBid = useCallback(async () => {
    const result = await apiUndo();
    await refresh();
    return result;
  }, [refresh]);

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
    await refresh();
    return result;
  }, [refresh]);

  const value = {
    auction,
    alerts,
    portfolio,
    golfers,
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
