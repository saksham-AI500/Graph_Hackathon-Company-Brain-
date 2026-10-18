import React from 'react';
import { MotionConfig } from 'motion/react';
import { useTheme } from '../context/ThemeContext';

export function MotionWrapper({ children }: { children: React.ReactNode }) {
  const { reducedMotion } = useTheme();

  return (
    <MotionConfig reducedMotion={reducedMotion ? 'always' : 'user'}>
      {children}
    </MotionConfig>
  );
}
