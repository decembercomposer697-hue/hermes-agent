#!/usr/bin/env python3
"""
Crypto Market Monitor — Autonomous Agent Tool
Monitors gas, prices, whale movements across chains. Zero API keys needed.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────

REPORT_DIR = Path(__file__).parent / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# Public RPC endpoints (read-only, no key needed for basic queries)
PUBLIC_RPC = {
    "ethereum": "https://eth.llamarpc.com",
    "bnb": "https://bsc-dataseed.binance.org",
    "base": "https://mainnet.base.org",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
}

PRICE_API = "https://api.coingecko.com/api/v3/simple/price"
WHALE_EXPLORER = "https://etherscan.io/tx"

# Whale alert threshold in USD
WHALE_THRESHOLD_USD = 100_000

# ── JSON-RPC Helpers ───────────────────────────────────────────────────────


def rpc_call(url: str, method: str, params: list) -> dict:
    """Make a JSON-RPC call to a public endpoint."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        return {"error": str(e)}


def eth_gas_price(rpc_url: str) -> dict:
    """Get gas price in gwei and estimated costs."""
    result = rpc_call(rpc_url, "eth_gasPrice", [])
    if "error" in result or "result" not in result:
        return {"error": result.get("error", "no result")}
    wei = int(result["result"], 16)
    gwei = wei / 1e9
    return {
        "gas_price_gwei": round(gwei, 4),
        "gas_price_wei": wei,
        "estimates": {
            "transfer": {"gas": 21000, "cost_eth": round(gwei * 21000 / 1e9, 8)},
            "erc20": {"gas": 65000, "cost_eth": round(gwei * 65000 / 1e9, 8)},
            "swap": {"gas": 150000, "cost_eth": round(gwei * 150000 / 1e9, 8)},
        },
    }


def get_eth_balance(address: str, rpc_url: str = None) -> float:
    """Get ETH balance for an address."""
    rpc_url = rpc_url or PUBLIC_RPC["ethereum"]
    result = rpc_call(rpc_url, "eth_getBalance", [address, "latest"])
    if "result" not in result:
        return 0.0
    return int(result["result"], 16) / 1e18


def latest_block_number(rpc_url: str) -> int:
    """Get latest block number."""
    result = rpc_call(rpc_url, "eth_blockNumber", [])
    if "result" not in result:
        return 0
    return int(result["result"], 16)


# ── Price API ──────────────────────────────────────────────────────────────


def get_prices(coins: list = None) -> dict:
    """Get current prices from CoinGecko (free, no key)."""
    if coins is None:
        coins = ["bitcoin", "ethereum", "solana", "binancecoin", "polygon"]
    ids = ",".join(coins)
    url = f"{PRICE_API}?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError):
        return {}


# ── Trending Tokens ────────────────────────────────────────────────────────


def get_trending() -> list:
    """Get trending searches on CoinGecko (free)."""
    url = "https://api.coingecko.com/api/v3/search/trending"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            return [
                {
                    "name": c["item"]["name"],
                    "symbol": c["item"]["symbol"],
                    "market_cap_rank": c["item"].get("market_cap_rank"),
                    "price_btc": c["item"].get("price_btc"),
                }
                for c in data.get("coins", [])[:5]
            ]
    except (urllib.error.URLError, json.JSONDecodeError):
        return []


# ── Report Generator ───────────────────────────────────────────────────────


def generate_daily_report() -> str:
    """Generate a complete market report."""
    lines = []
    now = datetime.now(timezone.utc)
    lines.append(f"# Crypto Market Report — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    # Gas prices across chains
    lines.append("## Gas Prices")
    for chain, rpc in PUBLIC_RPC.items():
        gas = eth_gas_price(rpc)
        if "error" in gas:
            lines.append(f"- **{chain}**: error ({gas['error']})")
        else:
            lines.append(f"- **{chain}**: {gas['gas_price_gwei']} Gwei "
                         f"(transfer ~${gas['estimates']['transfer']['cost_eth']:.4f})")
    lines.append("")

    # Token prices
    prices = get_prices()
    if prices:
        lines.append("## Token Prices (USD)")
        name_map = {
            "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL",
            "binancecoin": "BNB", "polygon": "MATIC",
        }
        for coin_id, display in name_map.items():
            if coin_id in prices:
                p = prices[coin_id]
                change = p.get("usd_24h_change", 0)
                arrow = "↑" if change and change >= 0 else "↓"
                lines.append(f"- **{display}**: ${p.get('usd', '?'):,.2f} "
                             f"{arrow} {abs(change or 0):.2f}%")
        lines.append("")

    # Trending
    trending = get_trending()
    if trending:
        lines.append("## Trending Now")
        for t in trending:
            rank = f" (#{t['market_cap_rank']})" if t.get("market_cap_rank") else ""
            lines.append(f"- {t['name']} ({t['symbol'].upper()}){rank}")
        lines.append("")

    return "\n".join(lines)


def save_report(report: str) -> Path:
    """Save report to file and return path."""
    fname = f"report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    path = REPORT_DIR / fname
    path.write_text(report)
    return path


# ── CLI ────────────────────────────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Crypto Market Monitor")
    parser.add_argument("--report", choices=["daily", "gas", "prices", "trending"],
                        default="daily", help="Report type")
    parser.add_argument("--save", action="store_true", help="Save report to file")
    args = parser.parse_args()

    if args.report == "gas":
        for chain, rpc in PUBLIC_RPC.items():
            gas = eth_gas_price(rpc)
            if "error" not in gas:
                print(f"{chain}: {gas['gas_price_gwei']} Gwei")
    elif args.report == "prices":
        prices = get_prices()
        for coin, data in prices.items():
            print(f"{coin}: ${data.get('usd', '?'):,.2f}")
    elif args.report == "trending":
        for t in get_trending():
            print(f"{t['name']} ({t['symbol']})")
    else:
        report = generate_daily_report()
        if args.save:
            path = save_report(report)
            print(f"Report saved to {path}")
        print(report)


if __name__ == "__main__":
    main()
