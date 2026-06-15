import React, { useState, useEffect, useRef } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';
import { useOrderBook } from '../hooks/useOrderBook';

const LiquidityHeatmap = ({ symbol = 'BTCUSDT' }) => {
  const { bids, asks, status } = useOrderBook(symbol);
  const [heatmapData, setHeatmapData] = useState([]);
  const lastCaptureTime = useRef(0);

  useEffect(() => {
    // Throttle capture to once per second to avoid overloading Recharts
    const now = Date.now();
    if (now - lastCaptureTime.current < 1000) return;
    if (!bids.length || !asks.length) return;

    lastCaptureTime.current = now;

    // Capture top 15 bids and 15 asks
    const timeStr = new Date(now).toLocaleTimeString([], { hour12: false });
    
    const newPoints = [];
    asks.slice(0, 15).forEach(a => {
      newPoints.push({
        time: timeStr,
        rawTime: now,
        price: a[0],
        size: a[1],
        type: 'ask'
      });
    });

    bids.slice(0, 15).forEach(b => {
      newPoints.push({
        time: timeStr,
        rawTime: now,
        price: b[0],
        size: b[1],
        type: 'bid'
      });
    });

    setHeatmapData(prev => {
      // Keep last 60 seconds of data (60 * 30 = 1800 points max)
      const MAX_HISTORY_MS = 60000;
      const cutoff = now - MAX_HISTORY_MS;
      const filtered = prev.filter(p => p.rawTime > cutoff);
      return [...filtered, ...newPoints];
    });

  }, [bids, asks]);

  // Calculate dynamic domain for Y-Axis
  const yDomain = React.useMemo(() => {
    if (heatmapData.length === 0) return ['auto', 'auto'];
    const prices = heatmapData.map(d => d.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    // Add 1% padding
    return [min * 0.999, max * 1.001];
  }, [heatmapData]);

  // Find max size for ZAxis scale
  const maxSize = React.useMemo(() => {
    if (heatmapData.length === 0) return 10;
    return Math.max(...heatmapData.map(d => d.size));
  }, [heatmapData]);

  return (
    <div className="panel" style={{height: '400px', display: 'flex', flexDirection: 'column'}}>
      <div className="panel-header" style={{display: 'flex', justifyContent: 'space-between'}}>
        <span>Order Book Liquidity Heatmap (60s)</span>
        <div style={{display: 'flex', alignItems: 'center', gap: '6px'}}>
          <span className={`status-dot ${status === 'connected' ? 'status-live' : 'status-offline'}`}></span>
          <span style={{fontSize: '0.75rem', color: 'var(--text-secondary)'}}>{status}</span>
        </div>
      </div>
      <div className="panel-content" style={{flex: 1, padding: 0}}>
        {heatmapData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-highlight)" opacity={0.5} />
              <XAxis 
                dataKey="time" 
                name="Time" 
                stroke="var(--text-secondary)" 
                tick={{fontSize: 11, fontFamily: 'JetBrains Mono'}}
                interval="preserveStartEnd"
                minTickGap={30}
              />
              <YAxis 
                dataKey="price" 
                name="Price" 
                domain={yDomain} 
                stroke="var(--text-secondary)" 
                tick={{fontSize: 11, fontFamily: 'JetBrains Mono'}}
                tickFormatter={val => val.toLocaleString()}
              />
              <ZAxis dataKey="size" range={[10, 400]} name="Volume" />
              <RechartsTooltip 
                cursor={{ strokeDasharray: '3 3' }}
                contentStyle={{ backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                itemStyle={{ fontFamily: 'JetBrains Mono', color: 'var(--text-primary)' }}
                labelStyle={{ display: 'none' }}
                formatter={(value, name, props) => {
                  if (name === 'Price') return [`$${value.toLocaleString()}`, 'Price'];
                  if (name === 'Volume') return [`${value.toFixed(4)} BTC`, 'Liquidity'];
                  return [value, name];
                }}
              />
              <Scatter data={heatmapData} shape="circle" isAnimationActive={false}>
                {heatmapData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={entry.type === 'ask' ? 'var(--color-down)' : 'var(--color-up)'} 
                    fillOpacity={0.6 + (entry.size / maxSize) * 0.4} // Higher volume = more opaque
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        ) : (
          <div style={{height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)'}}>
            Accumulating order book data...
          </div>
        )}
      </div>
    </div>
  );
};

export default LiquidityHeatmap;
