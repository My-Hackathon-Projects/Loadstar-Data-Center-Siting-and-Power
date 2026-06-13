import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import {
  AdditiveBlending,
  type BufferAttribute,
  CanvasTexture,
  MathUtils,
  type Points,
  type Texture,
} from "three";

import { COLOR } from "../../../styles/tokens";
import { JOURNEY_TIMING, STARFIELD } from "../constants";

const FLIGHT_SECONDS = JOURNEY_TIMING.flightMs / 1000;

function easeOut(t: number): number {
  return 1 - Math.pow(1 - Math.min(Math.max(t, 0), 1), 3);
}

/**
 * A soft round star: a radial luminance falloff from the primary text token to
 * transparent. Used as the point sprite so the stars read as gentle glows
 * rather than square blocks. The center color is a token; the edge is a pure
 * alpha fade, so no raw palette color is introduced.
 */
function makeStarSprite(): Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const gradient = ctx.createRadialGradient(
      size / 2,
      size / 2,
      0,
      size / 2,
      size / 2,
      size / 2,
    );
    gradient.addColorStop(0, COLOR.textPrimary);
    gradient.addColorStop(0.35, COLOR.textPrimary);
    gradient.addColorStop(1, "transparent");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);
  }
  return new CanvasTexture(canvas);
}

/**
 * A single BufferGeometry of a few thousand points, additive-blended, drawn in
 * one call. The camera holds at the origin while the stars stream toward it,
 * easing from intense to gentle over the flight. No postprocessing.
 */
function Starfield() {
  const pointsRef = useRef<Points>(null);
  const startRef = useRef<number>(performance.now());

  const sprite = useMemo(makeStarSprite, []);

  const positions = useMemo(() => {
    const array = new Float32Array(STARFIELD.count * 3);
    for (let i = 0; i < STARFIELD.count; i += 1) {
      array[i * 3] = (Math.random() - 0.5) * STARFIELD.spreadXY;
      array[i * 3 + 1] = (Math.random() - 0.5) * STARFIELD.spreadXY;
      array[i * 3 + 2] = -Math.random() * STARFIELD.depth;
    }
    return array;
  }, []);

  useFrame((_, delta) => {
    const points = pointsRef.current;
    if (!points) {
      return;
    }
    const elapsed = (performance.now() - startRef.current) / 1000;
    const progress = elapsed / FLIGHT_SECONDS;
    const speed = MathUtils.lerp(
      STARFIELD.speedMax,
      STARFIELD.speedMin,
      easeOut(progress),
    );
    const attribute = points.geometry.attributes.position as BufferAttribute;
    const array = attribute.array as Float32Array;
    const step = speed * Math.min(delta, 0.05);
    for (let i = 0; i < STARFIELD.count; i += 1) {
      const zIndex = i * 3 + 2;
      array[zIndex] += step;
      if (array[zIndex] > STARFIELD.recycleZ) {
        array[zIndex] = -STARFIELD.depth;
        array[i * 3] = (Math.random() - 0.5) * STARFIELD.spreadXY;
        array[i * 3 + 1] = (Math.random() - 0.5) * STARFIELD.spreadXY;
      }
    }
    attribute.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        alphaMap={sprite}
        blending={AdditiveBlending}
        color={COLOR.textPrimary}
        depthWrite={false}
        map={sprite}
        opacity={0.95}
        size={2.4}
        sizeAttenuation
        transparent
      />
    </points>
  );
}

/** Full-screen flight canvas. Lazy-imported so three lands in a /-only chunk. */
export default function Flight() {
  return (
    <Canvas
      camera={{ position: [0, 0, 0], fov: 75, near: 0.1, far: 1000 }}
      dpr={[1, 2]}
      gl={{ antialias: true }}
    >
      <color args={[COLOR.bgVoid]} attach="background" />
      <Starfield />
    </Canvas>
  );
}
