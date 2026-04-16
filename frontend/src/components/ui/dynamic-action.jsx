import * as React from "react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const DynamicActionBar = React.forwardRef(
  ({ actions, className = "", ...props }, ref) => {
    const [activeIndex, setActiveIndex] = useState(null);
    const activeAction = activeIndex !== null ? actions[activeIndex] : null;

    const BUTTON_BAR_HEIGHT = 52;

    const containerAnimate = activeAction
      ? { height: activeAction.dimensions.height + BUTTON_BAR_HEIGHT }
      : { height: BUTTON_BAR_HEIGHT };

    const transition = { type: "spring", stiffness: 420, damping: 38 };

    return (
      <div
        ref={ref}
        className={`relative ${className}`}
        onMouseLeave={() => setActiveIndex(null)}
        {...props}
      >
        <motion.div
          style={{
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            borderRadius: "16px",
            background: "rgba(250,240,230,0.07)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            border: "1px solid rgba(250,240,230,0.1)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.4), 0 1px 0 rgba(250,240,230,0.05) inset",
          }}
          animate={containerAnimate}
          transition={transition}
          initial={{ height: BUTTON_BAR_HEIGHT }}
        >
          {/* Expandable content panel */}
          <div style={{ flexGrow: 1, overflow: "hidden" }}>
            <AnimatePresence>
              {activeAction && (
                <motion.div
                  style={{ width: "100%" }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15, delay: 0.08 }}
                >
                  {activeAction.content}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Button row */}
          <div
            style={{
              display: "flex",
              flexShrink: 0,
              alignItems: "center",
              justifyContent: "center",
              gap: "2px",
              padding: "0 6px",
              height: `${BUTTON_BAR_HEIGHT}px`,
            }}
          >
            {actions.map((action, index) => {
              const Icon = action.icon;
              const isActive = activeIndex === index;
              return (
                <button
                  key={action.id}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={action.onClick}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "7px",
                    borderRadius: "10px",
                    padding: "8px 14px",
                    border: "none",
                    cursor: "pointer",
                    fontFamily: "var(--font)",
                    fontWeight: 500,
                    fontSize: "0.82rem",
                    letterSpacing: "0.01em",
                    transition: "all 0.15s ease",
                    background: isActive || action.isActive
                      ? "rgba(250,240,230,0.12)"
                      : "transparent",
                    color: action.isActive
                      ? "var(--linen)"
                      : isActive
                      ? "var(--linen)"
                      : "rgba(250,240,230,0.45)",
                    whiteSpace: "nowrap",
                  }}
                >
                  <Icon size={15} strokeWidth={1.8} />
                  <span>{action.label}</span>
                </button>
              );
            })}
          </div>
        </motion.div>
      </div>
    );
  }
);

DynamicActionBar.displayName = "DynamicActionBar";
export default DynamicActionBar;
