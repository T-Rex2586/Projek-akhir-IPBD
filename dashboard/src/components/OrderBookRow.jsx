import React, { useEffect, useRef } from 'react';

const OrderBookRow = React.memo(({ price, size, total, type, maxTotal }) => {
  const rowRef = useRef(null);
  const prevSize = useRef(size);

  useEffect(() => {
    if (prevSize.current !== size && rowRef.current) {
      // Trigger flash animation
      rowRef.current.classList.remove('flash-row');
      // Trigger reflow
      void rowRef.current.offsetWidth;
      rowRef.current.classList.add('flash-row');
    }
    prevSize.current = size;
  }, [size]);

  // Calculate width for depth bar (max 100%)
  const widthPct = maxTotal > 0 ? Math.min((total / maxTotal) * 100, 100) : 0;
  
  const isAsk = type === 'ask';
  const textColor = isAsk ? 'var(--color-down)' : 'var(--color-up)';
  const barColor = isAsk ? 'rgba(246, 70, 93, 0.15)' : 'rgba(14, 203, 129, 0.15)';

  const formatNumber = (num, decimals) => {
    return new Intl.NumberFormat('en-US', { 
      minimumFractionDigits: decimals, 
      maximumFractionDigits: decimals 
    }).format(num);
  };

  return (
    <div 
      ref={rowRef}
      className="ob-row mono" 
      title={`Cumulative Total: ${formatNumber(total, 4)}`}
    >
      <div 
        className="ob-bg-bar" 
        style={{ width: `${widthPct}%`, backgroundColor: barColor }} 
      />
      <div className="ob-cell" style={{ color: textColor }}>
        {formatNumber(price, 2)}
      </div>
      <div className="ob-cell ob-size">
        {formatNumber(size, 5)}
      </div>
      <div className="ob-cell ob-total">
        {formatNumber(total, 5)}
      </div>
    </div>
  );
}, (prevProps, nextProps) => {
  return prevProps.price === nextProps.price && prevProps.size === nextProps.size;
});

export default OrderBookRow;
