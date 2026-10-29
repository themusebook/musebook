const READ_TOOLS = new Set([
    "musebook_wallet_context", "musebook_site_launches", "musebook_metaplex_launches", "musebook_agent_card",
]);
export class WebMCPUnavailableError extends Error {
    constructor(message = "WebMCP is unavailable. Open Musebook in a compatible browser with its page tools enabled.") {
        super(message);
        this.name = "WebMCPUnavailableError";
    }
}
/** Read-only companion to Musebook's page tools, not a remote MCP transport or wallet executor. */
export class MusebookWebMCPClient {
    options;
    constructor(options = {}) {
        this.options = options;
    }
    context() {
        const doc = typeof document === "undefined" ? undefined : document;
        return this.options.context ?? doc?.modelContext;
    }
    get supported() {
        const context = this.context();
        return typeof context?.getTools === "function" && typeof context.executeTool === "function";
    }
    accepts(tool) {
        const origin = this.options.expectedOrigin ?? (typeof location === "undefined" ? undefined : location.origin);
        return READ_TOOLS.has(tool.name)
            && tool.annotations?.readOnlyHint === true && tool.annotations.consequentialHint !== true
            && (!origin || tool.origin === origin);
    }
    async tools() {
        const context = this.context();
        if (!context || !this.supported)
            throw new WebMCPUnavailableError();
        return (await context.getTools()).filter(tool => this.accepts(tool));
    }
    async call(name, input, options = {}) {
        if (!READ_TOOLS.has(name))
            throw new Error("This SDK entry point only invokes the four Musebook discovery tools.");
        options.signal?.throwIfAborted();
        const context = this.context();
        if (!context || !this.supported)
            throw new WebMCPUnavailableError();
        const tools = (await context.getTools()).filter(tool => tool.name === name && this.accepts(tool));
        options.signal?.throwIfAborted();
        if (tools.length !== 1)
            throw new WebMCPUnavailableError(`Expected one trusted ${name} tool; found ${tools.length}.`);
        const args = this.options.inputEncoding === "json-string" ? JSON.stringify(input) : input;
        // Keep the native receiver and RegisteredTool object. Never retry execution on a type error.
        const result = await context.executeTool(tools[0], args, options);
        return (typeof result === "string" ? JSON.parse(result) : result);
    }
}
//# sourceMappingURL=webmcp.js.map