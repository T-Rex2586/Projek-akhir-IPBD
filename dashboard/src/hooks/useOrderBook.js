import { useState, useEffect, useRef } from 'react';

export function useOrderBook(symbol = 'BTCUSDT') {
  const [orderBook, setOrderBook] = useState({
    bids: [],
    asks: [],
    spread: 0,
    spreadPct: 0,
    status: 'connecting',
    lastUpdate: null
  });

  const ws = useRef(null);

  useEffect(() => {
    let reconnectTimer;
    let isMounted = true;

    const connect = () => {
      ws.current = new WebSocket(`wss://data-stream.binance.vision/ws/${symbol.toLowerCase()}@depth20@1000ms`);

      ws.current.onopen = () => {
        if (isMounted) {
          setOrderBook(prev => ({ ...prev, status: 'connected' }));
        }
      };

      ws.current.onmessage = (event) => {
        if (!isMounted) return;
        const data = JSON.parse(event.data);
        if (data.bids && data.asks) {
          const bids = data.bids.map(b => [parseFloat(b[0]), parseFloat(b[1])]);
          const asks = data.asks.map(a => [parseFloat(a[0]), parseFloat(a[1])]);
          
          let spread = 0;
          let spreadPct = 0;
          if (asks.length > 0 && bids.length > 0) {
            spread = asks[0][0] - bids[0][0];
            spreadPct = (spread / asks[0][0]) * 100;
          }

          setOrderBook({
            bids,
            asks,
            spread,
            spreadPct,
            status: 'connected',
            lastUpdate: Date.now()
          });
        }
      };

      ws.current.onclose = () => {
        if (isMounted) {
          setOrderBook(prev => ({ ...prev, status: 'reconnecting' }));
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.current.onerror = (error) => {
        console.error("OrderBook WS Error: ", error);
        if (ws.current) ws.current.close();
      };
    };

    connect();

    return () => {
      isMounted = false;
      clearTimeout(reconnectTimer);
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [symbol]);

  return orderBook;
}
