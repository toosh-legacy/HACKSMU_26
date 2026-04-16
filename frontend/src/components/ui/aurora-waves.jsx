import { useRef, useEffect } from "react";
import { Renderer, Program, Mesh, Triangle, Vec2 } from "ogl";

const vertex = `
attribute vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

// Palette uses project colors:
// #2C2C2C charcoal, #E2703A sienna, #F4C842 yellow, #7A9E7E sage, #FAF0E6 linen
const fragment = `
#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 uResolution;
uniform float uTime;
uniform float uSpeed;
uniform float uGlow;

vec3 palette(float t) {
    vec3 sienna = vec3(0.886, 0.439, 0.227); // #E2703A
    vec3 yellow = vec3(0.957, 0.784, 0.259); // #F4C842
    vec3 sage   = vec3(0.478, 0.620, 0.494); // #7A9E7E
    float s = 0.5 + 0.5 * sin(t);
    float s2 = 0.5 + 0.5 * sin(t + 2.094);
    // bias heavily toward yellow, reduce sage influence
    return mix(mix(sienna, yellow, clamp(s + 0.4, 0.0, 1.0)), sage, s2 * 0.15);
}

float wave(vec2 uv, float freq, float phase) {
    return 0.35 * sin(uv.x * freq + uTime * uSpeed + phase);
}

float glow(float d, float strength) {
    return exp(-d * d * strength);
}

void main() {
    vec2 uv = (gl_FragCoord.xy / uResolution.xy) * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;

    float y = uv.y;

    float w1 = wave(uv, 3.0, 0.0);
    float w2 = wave(uv, 5.0, 1.0);
    float w3 = wave(uv, 7.0, 2.5);
    float waveLine = w1 + w2 * 0.6 + w3 * 0.4;

    float dist = abs(y - waveLine);
    float g = glow(dist, uGlow);

    vec3 col = palette(waveLine + y + uTime * 0.15);

    // Light linen bg: #FAF0E6
    vec3 bg = vec3(0.980, 0.941, 0.902);
    col = mix(bg, col, g * 1.2);

    gl_FragColor = vec4(col, 1.0);
}
`;

export default function AuroraWaves({
  speed = 0.8,
  glow = 12.0,
  resolutionScale = 1.0,
}) {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    const parent = canvas.parentElement;

    const renderer = new Renderer({
      dpr: Math.min(window.devicePixelRatio, 2),
      canvas,
    });

    const gl = renderer.gl;
    const geometry = new Triangle(gl);

    const program = new Program(gl, {
      vertex,
      fragment,
      uniforms: {
        uTime: { value: 0 },
        uResolution: { value: new Vec2() },
        uSpeed: { value: speed },
        uGlow: { value: glow },
      },
    });

    const mesh = new Mesh(gl, { geometry, program });

    const resize = () => {
      const w = parent.clientWidth;
      const h = parent.clientHeight;
      renderer.setSize(w * resolutionScale, h * resolutionScale);
      program.uniforms.uResolution.value.set(w, h);
    };

    window.addEventListener("resize", resize);
    resize();

    const start = performance.now();
    let frame = 0;

    const loop = () => {
      program.uniforms.uTime.value = (performance.now() - start) / 1000;
      renderer.render({ scene: mesh });
      frame = requestAnimationFrame(loop);
    };

    loop();

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
    };
  }, [speed, glow, resolutionScale]);

  return (
    <canvas
      ref={ref}
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", display: "block" }}
    />
  );
}
