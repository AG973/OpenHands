import React from "react";
import { motion } from "framer-motion";

interface DockItem {
  id: string;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  active?: boolean;
  badge?: number;
}

interface FloatingDockProps {
  items: DockItem[];
  className?: string;
  orientation?: "horizontal" | "vertical";
}

function DockIcon({ item }: { item: DockItem }) {
  const [isHovered, setIsHovered] = React.useState(false);

  return (
    <motion.button
      className={`relative flex items-center justify-center w-12 h-12 rounded-xl transition-colors ${
        item.active
          ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
          : "text-gray-400 hover:text-white hover:bg-white/10"
      }`}
      whileHover={{ scale: 1.15 }}
      whileTap={{ scale: 0.95 }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      onClick={item.onClick}
      aria-label={item.label}
    >
      {item.icon}

      {/* Badge */}
      {item.badge !== undefined && item.badge > 0 && (
        <span className="absolute -top-1 -right-1 w-5 h-5 flex items-center justify-center text-[10px] font-bold bg-red-500 text-white rounded-full">
          {item.badge > 99 ? "99+" : item.badge}
        </span>
      )}

      {/* Tooltip */}
      {isHovered && (
        <motion.div
          initial={{ opacity: 0, x: 10 }}
          animate={{ opacity: 1, x: 0 }}
          className="absolute left-full ml-3 px-3 py-1.5 bg-gray-900 border border-white/10 rounded-lg text-sm text-white whitespace-nowrap z-50 pointer-events-none"
        >
          {item.label}
        </motion.div>
      )}
    </motion.button>
  );
}

export function FloatingDock({
  items,
  className = "",
  orientation = "vertical",
}: FloatingDockProps) {
  const isVertical = orientation === "vertical";

  return (
    <motion.div
      initial={{ opacity: 0, x: isVertical ? -20 : 0, y: isVertical ? 0 : 20 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={`flex ${isVertical ? "flex-col" : "flex-row"} gap-2 p-2 bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl ${className}`}
    >
      {items.map((item) => (
        <DockIcon key={item.id} item={item} />
      ))}
    </motion.div>
  );
}
