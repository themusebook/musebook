import type { AgentCard, Network } from "./types.js";
export interface RegisteredWebMCPTool {
    name: string;
    origin: string;
    title?: string;
    description?: string;
    inputSchema?: Record<string, unknown>;
    annotations?: {
        readOnlyHint?: boolean;
        consequentialHint?: boolean;
        untrustedContentHint?: boolean;
    };
}
export interface WebMCPContext {
    getTools(): Promise<RegisteredWebMCPTool[]>;
    executeTool(tool: RegisteredWebMCPTool, input: object | string, options?: {
        signal?: AbortSignal;
    }): Promise<unknown>;
}
export interface MusebookWebMCPOptions {
    /** Defaults to document.modelContext. Override only with a trusted browser context. */
    context?: WebMCPContext;
    /** Defaults to the current document origin. Useful with an injected context. */
    expectedOrigin?: string;
    /** Current Chrome uses objects; Chrome 154 and earlier previews require json-string. */
    inputEncoding?: "object" | "json-string";
}
export interface WebMCPReadInputs {
    musebook_wallet_context: Record<string, never>;
    musebook_site_launches: {
        network: Network;
        kind?: "token" | "agent";
        limit?: number;
    };
    musebook_metaplex_launches: {
        network: Network;
        status?: "upcoming" | "live" | "graduated";
        spotlight?: boolean;
        limit?: number;
    };
    musebook_agent_card: {
        network: Network;
        address: string;
    };
}
export interface WebMCPReadResults {
    musebook_wallet_context: {
        connected: boolean;
        address: string | null;
        chain: "solana";
        tradeNetwork: "mainnet";
        requiresUserReview: true;
    };
    musebook_site_launches: {
        network: Network;
        scope: "verified_site_reports";
        count: number;
        items: Array<{
            network: Network;
            kind: "token" | "agent";
            asset: string;
            signature: string;
            creatorWallet: string;
            name: string | null;
            symbol: string | null;
            venue: string | null;
            createdAt: number;
        }>;
    };
    musebook_metaplex_launches: {
        network: Network;
        count: number;
        total: number;
        truncated: boolean;
        items: Array<{
            genesis: string;
            mint: string;
            name: string | null;
            symbol: string | null;
            status?: string;
            type?: string;
            spotlight: boolean;
            startTime?: string;
            endTime?: string | null;
        }>;
    };
    musebook_agent_card: AgentCard;
}
export declare class WebMCPUnavailableError extends Error {
    constructor(message?: string);
}
/** Read-only companion to Musebook's page tools, not a remote MCP transport or wallet executor. */
export declare class MusebookWebMCPClient {
    private readonly options;
    constructor(options?: MusebookWebMCPOptions);
    private context;
    get supported(): boolean;
    private accepts;
    tools(): Promise<RegisteredWebMCPTool[]>;
    call<Name extends keyof WebMCPReadInputs>(name: Name, input: WebMCPReadInputs[Name], options?: {
        signal?: AbortSignal;
    }): Promise<WebMCPReadResults[Name] | null>;
}
//# sourceMappingURL=webmcp.d.ts.map