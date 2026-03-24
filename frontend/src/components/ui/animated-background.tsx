import React, { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface ParticleFieldProps {
  count?: number;
  color?: string;
  speed?: number;
  size?: number;
}

function Particles({
  count = 500,
  color = "#3B82F6",
  speed = 0.3,
  size = 2,
}: ParticleFieldProps) {
  const meshRef = useRef<THREE.Points>(null);

  const particles = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const velocities = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 20;
      velocities[i * 3] = (Math.random() - 0.5) * speed * 0.01;
      velocities[i * 3 + 1] = (Math.random() - 0.5) * speed * 0.01;
      velocities[i * 3 + 2] = (Math.random() - 0.5) * speed * 0.01;
    }
    return { positions, velocities };
  }, [count, speed]);

  useFrame(() => {
    if (!meshRef.current) return;
    const positions = meshRef.current.geometry.attributes.position
      .array as Float32Array;
    for (let i = 0; i < count; i++) {
      positions[i * 3] += particles.velocities[i * 3];
      positions[i * 3 + 1] += particles.velocities[i * 3 + 1];
      positions[i * 3 + 2] += particles.velocities[i * 3 + 2];

      // Wrap around boundaries
      for (let j = 0; j < 3; j++) {
        if (positions[i * 3 + j] > 10) positions[i * 3 + j] = -10;
        if (positions[i * 3 + j] < -10) positions[i * 3 + j] = 10;
      }
    }
    meshRef.current.geometry.attributes.position.needsUpdate = true;
  });

  return (
    <points ref={meshRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[particles.positions, 3]}
          count={count}
        />
      </bufferGeometry>
      <pointsMaterial
        size={size * 0.01}
        color={color}
        transparent
        opacity={0.6}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

interface AnimatedBackgroundProps {
  variant?: "particles" | "minimal";
  className?: string;
  children?: React.ReactNode;
}

export function AnimatedBackground({
  variant = "particles",
  className = "",
  children,
}: AnimatedBackgroundProps) {
  if (variant === "minimal") {
    return (
      <div className={`relative ${className}`}>
        <div className="absolute inset-0 bg-gradient-to-br from-[#0a0a1a] via-[#0d1117] to-[#1a0a2e] -z-10" />
        <div className="absolute inset-0 opacity-30 -z-10">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse delay-1000" />
          <div className="absolute top-1/2 left-1/2 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl animate-pulse delay-500" />
        </div>
        {children}
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      <div className="absolute inset-0 -z-10">
        <Canvas
          camera={{ position: [0, 0, 5], fov: 75 }}
          style={{ background: "transparent" }}
          gl={{ alpha: true, antialias: false }}
          dpr={[1, 1.5]}
        >
          <ambientLight intensity={0.5} />
          <Particles count={300} color="#3B82F6" speed={0.2} size={1.5} />
          <Particles count={200} color="#8B5CF6" speed={0.15} size={1} />
          <Particles count={100} color="#06B6D4" speed={0.25} size={2} />
        </Canvas>
      </div>
      <div className="absolute inset-0 bg-[#0d1117]/80 -z-[5]" />
      {children}
    </div>
  );
}
