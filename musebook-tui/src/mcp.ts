import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { AsyncLocalStorage } from 'node:async_hooks';

const requestUrl = new AsyncLocalStorage<string>();
export const withMcpUrl = <T>(url: string, run: () => T): T => requestUrl.run(url, run);
export const configuredMcpUrl = (): string => requestUrl.getStore() ?? process.env.MUSEBOOK_MCP_URL ?? 'https://musebook.trade/mcp';

export interface McpConnection {
  client: Client;
  url: string;
  close: () => Promise<void>;
}

const connections = new Map<string, Promise<McpConnection>>();

export async function getMcpConnection(url: string): Promise<McpConnection> {
  const existing = connections.get(url);
  if (existing) return existing;
  const pending = (async (): Promise<McpConnection> => {
    const client = new Client({ name: 'musebook-tui', version: '0.1.2' });
    try {
      await client.connect(new StreamableHTTPClientTransport(new URL(url)));
      return { client, url, close: async () => {
        await client.close().catch(() => {});
        connections.delete(url);
      } };
    } catch (error) {
      await client.close().catch(() => {});
      connections.delete(url);
      throw error;
    }
  })();
  connections.set(url, pending);
  return pending;
}

/** Call a remote MCP tool and return the parsed payload (JSON when possible). */
export async function callMcpTool(
  url: string,
  name: string,
  args: Record<string, unknown>,
): Promise<unknown> {
  const { client } = await getMcpConnection(url);
  const res = await client.callTool({ name, arguments: args });
  const blocks = (res.content ?? []) as Array<{ type: string; text?: string }>;
  const texts = blocks.filter((b) => b.type === 'text').map((b) => b.text ?? '');
  const joined = texts.join('\n');
  if ((res as { isError?: boolean }).isError) {
    return { error: joined || `MCP tool ${name} failed` };
  }
  try {
    return JSON.parse(joined);
  } catch {
    return { text: joined };
  }
}

export async function closeMcp(): Promise<void> {
  await Promise.allSettled([...connections.values()].map(async pending => (await pending).close()));
}
