import React from "react";
import { motion } from "framer-motion";

interface GlowingBorderProps {
  children: React.ReactNode;
  className?: string;
  glowColor?: string;
  borderRadius?: string;
  animated?: boolean;
}

export function GlowingBorder({
  children,
  className = "",
  glowColor = "from-blue-500 via-purple-500 to-cyan-500",
  borderRadius = "rounded-2xl",
  animated = true,
}: GlowingBorderProps) {
  return (
    <div className={`relative group ${className}`}>
      {/* Glow effect */}
      <motion.div
        className={`absolute -inset-[1px] bg-gradient-to-r ${glowColor} ${borderRadius} opacity-50 blur-sm group-hover:opacity-75 transition-opacity duration-500`}
        animate={
          animated
            ? {
                backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"],
              }
            : undefined
        }
        transition={
          animated
            ? {
                duration: 5,
                repeat: Infinity,
                ease: "linear",
              }
            : undefined
        }
        style={{ backgroundSize: "200% 200%" }}
      />
      {/* Content */}
      <div
        className={`relative bg-[#0d1117] ${borderRadius} overflow-hidden`}
      >
        {children}
      </div>
    </div>
  );
}
