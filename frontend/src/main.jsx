import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import ErrorBoundary from './ErrorBoundary';
import { AuctionProvider } from './context/AuctionContext';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuctionProvider>
        <App />
      </AuctionProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
