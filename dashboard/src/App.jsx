import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  ComposedChart, AreaChart, Area, BarChart, Bar, ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell
} from 'recharts';
import OrderBookPanel from './components/OrderBookPanel';
import LiquidityHeatmap from './components/LiquidityHeatmap';
import TopicBubbleChart from './components/TopicBubbleChart';
import DivergenceGauge from './components/DivergenceGauge';

const API_BASE_URL = 'http://localhost:8001';
const API_KEY = 'ak_58bb132b5b975898f1a11858d811d01438391693bb363204ad53e41dba4618c2';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'X-API-Key': API_KEY }
});

function App() {
  const [activeMainTab, setActiveMainTab] = useState('terminal');
  const [isLive, setIsLive] = useState(false);
  const [priceData, setPriceData] = useState([]);
  const [news, setNews] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [stats, setStats] = useState({
    currentPrice: 0, change24h: 0, high24h: 0, low24h: 0, volume24h: 0
  });

  const [prediction, setPrediction] = useState(null);
  const [predError, setPredError] = useState(null);
  const [goldMetrics, setGoldMetrics] = useState([]);

  const fetchData = async () => {
    try {
      const healthRes = await api.get('/health');
      setIsLive(healthRes.data.status === 'healthy');

      const newsRes = await api.get('/news', { params: { limit: 15 } });
      const newsList = newsRes.data || [];
      setNews(newsList);

      const priceRes = await api.get('/prices/BTCUSDT', { params: { hours: 24 } });
      const data = priceRes.data || [];
      if (data.length > 0) {
        const formattedData = data.map(d => {
          const dt = new Date(d.timestamp);
          return {
            ...d,
            timeStr: dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', hour12: false}),
            rawTime: dt.getTime()
          };
        });

        // Overlay news onto price data (News Impact Timeline)
        formattedData.forEach(p => {
          const pTime = p.rawTime;
          // Find news within a close time window (e.g. 5 minutes = 300000ms)
          const matchingNews = newsList.filter(n => Math.abs(new Date(n.published_at).getTime() - pTime) < 300000);
          if (matchingNews.length > 0) {
             p.newsEvent = matchingNews[0];
             p.newsSentiment = matchingNews[0].sentiment_label === 'positive' ? 1 : matchingNews[0].sentiment_label === 'negative' ? -1 : 0;
             p.newsPrice = p.price; 
          }
        });

        setPriceData(formattedData);

        const currentPrice = data[data.length - 1].price;
        const firstPrice = data[0].price;
        const change = ((currentPrice - firstPrice) / firstPrice) * 100;
        const prices = data.map(d => d.price);
        const volumes = data.map(d => d.volume || 0);

        setStats({
          currentPrice,
          change24h: change,
          high24h: Math.max(...prices),
          low24h: Math.min(...prices),
          volume24h: volumes.reduce((a, b) => a + b, 0)
        });
      }

      const anomRes = await api.get('/anomalies', { params: { hours: 24 } });
      setAnomalies(anomRes.data || []);

    } catch (error) {
      console.error('Error fetching data', error);
      setIsLive(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeMainTab === 'analysis') {
      const fetchAnalysis = async () => {
        try {
          const predRes = await api.get('/predict/BTCUSDT');
          setPrediction(predRes.data);
          setPredError(null);
        } catch (error) {
          setPredError(error.response?.data?.detail || "Prediction unavailable");
        }

        try {
          const goldRes = await api.get('/gold/metrics/BTCUSDT', { params: { hours: 24 } });
          const formattedGold = (goldRes.data || []).map(d => ({
            ...d,
            timeStr: new Date(d.window_start).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
          }));
          setGoldMetrics(formattedGold);
        } catch (error) {
          console.error("Gold fetch error", error);
        }
      };
      fetchAnalysis();
    }
  }, [activeMainTab]);

  const formatCurrency = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
  const formatNumber = (val) => new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val || 0);

  const isUp = stats.change24h >= 0;

  // Prepare data for Whale/Anomaly Radar
  const anomalyChartData = React.useMemo(() => {
    return anomalies.map(a => ({
      time: new Date(a.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', hour12: false}),
      rawTime: new Date(a.timestamp).getTime(),
      severityLevel: a.severity === 'high' ? 3 : a.severity === 'medium' ? 2 : 1,
      value: Math.abs(a.value || 0),
      type: a.event_type,
      description: a.description,
      severity: a.severity
    })).sort((a, b) => a.rawTime - b.rawTime);
  }, [anomalies]);

  return (
    <>
      <div className="navbar">
        <div className="navbar-brand" style={{flex: 1}}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          PRO_TERMINAL
        </div>
        
        <div className="main-tabs">
          <button className={`main-tab ${activeMainTab === 'terminal' ? 'active' : ''}`} onClick={() => setActiveMainTab('terminal')}>Terminal</button>
          <button className={`main-tab ${activeMainTab === 'analysis' ? 'active' : ''}`} onClick={() => setActiveMainTab('analysis')}>Analysis</button>
        </div>

        <div className="navbar-status" style={{flex: 1, justifyContent: 'flex-end'}}>
          BTC/USDT
          <span className={`status-dot ${isLive ? 'status-live' : 'status-offline'}`}></span>
          {isLive ? 'CONNECTED' : 'DISCONNECTED'}
        </div>
      </div>

      {activeMainTab === 'terminal' && (
        <div className="dashboard-layout">
          
          {/* Ticker Row */}
          <div className="ticker-row">
            <div className="ticker-item">
              <span className="ticker-label">24h Change</span>
              <span className={`ticker-value mono ${isUp ? 'text-up' : 'text-down'}`}>
                {isUp ? '+' : ''}{stats.change24h.toFixed(2)}%
              </span>
            </div>
            <div className="ticker-item">
              <span className="ticker-label">24h High</span>
              <span className="ticker-value mono">{formatNumber(stats.high24h)}</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-label">24h Low</span>
              <span className="ticker-value mono">{formatNumber(stats.low24h)}</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-label">24h Volume(BTC)</span>
              <span className="ticker-value mono">{formatNumber(stats.volume24h)}</span>
            </div>
          </div>

          {/* Left Panel: Anomalies & Events */}
          <div className="panel" style={{flex: 1, minHeight: '300px', display: 'flex', flexDirection: 'column'}}>
            <div className="panel-header">Whale & Anomaly Radar</div>
            <div className="panel-content" style={{display: 'flex', flexDirection: 'column', padding: 0}}>
              {anomalyChartData.length > 0 ? (
                <>
                  <div style={{height: '150px', borderBottom: '1px solid var(--border-color)'}}>
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{top: 10, right: 10, bottom: 0, left: 0}}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-highlight)" vertical={false} />
                        <XAxis dataKey="time" hide />
                        <YAxis dataKey="severityLevel" domain={[0, 4]} hide />
                        <ZAxis dataKey="value" range={[50, 400]} />
                        <RechartsTooltip 
                          cursor={{strokeDasharray: '3 3'}}
                          contentStyle={{ backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                          content={({active, payload}) => {
                            if (active && payload && payload.length) {
                              const data = payload[0].payload;
                              return (
                                <div style={{backgroundColor: 'var(--bg-panel)', padding: '8px', border: '1px solid var(--border-color)', borderRadius: '4px', maxWidth: '200px'}}>
                                  <span style={{fontSize: '0.75rem', color: data.severity === 'high' ? 'var(--color-down)' : '#fcd535'}}>{data.type.toUpperCase()}</span>
                                  <p style={{fontSize: '0.85rem', color: 'var(--text-primary)', margin: '4px 0', whiteSpace: 'normal'}}>{data.description}</p>
                                </div>
                              );
                            }
                            return null;
                          }}
                        />
                        <Scatter data={anomalyChartData} shape="circle">
                          {anomalyChartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.severity === 'high' ? 'var(--color-down)' : '#fcd535'} fillOpacity={0.6} stroke="#fff" strokeWidth={1} />
                          ))}
                        </Scatter>
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="anomalies-list" style={{flex: 1, padding: '16px', overflowY: 'auto'}}>
                    {anomalies.map((a, i) => (
                      <div key={i} style={{fontSize: '0.8rem', marginBottom: '12px', borderBottom: '1px solid var(--border-highlight)', paddingBottom: '8px'}}>
                        <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: '4px'}}>
                          <span style={{color: a.severity === 'high' ? 'var(--color-down)' : '#fcd535', fontWeight: 'bold'}}>{a.event_type.toUpperCase()}</span>
                          <span style={{color: 'var(--text-secondary)'}}>{new Date(a.timestamp).toLocaleTimeString()}</span>
                        </div>
                        <div style={{color: 'var(--text-primary)'}}>
                          {a.description}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div style={{padding: '16px', color: 'var(--text-secondary)'}}>No anomalies detected in the last 24H.</div>
              )}
            </div>
          </div>

          {/* Center Panel: Charting */}
          <div className="panel">
            <div className="panel-header">
              <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
                <span className={`ticker-large mono ${isUp ? 'text-up' : 'text-down'}`}>
                  {formatNumber(stats.currentPrice)}
                </span>
                <span style={{fontSize: '0.85rem', color: 'var(--text-secondary)'}}>Market Price (USD)</span>
              </div>
            </div>
            <div className="panel-content" style={{padding: 0, display: 'flex', flexDirection: 'column'}}>
              
              {/* Price Chart with News Impact Markers */}
              <div style={{ flex: 3, borderBottom: '1px solid var(--border-color)' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={priceData} syncId="anyId" margin={{ top: 20, right: 30, left: 10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={isUp ? 'var(--color-up)' : 'var(--color-down)'} stopOpacity={0.3}/>
                        <stop offset="95%" stopColor={isUp ? 'var(--color-up)' : 'var(--color-down)'} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-highlight)" vertical={false} />
                    <XAxis dataKey="timeStr" hide />
                    <YAxis domain={['auto', 'auto']} stroke="var(--text-secondary)" tick={{fontSize: 12, fontFamily: 'JetBrains Mono'}} orientation="right" tickFormatter={(val) => val.toLocaleString()} />
                    <RechartsTooltip 
                      contentStyle={{ backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                      itemStyle={{ color: 'var(--text-primary)', fontFamily: 'JetBrains Mono' }}
                      labelStyle={{ color: 'var(--text-secondary)' }}
                      content={({active, payload, label}) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div style={{backgroundColor: 'var(--bg-panel)', padding: '12px', border: '1px solid var(--border-color)', borderRadius: '8px'}}>
                              <p className="mono" style={{margin: 0}}>{label}</p>
                              <p className="mono" style={{color: isUp ? 'var(--color-up)' : 'var(--color-down)', margin: '4px 0'}}>Price: ${data.price.toLocaleString()}</p>
                              {data.newsEvent && (
                                <div style={{marginTop: '12px', borderTop: '1px solid var(--border-color)', paddingTop: '12px', maxWidth: '240px', whiteSpace: 'normal'}}>
                                  <span style={{fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600}}>NEWS IMPACT</span>
                                  <p style={{fontSize: '0.9rem', margin: '4px 0', color: data.newsSentiment > 0 ? 'var(--color-up)' : data.newsSentiment < 0 ? 'var(--color-down)' : 'var(--text-primary)'}}>
                                    {data.newsEvent.title}
                                  </p>
                                </div>
                              )}
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Area type="monotone" dataKey="price" stroke={isUp ? 'var(--color-up)' : 'var(--color-down)'} strokeWidth={2} fillOpacity={1} fill="url(#colorPrice)" isAnimationActive={false} />
                    <Scatter dataKey="newsPrice" shape={(props) => {
                       const { cx, cy, payload } = props;
                       if (!payload.newsEvent) return null;
                       const fill = payload.newsSentiment > 0 ? 'var(--color-up)' : payload.newsSentiment < 0 ? 'var(--color-down)' : '#fcd535';
                       return <circle cx={cx} cy={cy} r={6} fill={fill} stroke="#fff" strokeWidth={1.5} style={{cursor: 'pointer'}} />;
                    }} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* Volume Chart */}
              <div style={{ flex: 1 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={priceData} syncId="anyId" margin={{ top: 0, right: 30, left: 10, bottom: 20 }}>
                    <XAxis dataKey="timeStr" stroke="var(--text-secondary)" tick={{fontSize: 12}} />
                    <YAxis hide domain={['auto', 'auto']} />
                    <RechartsTooltip 
                      cursor={{fill: 'var(--bg-hover)'}}
                      contentStyle={{ backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-color)' }}
                    />
                    <Bar dataKey="volume" fill="var(--text-secondary)" opacity={0.5} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

            </div>
          </div>

          {/* Third Panel: Order Book */}
          <OrderBookPanel symbol="BTCUSDT" />

          {/* Right Panel: News */}
          <div className="panel">
            <div className="panel-header">Market News Stream</div>
            <div className="panel-content">
              {news.length === 0 ? (
                <div style={{color: 'var(--text-secondary)', fontSize: '0.85rem'}}>Awaiting news ingestion...</div>
              ) : (
                news.map((item, i) => (
                  <div key={i} className="list-item">
                    <div className="list-item-title">
                      <a href={item.url} target="_blank" rel="noreferrer" style={{color: 'var(--text-primary)', textDecoration: 'none'}}>
                        {item.title}
                      </a>
                    </div>
                    <div className="list-item-meta">
                      <span style={{color: item.sentiment_label === 'positive' ? 'var(--color-up)' : item.sentiment_label === 'negative' ? 'var(--color-down)' : 'var(--text-secondary)'}}>
                        {item.sentiment_label?.toUpperCase()} ({item.sentiment_score?.toFixed(2)})
                      </span>
                      <span>{item.source}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>
      )}

      {activeMainTab === 'analysis' && (
        <div className="analysis-layout">
          <h2 style={{color: 'var(--text-primary)'}}>BTC/USDT Market Analysis</h2>
          <div className="panel" style={{gridColumn: '1 / -1'}}>
            <LiquidityHeatmap symbol="BTCUSDT" />
          </div>

          <div className="analysis-grid" style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px', marginBottom: '20px'}}>
            <TopicBubbleChart />
            <DivergenceGauge symbol="BTCUSDT" />
          </div>

          <div className="analysis-grid">
            <div className="prediction-card">
              <h3 style={{borderBottom: '1px solid var(--border-color)', paddingBottom: '8px'}}>🤖 AI LSTM Prediction</h3>
              {predError ? (
                <div style={{color: 'var(--color-down)'}}>{predError}</div>
              ) : prediction ? (
                <>
                  <div style={{display: 'flex', justifyContent: 'space-between'}}>
                    <span className="ticker-label">Signal</span>
                    <span className={`ticker-value signal-${prediction.signal.toLowerCase()}`}>{prediction.signal}</span>
                  </div>
                  <div style={{display: 'flex', justifyContent: 'space-between'}}>
                    <span className="ticker-label">Predicted Price</span>
                    <span className="ticker-value mono">{formatCurrency(prediction.predicted_price)}</span>
                  </div>
                  <div style={{display: 'flex', justifyContent: 'space-between'}}>
                    <span className="ticker-label">Expected Change</span>
                    <span className={`ticker-value mono ${prediction.price_change_pct >= 0 ? 'text-up' : 'text-down'}`}>
                      {prediction.price_change_pct >= 0 ? '+' : ''}{prediction.price_change_pct.toFixed(2)}%
                    </span>
                  </div>
                  <div style={{display: 'flex', justifyContent: 'space-between'}}>
                    <span className="ticker-label">Confidence Score</span>
                    <span className="ticker-value mono">{formatNumber(prediction.confidence * 100)}%</span>
                  </div>

                  {/* Probabilistic Prediction Fan */}
                  {prediction.lower_bound && prediction.upper_bound && (
                    <div style={{height: '100px', marginTop: '12px'}}>
                      <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={[
                          { name: 'Current', price: prediction.current_price, range: [prediction.current_price, prediction.current_price] },
                          { name: 'Predicted', price: prediction.predicted_price, range: [prediction.lower_bound, prediction.upper_bound] }
                        ]} margin={{top:10, right:10, left:0, bottom:0}}>
                          <YAxis domain={['auto', 'auto']} hide/>
                          <Area dataKey="range" stroke="none" fill="var(--color-brand)" fillOpacity={0.15} isAnimationActive={false} />
                          <Scatter dataKey="price" fill="var(--color-brand)" line shape="circle" isAnimationActive={false} />
                          <RechartsTooltip 
                            contentStyle={{ backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-color)' }}
                            formatter={(value, name) => [Array.isArray(value) ? `${formatCurrency(value[0])} - ${formatCurrency(value[1])}` : formatCurrency(value), name === 'range' ? 'Bound Range' : 'Target']}
                          />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </>
              ) : (
                <div style={{color: 'var(--text-secondary)'}}>Loading prediction...</div>
              )}
            </div>

            <div className="prediction-card">
              <h3 style={{borderBottom: '1px solid var(--border-color)', paddingBottom: '8px'}}>📈 Sentiment & News Signal</h3>
              {goldMetrics.length > 0 ? (() => {
                const latest = goldMetrics[goldMetrics.length - 1];
                return (
                  <>
                    <div style={{display: 'flex', justifyContent: 'space-between'}}>
                      <span className="ticker-label">Avg Sentiment (1h)</span>
                      <span className={`ticker-value mono ${latest.avg_sentiment > 0.1 ? 'text-up' : latest.avg_sentiment < -0.1 ? 'text-down' : ''}`}>
                        {typeof latest.avg_sentiment === 'number' ? latest.avg_sentiment.toFixed(2) : 'N/A'}
                      </span>
                    </div>
                    <div style={{display: 'flex', justifyContent: 'space-between'}}>
                      <span className="ticker-label">News Signal Count</span>
                      <span className="ticker-value mono">{latest.sentiment_signal_count}</span>
                    </div>
                    <div style={{display: 'flex', justifyContent: 'space-between'}}>
                      <span className="ticker-label">Anomalies Detected</span>
                      <span className="ticker-value mono">{latest.anomaly_event_count}</span>
                    </div>
                  </>
                );
              })() : <div style={{color: 'var(--text-secondary)'}}>No gold metrics available</div>}
            </div>
          </div>

          <div className="panel" style={{flex: 1, minHeight: '400px'}}>
            <div className="panel-header">Price vs Sentiment Correlation (24H Gold Layer)</div>
            <div className="panel-content">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={goldMetrics} margin={{ top: 20, right: 30, left: 10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorSent" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-highlight)" vertical={false} />
                  <XAxis dataKey="timeStr" stroke="var(--text-secondary)" />
                  <YAxis yAxisId="left" domain={['auto', 'auto']} stroke="var(--text-secondary)" tickFormatter={(val) => `$${val.toLocaleString()}`} />
                  <YAxis yAxisId="right" orientation="right" domain={[-1, 1]} stroke="#3b82f6" />
                  <RechartsTooltip contentStyle={{ backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-color)' }} />
                  <Area yAxisId="left" type="monotone" dataKey="avg_price" stroke="#fcd535" fill="none" />
                  <Area yAxisId="right" type="monotone" dataKey="avg_sentiment" stroke="#3b82f6" fillOpacity={1} fill="url(#colorSent)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default App;
