import React from 'react';
import { motion } from 'motion/react';
import { useTheme } from '../context/ThemeContext';

interface StaggeredTextProps {
  text: string;
  onSourceClick?: (sourceId: string) => void;
  className?: string;
}

export function StaggeredText({ text, onSourceClick, className = '' }: StaggeredTextProps) {
  const { reducedMotion } = useTheme();

  // Split into sentences / paragraphs preserving structure
  const rawSentences = text
    .split(/(?<=[.?!])\s+|\n\n+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

  // If text is empty or just 1 short item
  const sentences = rawSentences.length > 0 ? rawSentences : [text];

  const renderSentenceWithChips = (sentence: string) => {
    // Match [S1], [S2], [S12], etc.
    const parts = sentence.split(/(\[S\d+\])/g);
    return (
      <>
        {parts.map((part, i) => {
          const match = part.match(/^\[S(\d+)\]$/);
          if (match) {
            const sourceId = `S${match[1]}`;
            return (
              <button
                key={i}
                type="button"
                onClick={() => onSourceClick?.(sourceId)}
                title={`View Source ${sourceId}`}
                className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-surface-container-high hover:bg-primary-container hover:text-on-primary-container text-primary font-mono text-xs font-semibold border border-outline-variant/30 transition-colors cursor-pointer"
              >
                [{sourceId}]
              </button>
            );
          }
          return <React.Fragment key={i}>{part}</React.Fragment>;
        })}
      </>
    );
  };

  if (reducedMotion) {
    return (
      <div className={`space-y-2 leading-relaxed ${className}`}>
        {sentences.map((s, idx) => (
          <p key={idx}>{renderSentenceWithChips(s)}</p>
        ))}
      </div>
    );
  }

  return (
    <div className={`space-y-2 leading-relaxed ${className}`}>
      {sentences.map((sentence, index) => (
        <motion.p
          key={index}
          initial={{ opacity: 0, y: 3 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: index * 0.08, ease: 'easeOut' }}
        >
          {renderSentenceWithChips(sentence)}
        </motion.p>
      ))}
    </div>
  );
}
