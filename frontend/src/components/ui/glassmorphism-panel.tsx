import React from "react";
import { motion } from "framer-motion";

interface GlassmorphismPanelProps {
  children: React.ReactNode;
  className?: string;
  blur?: "sm" | "md" | "lg" | "xl";
  opacity?: number;
  hover?: boolean;
  padding?: string;
}

const blurMap = {
  sm: "backdrop-blur-sm",
  md: "backdrop-blur-md",
  lg: "backdrop-blur-lg",
  xl: "backdrop-blur-xl",
};

export function GlassmorphismPanel({
  children,
  className = "",
  blur = "md",
  opacity = 5,
  hover = false,
  padding = "p-6",
}: GlassmorphismPanelProps) {
  const baseClasses = `${blurMap[blur]} bg-white/${opacity} border border-white/10 rounded-2xl ${padding} ${className}`;

  if (hover) {
    return (
      <motion.div
        className={baseClasses}
        whileHover={{
          backgroundColor: `rgba(255, 255, 255, ${(opacity + 3) / 100})`,
          borderColor: "rgba(255, 255, 255, 0.2)",
        }}
        transition={{ duration: 0.2 }}
      >
        {children}
      </motion.div>
    );
  }

  return <div className={baseClasses}>{children}</div>;
}
