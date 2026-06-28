---
name: ipquality-check
description: Use this skill to run, configure, and interpret xykt/IPQuality IP quality checks for server, VPS, proxy, VPN, residential/ISP, streaming unlock, ChatGPT access, mail-port, DNSBL, blacklist, fraud-risk, or IP reputation questions. Use it when the user asks whether an IP is clean, native, hosting/datacenter, risky, proxy/VPN/Tor, blacklisted, or usable for media/AI services.
---

# IPQuality Check

## Overview

This skill wraps the upstream `xykt/IPQuality` shell workflow and provides a concise interpretation path for IP quality, risk, unlock, and blacklist reports. It does not vendor the upstream script; run from the official project endpoint or Docker image unless the user provides a local copy.

Primary upstream project: `https://github.com/xykt/IPQuality`

## When To Use

Use this skill for:

- Checking the current machine, a VPS, a proxy route, or a specified outbound IP.
- Interpreting fields from IPQuality JSON or terminal reports.
- Comparing evidence across risk databases: IPinfo, ipregistry, ipapi, AbuseIPDB, IP2Location, IPQS, DB-IP, Scamalytics, DNSBLs.
- Explaining media/AI access results: TikTok, Disney+, Netflix, YouTube, Prime Video, Reddit, ChatGPT.
- Answering whether an IP looks like native ISP/residential, hosting/datacenter, proxy, VPN, Tor, robot, abuser, or blacklisted.

## Run Workflow

Before running a remote script, state that the command downloads and executes upstream code from `https://IP.Check.Place`. If the user only asked whether this can be a skill, explain the approach without executing it.

Default to the fast path: IPv4 only, English JSON, privacy mode, no dependency installation, quiet summary, and raw logs in a temp file.

```bash
./scripts/run-ipquality.sh
```

Common options:

- IPv4 only: `./scripts/run-ipquality.sh --ipv4`
- IPv6 only: `./scripts/run-ipquality.sh --ipv6`
- Full dual-stack check: `./scripts/run-ipquality.sh --dual-stack`
- Specific interface or outbound IP: `./scripts/run-ipquality.sh -i eth0`
- Through proxy: `./scripts/run-ipquality.sh -x http://127.0.0.1:7897`
- Full visible IP in report: `./scripts/run-ipquality.sh -f`
- Write JSON to a stable file: `./scripts/run-ipquality.sh --output /tmp/ipquality.json`
- Stream upstream output directly: `./scripts/run-ipquality.sh --raw`
- ANSI report instead of JSON: `./scripts/run-ipquality.sh --ansi`
- Let upstream prompt/install dependencies: pass `--allow-deps`

If Docker is better for the target host, use:

```bash
docker run --rm --net=host -it xykt/ipquality -Ejp
```

On macOS, upstream requires Bash 4+. The wrapper prefers Homebrew Bash and adjusts `PATH` so upstream sees the selected Bash. The wrapper also provides lightweight `ss` and `timeout` shims for macOS so upstream can finish cleanly. Treat mail connectivity results as lower-confidence unless GNU coreutils/iproute2-equivalent tools are installed or Docker/Linux is used.

## Speed And Blocking

For quick conclusions, run IPv4 only first. Dual-stack doubles the work and may produce separate, conflicting media/AI results.

Avoid relying on terminal output because upstream prints sponsor blocks and progress animation. Prefer the wrapper summary and the generated JSON file. Use the raw log only when debugging.

If a proxy port is requested, first confirm the route cheaply:

```bash
curl -sS -x http://127.0.0.1:7897 https://api.ipify.org
```

If the proxy and default route return the same IP, say so; the result may reflect system-wide proxying rather than only the explicit port.

If the run appears slow, wait for the `Raw log:` path and inspect the generated JSON. Do not rerun full dual-stack unless IPv6-specific behavior matters.

## Interpretation

Summarize results as evidence, not as a single absolute verdict. Use these priorities:

1. Basic identity: ASN, organization, actual/registered region, geo-consistency.
2. IP type: ISP/residential vs hosting/datacenter/CDN/mobile/business.
3. Risk scores: note high or conflicting provider scores by provider name.
4. Risk factors: proxy, VPN, Tor, server, abuser, robot signals.
5. Media/AI: service status, region, and native/DNS/web/app-only type.
6. Mail: port 25, mail provider connectivity, DNSBL clean/marked/blacklisted counts.

Fast verdict heuristics:

- `Hosting` from multiple usage providers plus `Server=true` means not residential/native, even if proxy/VPN/Tor are false.
- Low scores plus no blacklisted DNSBL entries means low abuse risk, but not necessarily good account/media quality.
- `Geo-discrepant` weakens native-region confidence.
- `ViaDNS` media unlock is weaker than `Native`.
- On macOS without `ss`/`timeout`, do not emphasize mail provider results.
- With the macOS shimmed `timeout`, slow mail probes are not forcibly killed; prefer Docker/Linux if mail-port accuracy or strict runtime bounds matter.

Recommended response shape:

- Verdict: one sentence with confidence.
- Key evidence: 3-6 bullets with provider names and important values.
- Caveats: mention if checked from the wrong network path, behind a proxy, IPv4/IPv6 mismatch, missing dependencies, or provider conflicts.
- Next step: only if it materially changes the answer, such as rerun with `-4`, `-6`, `-x`, or `-i`.
