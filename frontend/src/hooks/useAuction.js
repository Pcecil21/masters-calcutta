import { useContext } from 'react';
import { AuctionContext } from '../context/AuctionContext';

/**
 * Convenience hook to consume AuctionContext.
 */
export function useAuction() {
  const ctx = useContext(AuctionContext);
  if (!ctx) {
    throw new Error('useAuction must be used within an <AuctionProvider>');
  }
  return ctx;
}
