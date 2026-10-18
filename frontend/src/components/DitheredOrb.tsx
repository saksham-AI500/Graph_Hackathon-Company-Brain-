import { useEffect, useRef } from 'react';
import { useTheme } from '../context/ThemeContext';

interface DitheredOrbProps {
  size?: number;
  className?: string;
}

export function DitheredOrb({ size = 28, className = '' }: DitheredOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { reducedMotion } = useTheme();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let gl: WebGLRenderingContext | null = null;
    try {
      gl = canvas.getContext('webgl', { antialias: false, alpha: true });
    } catch {
      gl = null;
    }

    // Fallback to 2D canvas if WebGL is unavailable
    if (!gl) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        const rad = size / 2;
        const grad = ctx.createRadialGradient(rad * 0.7, rad * 0.7, 1, rad, rad, rad);
        grad.addColorStop(0, '#c084fc');
        grad.addColorStop(0.5, '#7dd3fc');
        grad.addColorStop(1, '#3b82f6');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(rad, rad, rad - 1, 0, Math.PI * 2);
        ctx.fill();
      }
      return;
    }

    const vsSource = `
      attribute vec2 a_position;
      varying vec2 v_uv;
      void main() {
        v_uv = (a_position + 1.0) * 0.5;
        gl_Position = vec4(a_position, 0.0, 1.0);
      }
    `;

    const fsSource = `
      precision mediump float;
      varying vec2 v_uv;
      uniform float u_time;
      uniform vec2 u_resolution;

      // 4x4 Bayer dither matrix
      float bayer4(vec2 p) {
        vec2 m = mod(floor(p), 4.0);
        int x = int(m.x);
        int y = int(m.y);
        float d = 0.0;
        if (x == 0 && y == 0) d = 0.0;
        else if (x == 2 && y == 0) d = 8.0;
        else if (x == 1 && y == 0) d = 2.0;
        else if (x == 3 && y == 0) d = 10.0;
        else if (x == 0 && y == 1) d = 12.0;
        else if (x == 2 && y == 1) d = 4.0;
        else if (x == 1 && y == 1) d = 14.0;
        else if (x == 3 && y == 1) d = 6.0;
        else if (x == 0 && y == 2) d = 3.0;
        else if (x == 2 && y == 2) d = 11.0;
        else if (x == 1 && y == 2) d = 1.0;
        else if (x == 3 && y == 2) d = 9.0;
        else if (x == 0 && y == 3) d = 15.0;
        else if (x == 2 && y == 3) d = 7.0;
        else if (x == 1 && y == 3) d = 13.0;
        else if (x == 3 && y == 3) d = 5.0;
        return d / 16.0;
      }

      void main() {
        vec2 p = (v_uv - 0.5) * 2.0;
        float r = length(p);
        if (r > 1.0) {
          gl_FragColor = vec4(0.0);
          return;
        }

        // Animated organic spherical shading
        float angle = atan(p.y, p.x) + u_time * 0.4;
        float shade = (1.0 - r) * (0.6 + 0.4 * sin(angle * 2.0 + u_time));
        
        vec3 col1 = vec3(0.49, 0.83, 0.99); // #7dd3fc
        vec3 col2 = vec3(0.75, 0.52, 0.99); // #c084fc
        vec3 col3 = vec3(0.23, 0.51, 0.96); // #3b82f6

        vec3 color = mix(col1, col2, 0.5 + 0.5 * sin(u_time * 0.7 + p.x * 2.0));
        color = mix(color, col3, r * 0.8);

        // Apply Bayer dithering threshold
        float dither = bayer4(gl_FragCoord.xy);
        float lum = dot(color, vec3(0.299, 0.587, 0.114)) + (dither - 0.5) * 0.25;
        vec3 dithered = mix(color * 0.7, color * 1.3, clamp(lum, 0.0, 1.0));

        // Smooth circular edge alpha
        float alpha = smoothstep(1.0, 0.92, r);
        gl_FragColor = vec4(dithered, alpha);
      }
    `;

    function createShader(glCtx: WebGLRenderingContext, type: number, src: string) {
      const shader = glCtx.createShader(type);
      if (!shader) return null;
      glCtx.shaderSource(shader, src);
      glCtx.compileShader(shader);
      if (!glCtx.getShaderParameter(shader, glCtx.COMPILE_STATUS)) {
        glCtx.deleteShader(shader);
        return null;
      }
      return shader;
    }

    const vs = createShader(gl, gl.VERTEX_SHADER, vsSource);
    const fs = createShader(gl, gl.FRAGMENT_SHADER, fsSource);
    if (!vs || !fs) return;

    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;

    gl.useProgram(program);

    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );

    const posLocation = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(posLocation);
    gl.vertexAttribPointer(posLocation, 2, gl.FLOAT, false, 0, 0);

    const timeLocation = gl.getUniformLocation(program, 'u_time');
    const resLocation = gl.getUniformLocation(program, 'u_resolution');
    gl.uniform2f(resLocation, size, size);

    let animationFrameId: number;
    let startTime = performance.now();
    let isPaused = false;

    const render = (now: number) => {
      if (!gl) return;
      gl.viewport(0, 0, size, size);
      const time = reducedMotion ? 1.0 : (now - startTime) * 0.001;
      gl.uniform1f(timeLocation, time);
      gl.drawArrays(gl.TRIANGLES, 0, 6);

      if (!reducedMotion && !isPaused) {
        animationFrameId = requestAnimationFrame(render);
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        isPaused = true;
        cancelAnimationFrame(animationFrameId);
      } else {
        isPaused = false;
        if (!reducedMotion) {
          startTime = performance.now();
          animationFrameId = requestAnimationFrame(render);
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    // Initial render
    render(performance.now());

    return () => {
      cancelAnimationFrame(animationFrameId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (gl) {
        gl.deleteProgram(program);
        gl.deleteShader(vs);
        gl.deleteShader(fs);
      }
    };
  }, [size, reducedMotion]);

  return (
    <canvas
      ref={canvasRef}
      width={size}
      height={size}
      className={`rounded-full shadow-inner ${className}`}
      style={{ width: `${size}px`, height: `${size}px` }}
      aria-label="RepoBrain WebGL Orb"
    />
  );
}
