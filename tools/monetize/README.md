# Crypto Market Monitor — Autonomous Agent Tool

A self-contained Python script that monitors cryptocurrency markets across
multiple chains, detects whale movements, tracks gas prices, and generates
daily reports. Zero external API keys required.

## Features
- **Multi-chain gas tracker**: ETH, BNB, Base, Arbitrum, Polygon, Optimism
- **Whale alert**: Detect large transfers on EVM chains
- **Price alerts**: Track BTC/ETH/SOL and top tokens via public APIs
- **Daily summary**: Generate markdown report of market conditions
- **No API keys**: Uses only public RPC endpoints and free APIs

## Quick Start
```bash
python3 market_monitor.py --report daily
```

## Output
```
=== Market Report 2026-06-16 ===
ETH gas: 0.08 Gwei ($0.003/tx)
BTC: $67,842  ETH: $1,823  SOL: $75.28
Whale: 5,432 ETH moved to unknown wallet (0x...)
```
