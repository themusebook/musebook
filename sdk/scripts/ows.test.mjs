import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, readFile, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createPublicKey, verify } from 'node:crypto';
import { createOWSClient, OWS_SOLANA_CHAIN } from '../dist/ows.js';
import * as native from '@open-wallet-standard/core';

function publicKey(address) {
  const alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  let n = 0n;
  for (const c of address) n = n * 58n + BigInt(alphabet.indexOf(c));
  const raw = Buffer.from(n.toString(16).padStart(64, '0'), 'hex');
  return { raw, key: createPublicKey({ key: Buffer.concat([Buffer.from('302a300506032b6570032100', 'hex'), raw]), format: 'der', type: 'spki' }) };
}
test('SDK OWS entry creates real encrypted wallets and verifies message and transaction signatures', async () => {
  const vaultPath = await mkdtemp(join(tmpdir(), 'musebook-sdk-ows-'));
  const passphrase = 'sdk-test-only-passphrase-123';
  try {
    const ows = await createOWSClient({ vaultPath });
    const wallet = ows.createWallet({ name: 'sdk-fixture', passphrase });
    assert.equal(wallet.chainId, OWS_SOLANA_CHAIN);
    assert.deepEqual(ows.getWallet(wallet.id), wallet);
    assert.equal(ows.listWallets().length, 1);
    assert.throws(() => ows.createWallet({ name: 'sdk-fixture', passphrase }), /already exists/);
    const file = join(vaultPath, 'wallets', wallet.id + '.json');
    assert.equal((await stat(file)).mode & 0o777, 0o600);
    const envelope = JSON.parse(await readFile(file, 'utf8'));
    assert.equal(envelope.crypto.cipher, 'aes-256-gcm');
    const { raw, key } = publicKey(wallet.address);
    const message = 'Approve this Musebook SDK sign-in test';
    const signed = ows.signMessage({ wallet: wallet.id, message, credential: passphrase });
    assert.ok(verify(null, Buffer.from(message), key, Buffer.from(signed.signatureBase64, 'base64')));
    assert.equal(Buffer.from(signed.signature, 'hex').toString('base64'), signed.signatureBase64);
    // Valid legacy transaction, one signer, zero instructions; never broadcast.
    const txMessage = Buffer.concat([Buffer.from([1,0,0,1]), raw, Buffer.alloc(32, 1), Buffer.from([0])]);
    const tx = Buffer.concat([Buffer.from([1]), Buffer.alloc(64), txMessage]);
    const transaction = ows.signTransaction({ wallet: wallet.id, transactionHex: tx.toString('hex'), credential: passphrase });
    assert.ok(verify(null, txMessage, key, Buffer.from(transaction.signature, 'hex')));
    assert.throws(() => ows.signTransaction({ wallet: wallet.id, transactionHex: 'invalid', credential: passphrase }), /transactionHex/);
    assert.throws(() => ows.signMessage({ wallet: wallet.id, message, credential: '' }), /explicit/);
    assert.throws(() => ows.signMessage({ wallet: wallet.id, message, credential: 'ows_key_invalid' }), /Malformed/);
    const policy = { id: 'deny-solana', name: 'Base only', version: 1, created_at: new Date().toISOString(), rules: [{ type: 'allowed_chains', chain_ids: ['eip155:8453'] }], action: 'deny' };
    native.createPolicy(JSON.stringify(policy), vaultPath);
    const agentKey = native.createApiKey('denied-agent', [wallet.id], [policy.id], passphrase, undefined, vaultPath);
    assert.throws(() => ows.signMessage({ wallet: wallet.id, message, credential: agentKey.token }), /policy|chain/i);
    assert.throws(() => ows.signTransaction({ wallet: wallet.id, transactionHex: tx.toString('hex'), credential: agentKey.token }), /policy|chain/i);
    native.revokeApiKey(agentKey.id, vaultPath);
    assert.throws(() => ows.signMessage({ wallet: wallet.id, message, credential: agentKey.token }), /key|token/i);
  } finally { await rm(vaultPath, { recursive: true, force: true }); }
});
