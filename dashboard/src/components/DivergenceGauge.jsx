import React, { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import axios from 'axios';

const DivergenceGauge = ({ symbol = 'BTCUSDT' }) => {
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchDivergence = async () => {
      try {
        const response = await axios.get(`http://localhost:8001/analytics/divergence/${symbol}`, {
          headers: { 'X-API-Key': 'ak_58bb132b5b975898f1a11858d811d01438391693bb363204ad53e41dba4618c2' }
        });
        setData(response.data);
      } catch (err) {
        console.error("Failed to fetch divergence", err);
      }
    };
    
    fetchDivergence();
    const interval = setInterval(fetchDivergence, 10000); // 10s
    return () => clearInterval(interval);
  }, [symbol]);

  // Divergence > 0 is bullish (Green, Right), < 0 is bearish (Red, Left).
  const value = data ? Math.max(-3, Math.min(3, data.divergence)) : 0;
  // Map value [-3, 3] to angle [180, 0]
  const needleAngle = 180 - ((value + 3) / 6) * 180;
  
  const RADIAN = Math.PI / 180;
  const needleLen = 50;
  const needleX = 100 + needleLen * Math.cos(needleAngle * RADIAN);
  const needleY = 100 - needleLen * Math.sin(needleAngle * RADIAN);

  return (
    <div className="panel" style={{height: '350px', display: 'flex', flexDirection: 'column'}}>
      <div className="panel-header">Sentiment-Price Divergence</div>
      <div className="panel-content" style={{flex: 1, position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
        {!data ? (
           <div style={{color: 'var(--text-secondary)'}}>Loading gauge...</div>
        ) : (
          <>
            <div style={{width: '200px', height: '120px'}}>
              <svg viewBox="0 0 200 120" style={{width: '100%', height: '100%'}}>
                {/* Background arcs */}
                {/* Red arc (Bearish): from 180 deg to 135 deg (-3 to -1.5) */}
                <path d="M 20 100 A 80 80 0 0 1 43.4 43.4 L 100 100 Z" fill="var(--color-down)" opacity="0.7" />
                {/* Gray arc (Neutral): from 135 deg to 45 deg (-1.5 to 1.5) */}
                <path d="M 43.4 43.4 A 80 80 0 0 1 156.6 43.4 L 100 100 Z" fill="#555" opacity="0.5" />
                {/* Green arc (Bullish): from 45 deg to 0 deg (1.5 to 3) */}
                <path d="M 156.6 43.4 A 80 80 0 0 1 180 100 L 100 100 Z" fill="var(--color-up)" opacity="0.7" />
                
                {/* Inner cutout - Fix the path so it accurately cuts out the center */}
                <path d="M 40 100 A 60 60 0 0 1 160 100 Z" fill="var(--bg-panel)" />

                {/* Needle base point & Needle */}
                <circle cx="100" cy="100" r="10" fill="#222" stroke="#444" strokeWidth="2" />
                <line x1="100" y1="100" x2={needleX} y2={needleY} stroke="#fff" strokeWidth="3" />
                <circle cx="100" cy="100" r="4" fill="#fff" />
              </svg>
            </div>
            <div style={{textAlign: 'center', marginTop: '16px'}}>
              <h2 className={data.status === 'bearish_divergence' ? 'text-down' : data.status === 'bullish_divergence' ? 'text-up' : ''} style={{margin: '0 0 8px 0'}}>
                {data.status.replace('_', ' ').toUpperCase()}
              </h2>
              <p className="mono" style={{margin: 0, fontSize: '1.2rem', color: 'var(--text-primary)'}}>Score: {data.divergence > 0 ? '+' : ''}{data.divergence.toFixed(2)}</p>
              <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '8px', maxWidth: '200px', margin: '8px auto'}}>
                Price Z: {data.price_z ? data.price_z.toFixed(2) : '0.00'} | Sent Z: {data.sentiment_z ? data.sentiment_z.toFixed(2) : '0.00'}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default DivergenceGauge;
