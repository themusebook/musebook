import type { LoaderConfig } from './config.js';

const DIM = '\x1b[2m';
const RESET = '\x1b[0m';

const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

// Solana shimmer: purple -> magenta -> green wave over the loader text.
const SHIMMER = [
  '\x1b[38;5;93m', // purple
  '\x1b[38;5;135m',
  '\x1b[38;5;177m',
  '\x1b[38;5;84m', // green
  '\x1b[38;5;177m',
  '\x1b[38;5;135m',
];

export class Loader {
  private config: LoaderConfig;
  private frame = 0;
  private interval: ReturnType<typeof setInterval> | null = null;

  constructor(config: LoaderConfig) {
    this.config = config;
  }

  start(): void {
    this.stop();
    this.frame = 0;
    const ms =
      this.config.style === 'gradient' ? 120 : this.config.style === 'spinner' ? 80 : 300;
    this.interval = setInterval(() => this.draw(), ms);
  }

  stop(): void {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
      process.stdout.write('\r\x1b[K');
    }
  }

  get running(): boolean {
    return this.interval !== null;
  }

  private draw(): void {
    const { text, style } = this.config;
    this.frame++;

    if (style === 'minimal') {
      const dots = ['·', '··', '···'];
      process.stdout.write(`\r${DIM}${text}${dots[this.frame % 3]}${RESET}`);
      return;
    }
    if (style === 'spinner') {
      const char = SPINNER_FRAMES[this.frame % SPINNER_FRAMES.length];
      process.stdout.write(`\r${DIM}${char} ${text}${RESET}`);
      return;
    }
    // gradient: scrolling Solana shimmer
    const len = SHIMMER.length;
    let out = '\r';
    for (let i = 0; i < text.length; i++) {
      out += SHIMMER[(this.frame + i) % len] + text[i];
    }
    out += RESET;
    process.stdout.write(out);
  }
}
