import React from "react";
import { motion } from "framer-motion";

interface AnimatedGradientTextProps {
  children: React.ReactNode;
  className?: string;
  gradient?: string;
  as?: "h1" | "h2" | "h3" | "h4" | "p" | "span";
}

export function AnimatedGradientText({
  children,
  className = "",
  gradient = "from-blue-400 via-purple-400 to-cyan-400",
  as: Component = "h1",
}: AnimatedGradientTextProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Component
        className={`bg-gradient-to-r ${gradient} bg-clip-text text-transparent animate-gradient-x bg-[length:200%_auto] ${className}`}
      >
        {children}
      </Component>
    </motion.div>
  );
}
