import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";

interface TypewriterEffectProps {
  words: string[];
  className?: string;
  typingSpeed?: number;
  deletingSpeed?: number;
  pauseDuration?: number;
  cursorColor?: string;
}

export function TypewriterEffect({
  words,
  className = "",
  typingSpeed = 80,
  deletingSpeed = 50,
  pauseDuration = 2000,
  cursorColor = "#3B82F6",
}: TypewriterEffectProps) {
  const [currentWordIndex, setCurrentWordIndex] = useState(0);
  const [currentText, setCurrentText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const currentWord = words[currentWordIndex];

    const timeout = setTimeout(
      () => {
        if (!isDeleting) {
          setCurrentText(currentWord.substring(0, currentText.length + 1));
          if (currentText === currentWord) {
            setTimeout(() => setIsDeleting(true), pauseDuration);
          }
        } else {
          setCurrentText(currentWord.substring(0, currentText.length - 1));
          if (currentText === "") {
            setIsDeleting(false);
            setCurrentWordIndex((prev) => (prev + 1) % words.length);
          }
        }
      },
      isDeleting ? deletingSpeed : typingSpeed,
    );

    return () => clearTimeout(timeout);
  }, [
    currentText,
    isDeleting,
    currentWordIndex,
    words,
    typingSpeed,
    deletingSpeed,
    pauseDuration,
  ]);

  return (
    <span className={className}>
      {currentText}
      <motion.span
        animate={{ opacity: [1, 0] }}
        transition={{ duration: 0.5, repeat: Infinity, repeatType: "reverse" }}
        style={{ color: cursorColor }}
      >
        |
      </motion.span>
    </span>
  );
}
