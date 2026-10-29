#!/usr/bin/env python3
"""Stonkfun LaunchLab launch planner (self-built path).

The API launch-prepare flow is DISABLED on the platform
(POST /launches/prepare -> 503 "launch through LaunchLab instead").
The live path is the self-built one: read /pairs + /launchlab/pricing,
construct the Raydium LaunchLab initialize_with_token2022, sign it
(creator + fresh mint keypair), broadcast it yourself. The platform
adopts the pool within ~1-2 min when the shape matches its pricing.

This tool does everything up to signing:
  plan  --quote-mint MINT --name NAME --symbol SYM --tax-bps 0|100|300
        [--metadata-uri ipfs://... | --metadata-file meta.json |
         --image art.png --description "..."]
  check --mint MINT        # adoption check: launchpad == "launchlab"?

Signing is NOT done here. Two options, user's call:
  A) Browser signing page: generates the mint keypair in-page, builds the
     tx with the Raydium SDK, user signs the creator part in their wallet,
     page adds the mint signature and broadcasts. No local keypairs.
  B) Scoped local `stonk-launcher` wallet exception (user-approved, like
     clawd-buyer): local keypair signs both parts, per-launch approval.

Metadata policy: every launch pins image + metadata JSON through Pinata/IPFS
and puts ipfs://<CID> on-chain. Never example.com / Irys / ephemeral hosts.
"""
import sys
import os
import json
import time
import subprocess
import urllib.request
import urllib.error

BASE = "https://www.stonkfun.xyz/api/public/v1"
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(SKILL_DIR, "state", "launches")
PINATA = os.path.expanduser("~/workspace/skills/pinata/bin/pinata_pin.py")
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
MAXIMUM_FEE = "1000000000000000"  # per Stonkfun docs: exact key/value the SDK needs


def api_get(path):
    # curl, not urllib: the egress proxy truncates large responses for
    # python's http.client (IncompleteRead), curl handles them fine.
    r = subprocess.run(
        ["curl", "-s", "--max-time", "30", "-H", "User-Agent: stonkfun-skill/1.0",
         "-H", "accept: application/json", "-w", "\n%{http_code}", BASE + path],
        capture_output=True, text=True, timeout=40,
    )
    body, _, code = r.stdout.rpartition("\n")
    if code.strip() != "200":
        raise SystemExit(f"API error HTTP {code.strip()} on {path}: {body[:500]}")
    try:
        return json.loads(body)["data"]
    except Exception as e:
        raise SystemExit(f"API parse failed on {path}: {e}")


PAIRS_CACHE = os.path.join(SKILL_DIR, "state", "pairs_cache.json")
PAIRS_CACHE_TTL = 6 * 3600


def get_pairs():
    """/pairs?launchable=true&launchLabReady=true with retries + disk cache.

    The payload is ~180KB and the egress path truncates it intermittently,
    so retry hard and fall back to a cached copy (< 24h) rather than failing.
    """
    last = None
    for attempt in range(8):
        try:
            data = api_get("/pairs?launchable=true&launchLabReady=true")
            pairs = data.get("pairs", [])
            if pairs:
                os.makedirs(os.path.dirname(PAIRS_CACHE), exist_ok=True)
                with open(PAIRS_CACHE, "w") as f:
                    json.dump({"at": time.time(), "pairs": pairs}, f)
                return pairs, "live"
        except SystemExit as e:
            last = e
        except Exception as e:  # truncated reads etc.
            last = e
        time.sleep(1 + attempt)
    if os.path.exists(PAIRS_CACHE):
        with open(PAIRS_CACHE) as f:
            cached = json.load(f)
        age_h = (time.time() - cached["at"]) / 3600
        if age_h < 24:
            print(f"WARNING: live /pairs fetch failed; using cache ({age_h:.1f}h old).",
                  file=sys.stderr)
            return cached["pairs"], "cache"
    raise SystemExit(f"Could not fetch /pairs and no usable cache: {last}")


