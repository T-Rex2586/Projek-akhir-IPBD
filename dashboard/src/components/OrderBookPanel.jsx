import React, { useMemo } from 'react';
import { useOrderBook } from '../hooks/useOrderBook';
import OrderBookRow from './OrderBookRow';

const OrderBookPanel = ({ symbol = 'BTCUSDT' }) => {
  const { bids, asks, spread, spreadPct, status } = useOrderBook(symbol);

  const { processedAsks, processedBids, maxTotal } = useMemo(() => {
    let currentAskTotal = 0;
    const procAsks = asks.slice(0, 20).map(a => {
      currentAskTotal += a[1];
      return { price: a[0], size: a[1], total: currentAskTotal };
    });
    
    // Reverse to display highest price at top, lowest at bottom (near spread)
    procAsks.reverse();

    let currentBidTotal = 0;
    const procBids = bids.slice(0, 20).map(b => {
      currentBidTotal += b[1];
      return { price: b[0], size: b[1], total: currentBidTotal };
    });

    const mTotal = Math.max(
      procAsks.length > 0 ? procAsks[0].total : 0, 
      procBids.length > 0 ? procBids[procBids.length - 1].total : 0
    );
    
    return { processedAsks: procAsks, processedBids: procBids, maxTotal: mTotal };
  }, [asks, bids]);

  const formatSpread = (val) => new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val || 0);

  return (
    <div className="panel ob-panel">
      <div className="panel-header">
        <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
          <span>Order Book</span>
          <span className="ob-pair-label">{symbol}</span>
        </div>
        <div style={{display: 'flex', alignItems: 'center', gap: '6px'}}>
          <span className={`status-dot ${status === 'connected' ? 'status-live' : 'status-offline'}`}></span>
          <span style={{fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase'}}>{status}</span>
        </div>
      </div>
      
      <div className="ob-header mono">
        <div className="ob-cell">Price(USD)</div>
        <div className="ob-cell ob-size">Size(BTC)</div>
        <div className="ob-cell ob-total">Total</div>
      </div>

      <div className="ob-content">
        <div className="ob-asks">
          {processedAsks.map(ask => (
            <OrderBookRow 
              key={ask.price} 
              price={ask.price} 
              size={ask.size} 
              total={ask.total} 
              type="ask" 
              maxTotal={maxTotal} 
            />
          ))}
        </div>

        <div className="ob-spread mono">
          <span className={spread > 0 ? 'text-up' : 'text-down'} style={{fontWeight: 600, fontSize: '1.1rem'}}>
            {formatSpread(spread)}
          </span>
          <span style={{color: 'var(--text-secondary)', fontSize: '0.8rem', marginLeft: '8px'}}>
            Spread ({spreadPct.toFixed(3)}%)
          </span>
        </div>

        <div className="ob-bids">
          {processedBids.map(bid => (
            <OrderBookRow 
              key={bid.price} 
              price={bid.price} 
              size={bid.size} 
              total={bid.total} 
              type="bid" 
              maxTotal={maxTotal} 
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default OrderBookPanel;
