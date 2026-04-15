import { createRoot } from "react-dom/client";
import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Search,
  Layers,
  Share2,
  Upload,
} from "lucide-react";
import DynamicActionBar from "./components/ui/dynamic-action";

// ── Hover content panels ──────────────────────────────────────────────

const DashboardContent = () => (
  <div style={{ padding: "16px 20px 4px" }}>
    <p style={{ fontSize: "0.7rem", color: "rgba(250,240,230,0.4)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>Overview</p>
    <p style={{ fontSize: "0.82rem", color: "rgba(250,240,230,0.7)", lineHeight: 1.5 }}>
      Pipeline run stats — SNR gain, noise distribution, cluster summary.
    </p>
    <div style={{ height: "1px", background: "rgba(250,240,230,0.08)", margin: "12px 0 0" }} />
  </div>
);

const ExplorerContent = () => (
  <div style={{ padding: "16px 20px 4px" }}>
    <p style={{ fontSize: "0.7rem", color: "rgba(250,240,230,0.4)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>Call Browser</p>
    <p style={{ fontSize: "0.82rem", color: "rgba(250,240,230,0.7)", lineHeight: 1.5 }}>
      Filter by noise type or cluster. Inspect spectrograms, F0, and cleaned audio.
    </p>
    <div style={{ height: "1px", background: "rgba(250,240,230,0.08)", margin: "12px 0 0" }} />
  </div>
);

const ClustersContent = () => (
  <div style={{ padding: "16px 20px 4px" }}>
    <p style={{ fontSize: "0.7rem", color: "rgba(250,240,230,0.4)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>Pattern Analysis</p>
    <p style={{ fontSize: "0.82rem", color: "rgba(250,240,230,0.7)", lineHeight: 1.5 }}>
      UMAP + K-means groups. Each cluster represents a distinct call signature.
    </p>
    <div style={{ height: "1px", background: "rgba(250,240,230,0.08)", margin: "12px 0 0" }} />
  </div>
);

const NetworkContent = () => (
  <div style={{ padding: "16px 20px 4px" }}>
    <p style={{ fontSize: "0.7rem", color: "rgba(250,240,230,0.4)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>Tribe Graph</p>
    <p style={{ fontSize: "0.82rem", color: "rgba(250,240,230,0.7)", lineHeight: 1.5 }}>
      Sigma.js force-directed graph of inter-herd acoustic similarity.
    </p>
    <div style={{ height: "1px", background: "rgba(250,240,230,0.08)", margin: "12px 0 0" }} />
  </div>
);

const UploadContent = () => (
  <div style={{ padding: "16px 20px 4px" }}>
    <p style={{ fontSize: "0.7rem", color: "rgba(250,240,230,0.4)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>Process New File</p>
    <p style={{ fontSize: "0.82rem", color: "rgba(250,240,230,0.7)", lineHeight: 1.5 }}>
      Upload a .wav recording — pipeline runs automatically and results reload.
    </p>
    <div style={{ height: "1px", background: "rgba(250,240,230,0.08)", margin: "12px 0 0" }} />
  </div>
);

// ── Nav wrapper — syncs active state with hash ────────────────────────

function AppNav() {
  const [activeSection, setActiveSection] = useState(
    window.location.hash.replace("#", "") || "dashboard"
  );

  useEffect(() => {
    const onHash = () =>
      setActiveSection(window.location.hash.replace("#", "") || "dashboard");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (section) => {
    window.location.hash = `#${section}`;
    setActiveSection(section);
  };

  const actions = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: LayoutDashboard,
      content: <DashboardContent />,
      dimensions: { width: 320, height: 90 },
      onClick: () => navigate("dashboard"),
      isActive: activeSection === "dashboard",
    },
    {
      id: "explorer",
      label: "Explorer",
      icon: Search,
      content: <ExplorerContent />,
      dimensions: { width: 340, height: 90 },
      onClick: () => navigate("explorer"),
      isActive: activeSection === "explorer",
    },
    {
      id: "clusters",
      label: "Clusters",
      icon: Layers,
      content: <ClustersContent />,
      dimensions: { width: 340, height: 90 },
      onClick: () => navigate("clusters"),
      isActive: activeSection === "clusters",
    },
    {
      id: "network",
      label: "Network",
      icon: Share2,
      content: <NetworkContent />,
      dimensions: { width: 320, height: 90 },
      onClick: () => navigate("network"),
      isActive: activeSection === "network",
    },
    {
      id: "upload",
      label: "Upload",
      icon: Upload,
      content: <UploadContent />,
      dimensions: { width: 340, height: 90 },
      onClick: () => navigate("upload"),
      isActive: activeSection === "upload",
    },
  ];

  return <DynamicActionBar actions={actions} activeSection={activeSection} />;
}

export function mountNavBar(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const root = createRoot(container);
  root.render(<AppNav />);
}
