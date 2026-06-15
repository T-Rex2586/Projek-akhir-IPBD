import React, { useState, useEffect } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';
import axios from 'axios';

const TopicBubbleChart = () => {
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTopics = async () => {
      try {
        const response = await axios.get('http://localhost:8001/news/topics', {
          headers: { 'X-API-Key': 'ak_58bb132b5b975898f1a11858d811d01438391693bb363204ad53e41dba4618c2' }
        });
        
        // Add pseudo-coordinates to spread bubbles nicely
        const data = response.data.map((t, index) => {
          // simple spiral or grid distribution for aesthetic
          const row = Math.floor(index / 5);
          const col = index % 5;
          return {
            ...t,
            x: col + Math.random() * 0.5,
            y: row + Math.random() * 0.5
          };
        });
        setTopics(data);
        setLoading(false);
      } catch (err) {
        console.error("Failed to fetch topics", err);
        setLoading(false);
      }
    };
    
    fetchTopics();
    const interval = setInterval(fetchTopics, 60000); // refresh every minute
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="panel" style={{height: '350px', display: 'flex', flexDirection: 'column'}}>
      <div className="panel-header">Narrative Topic Map (24H)</div>
      <div className="panel-content" style={{flex: 1, padding: '16px'}}>
        {loading ? (
          <div style={{color: 'var(--text-secondary)'}}>Loading topics...</div>
        ) : topics.length === 0 ? (
          <div style={{color: 'var(--text-secondary)', textAlign: 'center', marginTop: '40px'}}>
            Not enough news data to extract topics.<br/><small>Wait for RSS ingestor to fetch more articles.</small>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
              <XAxis dataKey="x" type="number" hide domain={[-0.5, 5.5]} />
              <YAxis dataKey="y" type="number" hide domain={[-0.5, 4.5]} />
              <ZAxis dataKey="weight" range={[500, 3000]} name="Weight" />
              
              <RechartsTooltip 
                cursor={{ strokeDasharray: '3 3' }}
                contentStyle={{ backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                content={({active, payload}) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div style={{backgroundColor: 'var(--bg-panel)', padding: '8px', border: '1px solid var(--border-color)', borderRadius: '4px'}}>
                        <h4 style={{margin: '0 0 4px 0', color: 'var(--text-primary)'}}>"{data.topic}"</h4>
                        <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>
                          Relevance: {data.weight}%<br/>
                          Sentiment: <span style={{color: data.sentiment > 0 ? 'var(--color-up)' : data.sentiment < 0 ? 'var(--color-down)' : '#fcd535'}}>{data.sentiment > 0 ? '+' : ''}{data.sentiment}</span>
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Scatter data={topics} shape="circle">
                {topics.map((entry, index) => {
                  const color = entry.sentiment > 0 ? 'var(--color-up)' : entry.sentiment < 0 ? 'var(--color-down)' : '#fcd535';
                  return (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={color} 
                      fillOpacity={0.7}
                      stroke={color}
                      strokeWidth={1}
                    />
                  );
                })}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default TopicBubbleChart;
