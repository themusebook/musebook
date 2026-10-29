// Solana brand gradient: purple #9945FF -> green #14F195, mapped onto the
// 256-color cube. Interpolated per column so the banner shimmers left->right.

const RESET = '\x1b[0m';
const BOLD = '\x1b[1m';
const DIM = '\x1b[2m';

const PURPLE: [number, number, number] = [0x99, 0x45, 0xff];
const GREEN: [number, number, number] = [0x14, 0xf1, 0x95];

function lerp(a: number, b: number, t: number): number {
  return Math.round(a + (b - a) * t);
}

// Map an RGB triple to the nearest 256-color cube entry (16-231).
function toAnsi256([r, g, b]: [number, number, number]): number {
  const q = (v: number) => Math.max(0, Math.min(5, Math.round(v / 51)));
  return 16 + 36 * q(r) + 6 * q(g) + q(b);
}

const LOGO = [
  '█   █ █   █ █████ █████ ██████   ███   ███  █   █',
  '██ ██ █   █ █     █     █     █ █   █ █   █ █  █ ',
  '█ █ █ █   █ ████  ████  ██████  █   █ █   █ ███  ',
  '█   █ █   █     █ █     █   █   █   █ █   █ █  █ ',
  '█   █  ███  █████ █████ ██████   ███   ███  █   █',
];

function gradientLine(line: string): string {
  let out = '';
  const n = line.length;
  for (let i = 0; i < n; i++) {
    const ch = line[i];
    if (ch === ' ') {
      out += ' ';
      continue;
    }
    const t = n <= 1 ? 0 : i / (n - 1);
    const rgb: [number, number, number] = [
      lerp(PURPLE[0], GREEN[0], t),
      lerp(PURPLE[1], GREEN[1], t),
      lerp(PURPLE[2], GREEN[2], t),
    ];
    out += `\x1b[38;5;${toAnsi256(rgb)}m${ch}`;
  }
  return out + RESET;
}

export function printBanner(model: string, version: string): void {
  console.log();
  for (const line of LOGO) console.log(BOLD + gradientLine(line) + RESET);
  console.log(
    `  ${DIM}🦞 musebook-tui ${version}  ·  model ${RESET}${model}${DIM}  ·  type /help${RESET}`,
  );
  console.log();
}
