import { MusebookClient, type Bundle } from '../src/index.js';

// The API fixture intentionally omits size_bytes: the public field is tarball_bytes.
const manifest: Bundle = {
  tarball_url: 'https://musebook.trade/clawd-skills.tar.gz',
  sha256: 'e40c3c96f24f84feaeec00c897477e73a7cba00b12a2f5d45bffa5703fa56493',
  tarball_bytes: 22358841,
  skill_count: 214,
  connector_count: 16,
  generated_at: '2026-10-02T16:12:05.430239+00:00',
  install_steps: [],
};
void manifest;

async function useBundle(client: MusebookClient): Promise<void> {
  const bundle = await client.bundle();
  const bytes: number = bundle.tarball_bytes;
  const publishedAt: string = bundle.generated_at;
  void bytes;
  void publishedAt;
}
void useBundle;
