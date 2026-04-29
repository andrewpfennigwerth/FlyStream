import { useEffect, useRef } from 'react';

const SHADER_UNIFORMS = {
  u_color: [0, 0, 0],
  u_size: 28.25,
  u_phase: 0.15,
  u_gain: 0.219,
  u_octaves: 8,
  u_lacunarity: 4.733,
  u_factor: 0.728,
  u_width: 0.19,
};

const VERTEX_SHADER = `#version 300 es
in vec2 a_position;

void main() {
  gl_Position = vec4(a_position, 0.0, 1.0);
}`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

uniform vec2 u_resolution;
uniform float u_time;
uniform vec3 u_color;
uniform float u_size;
uniform float u_phase;
uniform float u_gain;
uniform int u_octaves;
uniform float u_lacunarity;
uniform float u_factor;
uniform float u_width;

out vec4 outColor;

vec2 hash2(vec2 p) {
  p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
  return fract(sin(p) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);

  float a = dot(hash2(i + vec2(0.0, 0.0)) - 0.5, f - vec2(0.0, 0.0));
  float b = dot(hash2(i + vec2(1.0, 0.0)) - 0.5, f - vec2(1.0, 0.0));
  float c = dot(hash2(i + vec2(0.0, 1.0)) - 0.5, f - vec2(0.0, 1.0));
  float d = dot(hash2(i + vec2(1.0, 1.0)) - 0.5, f - vec2(1.0, 1.0));

  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y) + 0.5;
}

float fbm(vec2 p) {
  float value = 0.0;
  float amplitude = u_gain * 1.8;
  float frequency = 1.0;

  for (int i = 0; i < 8; i++) {
    if (i >= u_octaves) {
      break;
    }

    value += amplitude * pow(abs(noise(p * frequency)), max(u_factor, 0.001));
    frequency *= floor(u_lacunarity);
    amplitude *= u_gain;
    p += vec2(u_phase * 9.0, u_phase * 5.0);
  }

  return value;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution.xy;
  vec2 aspect = vec2(u_resolution.x / max(u_resolution.y, 1.0), 1.0);
  vec2 p = uv * aspect * max(u_resolution.y / max(u_size, 1.0), 1.0) * 0.05;

  float value = fbm(p + vec2(u_time * 0.015, -u_time * 0.01));
  float contour = fract(value * 10.0);
  float line = smoothstep(1.0 - u_width, 1.0, contour);
  line *= 0.22;

  outColor = vec4(u_color, line);
}`;

function createShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);

  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error(gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }

  return shader;
}

function createProgram(gl) {
  const vertexShader = createShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);

  if (!vertexShader || !fragmentShader) {
    return null;
  }

  const program = gl.createProgram();
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error(gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }

  return program;
}

export default function ShaderBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas.getContext('webgl2', { alpha: true, antialias: true });

    if (!gl) {
      return undefined;
    }

    const program = createProgram(gl);
    if (!program) {
      return undefined;
    }

    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );

    const positionLocation = gl.getAttribLocation(program, 'a_position');
    const uniformLocations = {
      resolution: gl.getUniformLocation(program, 'u_resolution'),
      time: gl.getUniformLocation(program, 'u_time'),
      color: gl.getUniformLocation(program, 'u_color'),
      size: gl.getUniformLocation(program, 'u_size'),
      phase: gl.getUniformLocation(program, 'u_phase'),
      gain: gl.getUniformLocation(program, 'u_gain'),
      octaves: gl.getUniformLocation(program, 'u_octaves'),
      lacunarity: gl.getUniformLocation(program, 'u_lacunarity'),
      factor: gl.getUniformLocation(program, 'u_factor'),
      width: gl.getUniformLocation(program, 'u_width'),
    };

    let animationFrameId;

    function resize() {
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.floor(window.innerWidth * pixelRatio);
      const height = Math.floor(window.innerHeight * pixelRatio);

      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        gl.viewport(0, 0, width, height);
      }
    }

    function render(time) {
      resize();
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.useProgram(program);

      gl.enableVertexAttribArray(positionLocation);
      gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
      gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

      gl.uniform2f(uniformLocations.resolution, canvas.width, canvas.height);
      gl.uniform1f(uniformLocations.time, time * 0.001);
      gl.uniform3fv(uniformLocations.color, SHADER_UNIFORMS.u_color);
      gl.uniform1f(uniformLocations.size, SHADER_UNIFORMS.u_size);
      gl.uniform1f(uniformLocations.phase, SHADER_UNIFORMS.u_phase);
      gl.uniform1f(uniformLocations.gain, SHADER_UNIFORMS.u_gain);
      gl.uniform1i(uniformLocations.octaves, SHADER_UNIFORMS.u_octaves);
      gl.uniform1f(uniformLocations.lacunarity, SHADER_UNIFORMS.u_lacunarity);
      gl.uniform1f(uniformLocations.factor, SHADER_UNIFORMS.u_factor);
      gl.uniform1f(uniformLocations.width, SHADER_UNIFORMS.u_width);
      gl.drawArrays(gl.TRIANGLES, 0, 6);

      animationFrameId = requestAnimationFrame(render);
    }

    animationFrameId = requestAnimationFrame(render);
    window.addEventListener('resize', resize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', resize);
      gl.deleteBuffer(positionBuffer);
      gl.deleteProgram(program);
    };
  }, []);

  return <canvas className="shader-background" ref={canvasRef} aria-hidden="true" />;
}
