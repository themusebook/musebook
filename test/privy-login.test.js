"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const vm = require("node:vm");
const { spawnSync } = require("node:child_process");

const source = fs.readFileSync(path.join(__dirname, "../lib/privy.js"), "utf8");
const device = {
  device_code: "secret-test-device-code",
  user_code: "HUMAN-CODE1",
  verification_uri: "https://musebook.trade/authorize",
  expires_in: 600,
  interval: 5,
};
const tokens = { access_token: "secret-test-access", refresh_token: "secret-test-refresh", expires_in: 900 };

function harness(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "musebook-login-test-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const clock = { now: Date.now() };
  const requests = [];
  const output = [];
  const responses = [];
  function load() {
    const module = { exports: {} };
    const context = {
      module,
      require: (name) => name === "os" ? { ...os, homedir: () => root } : require(name),
      process: { env: {}, pid: process.pid },
      Buffer, URL, AbortSignal,
      Date: class extends Date { static now() { return clock.now; } },
      console: { log: (...args) => output.push(args.join(" ")), error: (...args) => output.push(args.join(" ")) },
      setTimeout: (fn, ms) => { clock.now += ms; queueMicrotask(fn); },
      fetch: async (url, init) => {
        requests.push({ url, init, body: JSON.parse(init.body || "null") });
        let reply;
        if (url.endsWith("/device_authorization")) reply = [200, device];
        else if (url.endsWith("/wallets/authenticate")) reply = [503, { error: "wallet service temporarily unavailable" }];
        else reply = responses.shift() || [400, { error: "authorization_pending" }];
        if (reply instanceof Error) throw reply;
        return { status: reply[0], text: async () => JSON.stringify(reply[1]) };
      },
    };
    vm.runInNewContext(source, context, { filename: "lib/privy.js" });
    return module.exports;
  }
  return { root, clock, requests, output, responses, load, pendingFile: path.join(root, ".config/musebook-cli/privy-login.enc") };
}

test("an agent starts login, exits, and resumes the same encrypted request", async (t) => {
  const h = harness(t);
  const start = await h.load().deviceLogin({ mode: "start", json: true });
  assert.equal(start.status, "pending");
  assert.equal(start.user_code, device.user_code);
  assert.equal(new URL(start.verification_uri_complete).searchParams.get("user_code"), device.user_code);
  assert.equal(h.requests.length, 1);
  assert.equal(fs.statSync(h.pendingFile).mode & 0o777, 0o600);
  assert.equal(fs.statSync(path.dirname(h.pendingFile)).mode & 0o777, 0o700);
  assert.ok(!fs.readFileSync(h.pendingFile, "utf8").includes(device.device_code));
  assert.ok(!JSON.stringify(start).includes(device.device_code));
  const resumed = await h.load().deviceLogin({ mode: "start", json: true });
  assert.equal(resumed.user_code, start.user_code);
  assert.equal(h.requests.length, 1);
  await h.load().deviceLogin({ mode: "check", json: true });
  assert.equal(h.requests.length, 1, "early checks must not poll the provider");
  h.clock.now += 5000;
  await h.load().deviceLogin({ mode: "check", json: true });
  assert.equal(h.requests[1].body.grant_type, "urn:ietf:params:oauth:grant-type:device_code");
  assert.equal(h.requests[1].body.device_code, device.device_code);
  assert.ok(h.requests[1].init.signal);
});

test("approval is saved even when wallet discovery fails", async (t) => {
  const h = harness(t);
  await h.load().deviceLogin({ mode: "start", json: true });
  h.clock.now += 5000;
  h.responses.push([200, tokens]);
  const result = await h.load().deviceLogin({ mode: "check", json: true });
  assert.equal(result.status, "approved");
  assert.equal(result.logged_in, true);
  assert.equal(result.wallet_discovery, "failed");
  assert.match(result.warning, /wallet discovery failed/);
  assert.equal(h.load().sessionLoad().refresh_token, tokens.refresh_token);
  assert.equal(h.load().pendingLoginStatus(), null);
  assert.ok(!fs.existsSync(h.pendingFile));
  const sessionFile = path.join(h.root, ".config/musebook-cli/privy-session.enc");
  assert.equal(fs.statSync(sessionFile).mode & 0o777, 0o600);
  const visible = JSON.stringify(result) + h.output.join("\n") + fs.readFileSync(sessionFile, "utf8");
  for (const secret of [device.device_code, tokens.access_token, tokens.refresh_token]) assert.ok(!visible.includes(secret));
  const checked = await h.load().deviceLogin({ mode: "check", json: true });
  assert.equal(checked.status, "approved");
  assert.equal(checked.wallet_discovery, "failed");
  assert.match(checked.warning, /wallet discovery failed/);
});

