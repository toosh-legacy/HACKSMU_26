import { createRoot } from 'react-dom/client';
import AuroraWaves from './components/ui/aurora-waves';

export function mountAuroraWaves(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const root = createRoot(container);
  root.render(<AuroraWaves speed={0.8} glow={12.0} />);
}
