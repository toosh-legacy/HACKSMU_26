import { createRoot } from 'react-dom/client';
import HomepageSections from './components/HomepageSections';

export function mountHomepage(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const root = createRoot(container);
  root.render(<HomepageSections />);
}