def pin_file(path):
    """Pin a local file via the pinata skill; return ipfs:// CID uri."""
    r = subprocess.run(
        [sys.executable, PINATA, "pin-file", "--file", path],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        raise SystemExit(f"Pinata pin-file failed: {r.stderr.strip()[:300]}")
    try:
        out = json.loads(r.stdout)
        cid = out.get("IpfsHash") or out.get("cid") or out.get("data", {}).get("IpfsHash")
    except Exception:
        cid = None
    if not cid:
        raise SystemExit(f"Pinata pin-file returned no CID: {r.stdout[:300]}")
    return f"ipfs://{cid}"


def cmd_plan(args):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--quote-mint", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--tax-bps", type=int, default=0)
    ap.add_argument("--description", default="")
    mg = ap.add_mutually_exclusive_group(required=True)
    mg.add_argument("--metadata-uri")
    mg.add_argument("--metadata-file")
    mg.add_argument("--image")
    ns = ap.parse_args(args)

    if ns.tax_bps not in (0, 100, 300):
        raise SystemExit("tax-bps must be 0 (standard) or an offered tier (100/300)")

    # 1. Pair must be launchable AND LaunchLab-ready.
    pairs, pairs_src = get_pairs()
    pair = next((p for p in pairs if p.get("mint") == ns.quote_mint), None)
    if not pair:
        raise SystemExit(
            f"Quote {ns.quote_mint} is not launchable+LaunchLab-ready right now. "
            "Pick a mint from GET /pairs?launchable=true&launchLabReady=true."
        )

    # 2. Pricing — the numbers that go in the create instruction.
    pricing = api_get(f"/launchlab/pricing?quoteMint={ns.quote_mint}")
    if ns.tax_bps and ns.tax_bps not in pricing["modes"]["reward"]["transferFeeBps"]:
        raise SystemExit(
            f"Tax {ns.tax_bps} bps is not an offered tier "
            f"({pricing['modes']['reward']['transferFeeBps']})."
        )
    mode = "reward" if ns.tax_bps else "standard"

    # 3. Metadata -> ipfs:// per policy.
    if ns.metadata_uri:
        if not ns.metadata_uri.startswith("ipfs://"):
            raise SystemExit("metadata-uri must be ipfs://<CID>[/path] per mint policy")
        metadata_uri = ns.metadata_uri
    elif ns.metadata_file:
        metadata_uri = pin_file(ns.metadata_file)
    else:
        image_uri = pin_file(ns.image)
        meta = {
            "name": ns.name,
            "symbol": ns.symbol,
            "description": ns.description,
            "image": image_uri,
        }
        tmp = f"/tmp/stonk_meta_{int(time.time())}.json"
        with open(tmp, "w") as f:
            json.dump(meta, f)
        metadata_uri = pin_file(tmp)
        os.remove(tmp)

    curve = pricing["curve"]
    platform_id = pricing["platform"][mode]
    curve_rule = pricing["curveRule"][mode]
    transfer_fee = None
    if ns.tax_bps:
        # Exact key names the Raydium SDK declares; anything else is ignored
        # and writes a zero-rate extension (taxes nobody).
        transfer_fee = {
            "transferFeeBasePoints": ns.tax_bps,
            "maxinumFee": MAXIMUM_FEE,
        }

    plan = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mode": mode,
        "tax_bps": ns.tax_bps,
        "token": {"name": ns.name, "symbol": ns.symbol, "metadata_uri": metadata_uri},
        "quote": {
            "mint": ns.quote_mint,
            "symbol": pair.get("symbol"),
            "token_program": pair.get("tokenProgram"),
            # Docs: SDK hardcodes classic SPL in the quote-token-program slot;
            # substitute Token-2022 when the quote is a Token-2022 mint.
            "substitute_token_2022_program": pair.get("tokenProgram") == TOKEN_2022,
        },
        "launchlab": {
            "program_id": curve["programId"],
            "config_id": curve["configId"],
            "platform_id": platform_id,
            # Append LAST, read-only. Ignored until enforcement; then required.
            "curve_rule_account": {"pubkey": curve_rule, "is_signer": False, "is_writable": False},
            "curve_type": "ConstantCurve",
            "migrate_type": curve["migrateType"],
            "base_decimals": curve["baseDecimals"],
            "supply": curve["supply"],
            "total_sell_a": curve["totalSellA"],
            # RAW amount in the quote token's decimals — from pricing, never a constant.
            "total_fund_raising_b": pricing["raise"]["raw"],
            "vesting": {"total_locked": "0", "cliff": "0", "unlock": "0"},
            "cpmm_creator_fee_on": curve["cpmmCreatorFeeOn"],
            "transfer_fee": transfer_fee,
            "derived": curve.get("derived"),
            "raise_note": pricing["raise"].get("basis"),
        },
        "warnings": [
            "Standard launch: confirm adoption in GET /tokens/{mint} (launchpad=launchlab) before building a taxed variant.",
            "A taxed mint that is NOT adopted taxes holders with no distribution — land standard first.",
        ],
    }

    os.makedirs(STATE_DIR, exist_ok=True)
    slug = "".join(c for c in ns.symbol.lower() if c.isalnum()) or "token"
    plan_path = os.path.join(STATE_DIR, f"{slug}-{int(time.time())}.plan.json")
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2)

    derived = curve.get("derived", {})
    print(json.dumps({
        "ok": True,
        "plan": plan_path,
        "mode": mode,
        "token": f"{ns.name} ({ns.symbol})",
        "metadata_uri": metadata_uri,
        "quote": pair.get("symbol"),
        "raise_raw": pricing["raise"]["raw"],
        "raise_units": pricing["raise"]["units"],
        "platform_id": platform_id,
        "curve_rule": curve_rule,
        "next": "NOTHING IS SIGNED OR LAUNCHED. Pick a signing path (browser page or approved stonk-launcher wallet), then build+sign+broadcast the initialize_with_token2022 from this plan, then run: stonk_launch.py check --mint <mint>",
    }, indent=2))
    return 0


def cmd_check(args):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mint", required=True)
    ns = ap.parse_args(args)
    t = api_get(f"/tokens/{ns.mint}")
    adopted = t.get("launchpad") == "launchlab"
    print(json.dumps({
        "mint": ns.mint,
        "adopted": adopted,
        "launchpad": t.get("launchpad"),
        "name": t.get("name"),
        "symbol": t.get("symbol"),
        "market_cap_usd": t.get("marketCapUsd") or t.get("marketCap"),
        "graduation_pct": t.get("graduationProgress") or t.get("graduationPct"),
    }, indent=2))
    if not adopted:
        print("Not adopted yet (or wrong shape) — wait ~2 min and re-check. "
              "If it never adopts, the pool trades on Raydium but the platform records nothing.")
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("plan", "check"):
        print(__doc__.strip())
        return 2
    return {"plan": cmd_plan, "check": cmd_check}[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