test("rate limiting survives process restarts", async (t) => {
  const h = harness(t);
  await h.load().deviceLogin({ mode: "start", json: true });
  h.clock.now += 5000;
  h.responses.push([400, { error: "slow_down" }]);
  const result = await h.load().deviceLogin({ mode: "check", json: true });
  assert.equal(result.retry_after, 10);
  h.clock.now += 5000;
  await h.load().deviceLogin({ mode: "check", json: true });
  assert.equal(h.requests.length, 2);
  h.clock.now += 5000;
  await h.load().deviceLogin({ mode: "check", json: true });
  assert.equal(h.requests.length, 3);
});

test("a network interruption leaves login resumable", async (t) => {
  const h = harness(t);
  await h.load().deviceLogin({ mode: "start", json: true });
  h.clock.now += 5000;
  h.responses.push(new Error("request timed out"));
  const result = await h.load().deviceLogin({ mode: "check", json: true });
  assert.equal(result.status, "pending");
  assert.equal(result.warning, "network_error");
  assert.equal(h.load().pendingLoginStatus().user_code, device.user_code);
});

test("wait mode survives provider errors and reports approval immediately", async (t) => {
  const h = harness(t);
  h.responses.push([503, { error: "unavailable" }], [200, tokens]);
  const result = await h.load().deviceLogin();
  assert.equal(result.status, "approved");
  assert.ok(h.output.some((line) => line.includes("Approval received. Login saved")));
});

test("denied and expired requests are cleared without saving a session", async (t) => {
  for (const error of ["access_denied", "expired_token"]) {
    const h = harness(t);
    await h.load().deviceLogin({ mode: "start", json: true });
    h.clock.now += 5000;
    h.responses.push([400, { error }]);
    await assert.rejects(h.load().deviceLogin({ mode: "check", json: true }), /denied|expired/);
    assert.equal(h.load().sessionLoad(), null);
    assert.ok(!fs.existsSync(h.pendingFile));
  }
});

test("expired requests are not polled, and logout removes pending login", async (t) => {
  const h = harness(t);
  await h.load().deviceLogin({ mode: "start", json: true });
  h.clock.now += 600000;
  await assert.rejects(h.load().deviceLogin({ mode: "check", json: true }), /expired/);
  assert.equal(h.requests.length, 1);
  await h.load().deviceLogin({ mode: "start", json: true });
  h.load().sessionDelete();
  assert.equal(h.load().pendingLoginStatus(), null);
});

test("CLI agent commands emit a single JSON value without leaking secrets", (t) => {
  const h = harness(t);
  const cli = path.join(__dirname, "../bin/musebook.js");
  function run(args) {
    const script = `require('os').homedir = () => ${JSON.stringify(h.root)};
      global.fetch = async () => ({status:200,text:async()=>JSON.stringify(${JSON.stringify(device)})});
      process.argv = ['node', ${JSON.stringify(cli)}, ...${JSON.stringify(args)}];
      require(${JSON.stringify(cli)});`;
    return spawnSync(process.execPath, ["-e", script], { encoding: "utf8", timeout: 5000 });
  }
  const loggedOut = run(["status", "--json"]);
  assert.equal(JSON.parse(loggedOut.stdout).logged_in, false);
  const start = run(["login", "--start", "--json"]);
  assert.equal(start.status, 0, start.stderr);
  assert.equal(JSON.parse(start.stdout).user_code, device.user_code);
  assert.ok(!start.stdout.includes(device.device_code));
  const check = run(["login", "--check", "--json"]);
  assert.equal(check.status, 0, check.stderr);
  assert.equal(JSON.parse(check.stdout).status, "pending");
  const invalid = run(["login", "--start", "--wait", "--json"]);
  assert.equal(invalid.status, 1);
  assert.equal(JSON.parse(invalid.stdout).status, "error");
});
