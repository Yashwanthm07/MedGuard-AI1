import { Canvas, useFrame } from '@react-three/fiber';
import { Float } from '@react-three/drei';
import { useRef } from 'react';

function Node({ position, color, isAnalyzing }) {
  const ref = useRef(null);
  useFrame((_, delta) => {
    if (!ref.current) return;
    const speedBoost = isAnalyzing ? 1.55 : 1;
    ref.current.rotation.x += delta * 0.25 * speedBoost;
    ref.current.rotation.y += delta * 0.35 * speedBoost;
  });

  return (
    <Float
      speed={isAnalyzing ? 3.2 : 2}
      rotationIntensity={isAnalyzing ? 1.9 : 1.2}
      floatIntensity={isAnalyzing ? 1.75 : 1.2}
    >
      <mesh ref={ref} position={position}>
        <icosahedronGeometry args={[isAnalyzing ? 0.7 : 0.65, 0]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isAnalyzing ? 0.4 : 0.16}
          wireframe
        />
      </mesh>
    </Float>
  );
}

function ScanField({ isAnalyzing }) {
  const ringRef = useRef(null);
  const pulseRef = useRef(null);

  useFrame((state, delta) => {
    if (ringRef.current) {
      ringRef.current.rotation.z += delta * (isAnalyzing ? 1.55 : 0.62);
    }

    if (pulseRef.current) {
      const t = state.clock.elapsedTime;
      const freq = isAnalyzing ? 3.2 : 1.8;
      const scale = 1 + Math.sin(t * freq) * (isAnalyzing ? 0.08 : 0.04);
      pulseRef.current.scale.set(scale, scale, 1);
      pulseRef.current.material.opacity = isAnalyzing
        ? 0.25 + (Math.sin(t * freq) + 1) * 0.1
        : 0.12 + (Math.sin(t * freq) + 1) * 0.05;
    }
  });

  return (
    <group>
      <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.2, 0.05, 14, 90]} />
        <meshStandardMaterial
          color={isAnalyzing ? '#57ebff' : '#2fc8ff'}
          emissive={isAnalyzing ? '#57ebff' : '#2fc8ff'}
          emissiveIntensity={isAnalyzing ? 0.85 : 0.4}
        />
      </mesh>

      <mesh ref={pulseRef} rotation={[Math.PI / 2, 0, 0]} position={[0, 0, -0.18]}>
        <ringGeometry args={[1.55, 1.78, 64]} />
        <meshStandardMaterial
          color="#7fffe4"
          transparent
          opacity={0.2}
          emissive="#7fffe4"
          emissiveIntensity={isAnalyzing ? 0.6 : 0.28}
          side={2}
        />
      </mesh>
    </group>
  );
}

export default function Scanner3D({ isAnalyzing = false }) {
  return (
    <div className={`scanner3d-wrap ${isAnalyzing ? 'is-analyzing' : ''}`} aria-hidden="true">
      <Canvas camera={{ position: [0, 0, 4.8], fov: 52 }}>
        <ambientLight intensity={isAnalyzing ? 0.66 : 0.5} />
        <pointLight position={[2, 2, 3]} intensity={isAnalyzing ? 1 : 0.8} color="#30d8ff" />
        <pointLight position={[-2, -1, 2]} intensity={isAnalyzing ? 0.9 : 0.7} color="#8fffcb" />
        <ScanField isAnalyzing={isAnalyzing} />
        <Node position={[-1.4, 0.1, 0]} color="#30d8ff" isAnalyzing={isAnalyzing} />
        <Node position={[1.4, -0.2, 0]} color="#7effb4" isAnalyzing={isAnalyzing} />
        <Node position={[0, 1.1, -0.5]} color="#f9bf4f" isAnalyzing={isAnalyzing} />
      </Canvas>
    </div>
  );
}
