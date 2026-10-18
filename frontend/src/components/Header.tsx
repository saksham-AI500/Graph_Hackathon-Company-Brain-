import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Sun, Moon, Settings } from 'lucide-react';
import { DitheredOrb } from './DitheredOrb';
import { SettingsModal } from './SettingsModal';
import { useTheme } from '../context/ThemeContext';
import { useHealth } from '../api/client';

export function Header() {
  const { theme, toggleTheme } = useTheme();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const { data: health, isError, isLoading } = useHealth();

  return (
    <>
      <header className="fixed top-0 left-0 w-full z-40 bg-surface/90 backdrop-blur-xl border-b border-outline-variant/30 shadow-[0_1px_8px_rgba(0,0,0,0.15)]">
        <div className="h-14 w-full px-4 md:px-8 max-w-[1440px] mx-auto flex items-center justify-between gap-4">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-7 h-7 rounded-full bg-surface-container-high border border-outline-variant/50 overflow-hidden shadow-inner">
              <DitheredOrb size={22} />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-base tracking-tight text-on-surface">RepoBrain</span>
              <span className="hidden sm:inline-block px-2 py-0.5 rounded-full bg-surface-container-high border border-outline-variant/40 text-on-surface-variant font-mono text-[10px] tracking-wider uppercase font-medium">
                Company Brain
              </span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-1 bg-surface-container-lowest p-1 rounded-lg border border-outline-variant/20">
            <NavLink
              to="/ask"
              className={({ isActive }) =>
                `px-3 py-1 rounded text-xs md:text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-surface-container-high text-primary border border-outline-variant/40 shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                }`
              }
            >
              Ask
            </NavLink>
            <NavLink
              to="/compare"
              className={({ isActive }) =>
                `px-3 py-1 rounded text-xs md:text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-surface-container-high text-primary border border-outline-variant/40 shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                }`
              }
            >
              Compare
            </NavLink>
            <NavLink
              to="/graph"
              className={({ isActive }) =>
                `px-3 py-1 rounded text-xs md:text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-surface-container-high text-primary border border-outline-variant/40 shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                }`
              }
            >
              Graph
            </NavLink>
            <NavLink
              to="/evaluation"
              className={({ isActive }) =>
                `px-3 py-1 rounded text-xs md:text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-surface-container-high text-primary border border-outline-variant/40 shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                }`
              }
            >
              Evaluation
            </NavLink>
          </nav>

          {/* Status Pill & Controls */}
          <div className="flex items-center gap-2 md:gap-3">
            {/* Status Pill from /api/health */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-mono tracking-wider uppercase font-semibold ${
                isLoading
                  ? 'bg-surface-container-lowest border-outline-variant/30 text-on-surface-variant'
                  : isError
                  ? 'bg-red-500/10 border-red-500/30 text-red-400'
                  : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isLoading
                    ? 'bg-zinc-400 animate-pulse'
                    : isError
                    ? 'bg-red-500'
                    : 'bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]'
                }`}
              />
              <span className="hidden sm:inline">
                {isLoading ? 'Checking...' : isError ? 'Backend offline' : health?.database === 'connected' ? 'Connected' : 'Healthy'}
              </span>
              <span className="sm:hidden">
                {isLoading ? '...' : isError ? 'Offline' : 'Live'}
              </span>
            </div>

            {/* Theme Toggle */}
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Toggle Theme"
              className="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high border border-transparent hover:border-outline-variant/40 transition-colors"
            >
              {theme === 'dark' ? <Moon size={16} /> : <Sun size={16} />}
            </button>

            {/* Settings */}
            <button
              type="button"
              onClick={() => setIsSettingsOpen(true)}
              aria-label="Open Settings"
              className="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high border border-transparent hover:border-outline-variant/40 transition-colors"
            >
              <Settings size={16} />
            </button>
          </div>
        </div>
      </header>

      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </>
  );
}
