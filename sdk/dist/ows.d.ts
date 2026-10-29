/** Optional local Node.js wallet integration. Never import into a browser bundle. */
export declare const OWS_SOLANA_CHAIN = "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp";
export interface OWSSolanaWallet {
    id: string;
    name: string;
    createdAt: string;
    address: string;
    chainId: typeof OWS_SOLANA_CHAIN;
    derivationPath: string;
}
export interface OWSSignature {
    wallet: OWSSolanaWallet;
    /** Detached Ed25519 signature; not a signed transaction envelope. */
    signature: string;
    encoding: 'hex';
    signatureBase64: string;
}
export interface OWSClient {
    /** Creates a 24-word encrypted OWS wallet; returns only its public Solana account. */
    createWallet(input: {
        name: string;
        passphrase: string;
    }): OWSSolanaWallet;
    listWallets(): OWSSolanaWallet[];
    getWallet(nameOrId: string): OWSSolanaWallet;
    /** Owner passphrase or an ows_key_ token. Tokens retain native OWS policy enforcement. */
    signMessage(input: {
        wallet: string;
        message: string;
        credential: string;
    }): OWSSignature;
    /** Full serialized Solana transaction as hex, including signature slots. No broadcast. */
    signTransaction(input: {
        wallet: string;
        transactionHex: string;
        credential: string;
    }): OWSSignature;
}
/**
 * Load the optional official OWS 1.4.3 native SDK. Install it alongside Musebook:
 * npm install @musebook/sdk @open-wallet-standard/core@1.4.3
 * Native binaries support macOS/glibc Linux on ARM64/x64. Vault defaults to ~/.ows.
 * Credentials are passed explicitly per operation and are never retained by this client.
 */
export declare function createOWSClient(options?: {
    vaultPath?: string;
}): Promise<OWSClient>;
//# sourceMappingURL=ows.d.ts.map