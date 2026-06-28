#!/usr/bin/env bash
set -euo pipefail

SCRIPT_URL="${IPQUALITY_SCRIPT_URL:-https://IP.Check.Place}"
BASH_BIN="${IPQUALITY_BASH:-}"
mode="summary"
family="4"
output_file=""
log_file=""

if [[ -z "$BASH_BIN" ]]; then
  if [[ -x /opt/homebrew/bin/bash ]]; then
    BASH_BIN=/opt/homebrew/bin/bash
  elif [[ -x /usr/local/bin/bash ]]; then
    BASH_BIN=/usr/local/bin/bash
  else
    BASH_BIN=$(command -v bash)
  fi
fi

export PATH="$(dirname "$BASH_BIN"):$PATH"

if ! command -v timeout >/dev/null 2>&1; then
  if command -v gtimeout >/dev/null 2>&1; then
    timeout() { gtimeout "$@"; }
  else
    timeout() {
      local _seconds="$1"
      shift
      "$@"
    }
  fi
  export -f timeout
fi

if ! command -v ss >/dev/null 2>&1; then
  ss() {
    if [[ "$(uname -s)" == "Darwin" ]]; then
      netstat -an -p tcp 2>/dev/null
    else
      return 127
    fi
  }
  export -f ss
fi

flags=(-E -j -p -n)
extra=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      cat <<'USAGE'
Usage: run-ipquality.sh [options] [upstream IPQuality options]

Fast defaults:
  English JSON, privacy mode, no dependency install, IPv4 only, quiet summary.

Options:
  --ipv4              Check IPv4 only (default)
  --ipv6              Check IPv6 only
  --dual-stack        Check IPv4 and IPv6
  --output FILE       Write upstream JSON to FILE
  --log FILE          Write raw upstream output/progress to FILE
  --raw               Stream upstream output directly, no summary
  --ansi              Stream ANSI report instead of JSON
  --allow-deps        Let upstream prompt/install dependencies
  --                  Pass remaining args to upstream

Examples:
  run-ipquality.sh -x http://127.0.0.1:7897
  run-ipquality.sh --ipv6 -x socks5://127.0.0.1:7897
  run-ipquality.sh --dual-stack --raw
USAGE
      exit 0
      ;;
    --ipv4)
      family="4"
      shift
      ;;
    --ipv6)
      family="6"
      shift
      ;;
    --dual-stack)
      family="dual"
      shift
      ;;
    --output)
      output_file="${2:?Missing file for --output}"
      shift 2
      ;;
    --log)
      log_file="${2:?Missing file for --log}"
      shift 2
      ;;
    --raw)
      mode="raw"
      shift
      ;;
    --ansi)
      flags=(-E -p -n)
      mode="raw"
      shift
      ;;
    --allow-deps)
      flags=("${flags[@]/-n/}")
      shift
      ;;
    --)
      shift
      extra+=("$@")
      break
      ;;
    *)
      extra+=("$1")
      shift
      ;;
  esac
done

case "$family" in
  4) flags+=(-4) ;;
  6) flags+=(-6) ;;
  dual) ;;
esac

if [[ "$mode" == "raw" ]]; then
  exec "$BASH_BIN" <(curl -fsSL "$SCRIPT_URL") "${flags[@]}" "${extra[@]}"
fi

if [[ -z "$output_file" ]]; then
  output_file="${TMPDIR:-/tmp}/ipquality-$(date +%Y%m%d%H%M%S)-$$.json"
fi
if [[ -z "$log_file" ]]; then
  log_file="${TMPDIR:-/tmp}/ipquality-$(date +%Y%m%d%H%M%S)-$$.log"
fi

upstream_status=0
"$BASH_BIN" <(curl -fsSL "$SCRIPT_URL") "${flags[@]}" -o "$output_file" "${extra[@]}" >"$log_file" 2>&1 || upstream_status=$?

if ! command -v jq >/dev/null 2>&1; then
  printf 'IPQuality JSON: %s\nRaw log: %s\nUpstream exit: %s\n' "$output_file" "$log_file" "$upstream_status"
  exit "$upstream_status"
fi

if [[ ! -s "$output_file" ]] || ! jq empty "$output_file" >/dev/null 2>&1; then
  printf 'IPQuality did not produce valid JSON.\nRaw log: %s\nUpstream exit: %s\n' "$log_file" "$upstream_status" >&2
  exit "$upstream_status"
fi

jq -r --arg output "$output_file" --arg log "$log_file" '
  def yn: if . == true then "true" elif . == false then "false" elif . == null then "null" else . end;
  [
    "IPQuality summary",
    "IP: \(.Head.IP // "unknown")",
    "ASN/Org: AS\(.Info.ASN // "unknown") \(.Info.Organization // "unknown")",
    "Region: \(.Info.Region.Code // "unknown") / registered \(.Info.RegisteredRegion.Code // "unknown") / \(.Info.Type // "unknown")",
    "Usage: IPinfo=\(.Type.Usage.IPinfo // "null"), ipregistry=\(.Type.Usage.ipregistry // "null"), ipapi=\(.Type.Usage.ipapi // "null")",
    "Score: ipapi=\(.Score.ipapi // "null"), DBIP=\(.Score.DBIP // "null"), Scamalytics=\(.Score.SCAMALYTICS // "null")",
    "Risk: proxy=\(.Factor.Proxy.IPinfo | yn), vpn=\(.Factor.VPN.IPinfo | yn), tor=\(.Factor.Tor.IPinfo | yn), server=\(.Factor.Server.IPinfo | yn)",
    "Media: TikTok=\(.Media.TikTok.Status // "null")/\(.Media.TikTok.Region // ""), Disney+=\(.Media.DisneyPlus.Status // "null")/\(.Media.DisneyPlus.Region // ""), Netflix=\(.Media.Netflix.Status // "null"), YouTube=\(.Media.Youtube.Status // "null")/\(.Media.Youtube.Region // ""), ChatGPT=\(.Media.ChatGPT.Status // "null")/\(.Media.ChatGPT.Region // "")",
    "DNSBL: clean=\(.Mail.DNSBlacklist.Clean // "null"), marked=\(.Mail.DNSBlacklist.Marked // "null"), blacklisted=\(.Mail.DNSBlacklist.Blacklisted // "null"), total=\(.Mail.DNSBlacklist.Total // "null")",
    "JSON: \($output)",
    "Raw log: \($log)"
  ] | .[]
' "$output_file"

if [[ "$upstream_status" -ne 0 ]]; then
  printf 'Upstream exit: %s (JSON was still produced; inspect raw log for dependency/probe errors.)\n' "$upstream_status" >&2
fi
