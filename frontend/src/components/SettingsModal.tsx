import { X, Moon, Sun, Activity } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { theme, setTheme, reducedMotion, setReducedMotion } = useTheme();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-2xl bg-surface-container border border-outline-variant/40 p-6 shadow-2xl text-on-surface">
        <div className="flex items-center justify-between pb-4 border-b border-outline-variant/30">
          <h2 className="text-base font-semibold tracking-tight">System Settings</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors"
            aria-label="Close settings"
          >
            <X size={18} />
          </button>
        </div>

        <div className="py-5 space-y-6">
          {/* Theme setting */}
          <div className="space-y-2">
            <label className="text-xs font-mono uppercase tracking-wider text-on-surface-variant font-medium">
              Theme Mode
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setTheme('dark')}
                className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg border text-sm font-medium transition-all ${
                  theme === 'dark'
                    ? 'bg-primary text-white border-primary shadow-sm'
                    : 'bg-surface-container-low text-on-surface-variant border-outline-variant/30 hover:border-outline-variant/60'
                }`}
              >
                <Moon size={15} />
                <span>Dark</span>
              </button>
              <button
                type="button"
                onClick={() => setTheme('light')}
                className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg border text-sm font-medium transition-all ${
                  theme === 'light'
                    ? 'bg-primary text-white border-primary shadow-sm'
                    : 'bg-surface-container-low text-on-surface-variant border-outline-variant/30 hover:border-outline-variant/60'
                }`}
              >
                <Sun size={15} />
                <span>Light</span>
              </button>
            </div>
          </div>

          {/* Reduced Motion setting */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-surface-container-low border border-outline-variant/20">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <Activity size={16} className="text-primary" />
                <span className="text-sm font-medium">Reduced Motion</span>
              </div>
              <p className="text-xs text-on-surface-variant">
                Minimize UI animations and pause WebGL loops
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={reducedMotion}
              onClick={() => setReducedMotion(!reducedMotion)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                reducedMotion ? 'bg-primary' : 'bg-surface-container-highest'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  reducedMotion ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>

        <div className="flex justify-end pt-2 border-t border-outline-variant/20">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-surface-container-high hover:bg-surface-bright text-on-surface text-sm font-medium transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
