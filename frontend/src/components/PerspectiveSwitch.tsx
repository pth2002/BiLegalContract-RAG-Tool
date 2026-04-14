import { motion } from 'framer-motion';
import type { PerspectiveInfo, PerspectiveType } from '../types';

interface PerspectiveSwitchProps {
  perspectives: PerspectiveInfo[];
  currentPerspective: PerspectiveType;
  onChange: (perspective: PerspectiveType) => void;
} 

export default function PerspectiveSwitch({
  perspectives,
  currentPerspective,
  onChange,
}: PerspectiveSwitchProps) {
  const partyA = perspectives.find((p) => p.id === 'party_a');
  const partyB = perspectives.find((p) => p.id === 'party_b');

  return (
    <div className="space-y-4">
      {/* Toggle Switch */}
      <div className="relative">
        <div className="flex bg-slate-700 rounded-lg p-1">
          <button
            onClick={() => onChange('party_a')}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              currentPerspective === 'party_a'
                ? 'bg-blue-600 text-white'
                : 'text-slate-300 hover:text-white'
            }`}
          >
            {partyA?.name || '甲方视角'}
          </button>
          <button
            onClick={() => onChange('party_b')}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              currentPerspective === 'party_b'
                ? 'bg-blue-600 text-white'
                : 'text-slate-300 hover:text-white'
            }`}
          >
            {partyB?.name || '乙方视角'}
          </button>
        </div>
      </div>

      {/* Current Perspective Info */}
      {currentPerspective === 'party_a' && partyA && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm text-slate-400"
        >
          <p className="mb-2">{partyA.description}</p>
          <div className="flex flex-wrap gap-1">
            {partyA.focus_areas.map((area: string) => (
              <span
                key={area}
                className="px-2 py-0.5 bg-slate-700 rounded text-xs"
              >
                {area}
              </span>
            ))}
          </div>
        </motion.div>
      )}

      {currentPerspective === 'party_b' && partyB && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm text-slate-400"
        >
          <p className="mb-2">{partyB.description}</p>
          <div className="flex flex-wrap gap-1">
            {partyB.focus_areas.map((area: string) => (
              <span
                key={area}
                className="px-2 py-0.5 bg-slate-700 rounded text-xs"
              >
                {area}
              </span>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
