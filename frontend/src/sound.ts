// Small synthesized sound effects. Nothing is downloaded: each sound is
// built from oscillators and filtered noise with the Web Audio API.
export type Sound =
  | "select"
  | "move"
  | "capture"
  | "check"
  | "solved"
  | "missed"
  | "hint"
  | "complete";

const KEY = "chesso-sound";
let context: AudioContext | null = null;

export function soundEnabled() {
  try {
    return localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}
export function setSoundEnabled(on: boolean) {
  try {
    localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    /* Sound still toggles for this page without storage. */
  }
  window.dispatchEvent(new Event("chesso-sound-setting"));
}

function audio() {
  const Context =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!Context) return null;
  context ??= new Context();
  if (context.state === "suspended") context.resume().catch(() => {});
  return context;
}

// A wooden tap: a short band-passed noise burst over a low thump.
function tap(ctx: AudioContext, at: number, gain: number, pitch: number) {
  const length = Math.floor(ctx.sampleRate * 0.05);
  const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < length; i++)
    data[i] = (Math.random() * 2 - 1) * (1 - i / length) ** 3;
  const noise = ctx.createBufferSource();
  noise.buffer = buffer;
  const band = ctx.createBiquadFilter();
  band.type = "bandpass";
  band.frequency.value = pitch * 10;
  band.Q.value = 1.4;
  const noiseGain = ctx.createGain();
  noiseGain.gain.value = gain;
  noise.connect(band).connect(noiseGain).connect(ctx.destination);
  noise.start(at);

  const body = ctx.createOscillator();
  body.type = "sine";
  body.frequency.setValueAtTime(pitch, at);
  body.frequency.exponentialRampToValueAtTime(pitch * 0.6, at + 0.08);
  const bodyGain = ctx.createGain();
  bodyGain.gain.setValueAtTime(gain * 0.9, at);
  bodyGain.gain.exponentialRampToValueAtTime(0.0001, at + 0.09);
  body.connect(bodyGain).connect(ctx.destination);
  body.start(at);
  body.stop(at + 0.1);
}

function tone(
  ctx: AudioContext,
  at: number,
  frequency: number,
  duration: number,
  gain: number,
  type: OscillatorType = "sine",
) {
  const osc = ctx.createOscillator();
  osc.type = type;
  osc.frequency.value = frequency;
  const env = ctx.createGain();
  env.gain.setValueAtTime(0.0001, at);
  env.gain.exponentialRampToValueAtTime(gain, at + 0.012);
  env.gain.exponentialRampToValueAtTime(0.0001, at + duration);
  osc.connect(env).connect(ctx.destination);
  osc.start(at);
  osc.stop(at + duration + 0.02);
}

export function play(sound: Sound) {
  if (!soundEnabled()) return;
  window.dispatchEvent(new CustomEvent("chesso-sound", { detail: sound }));
  // Build the sound after the click's frame paints, so audio setup never
  // delays visual feedback.
  setTimeout(() => render(sound), 0);
}
function render(sound: Sound) {
  const ctx = audio();
  if (!ctx) return;
  const now = ctx.currentTime + 0.005;
  switch (sound) {
    case "select":
      tap(ctx, now, 0.05, 260);
      break;
    case "move":
      tap(ctx, now, 0.22, 180);
      break;
    case "capture":
      tap(ctx, now, 0.3, 150);
      tap(ctx, now + 0.035, 0.18, 120);
      break;
    case "check":
      tap(ctx, now, 0.22, 180);
      tone(ctx, now + 0.04, 880, 0.18, 0.05, "triangle");
      break;
    case "solved":
      tone(ctx, now + 0.08, 659.25, 0.35, 0.09);
      tone(ctx, now + 0.18, 987.77, 0.5, 0.08);
      break;
    case "missed":
      tone(ctx, now + 0.05, 220, 0.3, 0.07, "triangle");
      tone(ctx, now + 0.17, 174.61, 0.4, 0.06, "triangle");
      break;
    case "hint":
      tone(ctx, now, 1318.5, 0.5, 0.04);
      tone(ctx, now, 1975.5, 0.35, 0.015);
      break;
    case "complete":
      [523.25, 659.25, 783.99, 1046.5].forEach((frequency, index) =>
        tone(ctx, now + index * 0.11, frequency, 0.5, 0.07),
      );
      break;
  }
}

// Creating the audio context costs ~100ms on slower devices. Do it during
// idle time after the first interaction, so the first board click stays fast.
if (typeof window !== "undefined") {
  const warm = () => {
    if (!soundEnabled() || context) return;
    const idle =
      window.requestIdleCallback || ((callback) => setTimeout(callback, 50));
    idle(() => audio());
  };
  window.addEventListener("pointerdown", warm, { once: true, capture: true });
  window.addEventListener("keydown", warm, { once: true, capture: true });
}
