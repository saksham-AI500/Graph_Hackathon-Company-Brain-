import { motion } from 'motion/react';
import { useTheme } from '../context/ThemeContext';

interface ScoreBarProps {
  score: number; // 0 to 1 or 0 to 100
  max?: number;
  className?: string;
  barColor?: string;
}

export function ScoreBar({
  score,
  max = 100,
  className = '',
  barColor = 'bg-primary-container',
}: ScoreBarProps) {
  const { reducedMotion } = useTheme();
  const normalized = score <= 1 && max > 1 ? score * 100 : score;
  const pct = Math.min(Math.max((normalized / max) * 100, 0), 100);

  return (
    <div className={`w-full bg-surface-container-lowest h-1.5 rounded-full overflow-hidden ${className}`}>
      {reducedMotion ? (
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      ) : (
        <motion.div
          className={`h-full rounded-full ${barColor}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      )}
    </div>
  );
}
