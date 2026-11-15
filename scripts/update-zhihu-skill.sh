#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$script_dir/.." && pwd)
target_dir="$repo_root/zhihu"
lock_file="$repo_root/zhihu-skill.lock.json"
manifest_url='https://developer-cdn.zhihu.com/zhihu-cli/releases/stable/manifest.json'

usage() {
  printf '%s\n' \
    '用法：' \
    '  ./scripts/update-zhihu-skill.sh          下载并更新知乎 Skill' \
    '  ./scripts/update-zhihu-skill.sh --check  检查官方是否有新版本' \
    '  ./scripts/update-zhihu-skill.sh --help   显示帮助'
}

if [ "$#" -gt 1 ]; then
  usage >&2
  exit 2
fi

mode='update'
case "${1:-}" in
  '') ;;
  --check) mode='check' ;;
  --help|-h) usage; exit 0 ;;
  --update) mode='update' ;;
  *) usage >&2; exit 2 ;;
esac

for command_name in curl python3 shasum unzip; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf '缺少依赖：%s\n' "$command_name" >&2
    exit 1
  fi
done

if [ "$mode" = 'update' ] && ! command -v git >/dev/null 2>&1; then
  printf '更新模式需要 git，用于检查 zhihu/ 是否有未提交改动。\n' >&2
  exit 1
fi

read_manifest_metadata() {
  python3 - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as manifest_file:
    skill = json.load(manifest_file)["skill"]

print("\t".join([
    skill["latest_version"],
    skill["url"],
    skill["sha256"],
    str(skill["size"]),
]))
PY
}

read_lock_metadata() {
  python3 - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as lock_file:
    lock = json.load(lock_file)

print("\t".join([lock["version"], lock["sha256"]]))
PY
}

tmp_dir=$(mktemp -d)
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

curl -sS -L --fail --retry 2 -o "$tmp_dir/manifest.json" "$manifest_url"
metadata=$(read_manifest_metadata "$tmp_dir/manifest.json")
IFS=$'\t' read -r latest_version skill_url expected_sha expected_size <<< "$metadata"

if [ "$mode" = 'check' ]; then
  if [ ! -f "$lock_file" ]; then
    printf '未找到锁文件，官方最新版本为 %s。\n' "$latest_version"
    exit 1
  fi

  lock_metadata=$(read_lock_metadata "$lock_file")
  IFS=$'\t' read -r local_version local_sha <<< "$lock_metadata"
  if [ "$local_version" = "$latest_version" ] && [ "$local_sha" = "$expected_sha" ]; then
    printf '知乎 Skill 已是最新版本：%s。\n' "$local_version"
  else
    printf '发现更新：%s -> %s。\n' "$local_version" "$latest_version"
    printf '执行 ./scripts/update-zhihu-skill.sh 应用更新。\n'
  fi
  exit 0
fi

if [ -d "$target_dir" ]; then
  changed_files=$(git -C "$repo_root" status --short -- zhihu zhihu-skill.lock.json)
  if [ -n "$changed_files" ]; then
    printf 'zhihu/ 或 zhihu-skill.lock.json 存在未提交改动，已停止更新：\n%s\n' "$changed_files" >&2
    exit 1
  fi
fi

if [ -d "$target_dir" ] && [ -f "$lock_file" ]; then
  lock_metadata=$(read_lock_metadata "$lock_file")
  IFS=$'\t' read -r local_version local_sha <<< "$lock_metadata"
  if [ "$local_version" = "$latest_version" ] && [ "$local_sha" = "$expected_sha" ]; then
    printf '知乎 Skill 已是最新版本：%s。\n' "$local_version"
    exit 0
  fi
fi

archive_file="$tmp_dir/zhihu-cli-skill.zip"
unpack_dir="$tmp_dir/unpacked"
curl -sS -L --fail --retry 2 -o "$archive_file" "$skill_url"

actual_size=$(wc -c < "$archive_file" | tr -d '[:space:]')
if [ "$actual_size" != "$expected_size" ]; then
  printf '文件大小校验失败：期望 %s，实际 %s。\n' "$expected_size" "$actual_size" >&2
  exit 1
fi

printf '%s  %s\n' "$expected_sha" "$archive_file" | shasum -a 256 -c -
unzip -q "$archive_file" -d "$unpack_dir"

new_skill_dir="$unpack_dir/zhihu"
if [ ! -f "$new_skill_dir/SKILL.md" ] || [ ! -f "$new_skill_dir/manifest.json" ]; then
  printf '压缩包结构校验失败：缺少 zhihu/SKILL.md 或 zhihu/manifest.json。\n' >&2
  exit 1
fi

package_version=$(python3 - "$new_skill_dir/manifest.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as manifest_file:
    print(json.load(manifest_file)["version"])
PY
)
if [ "$package_version" != "$latest_version" ]; then
  printf '包内版本校验失败：manifest 为 %s，远端 manifest 为 %s。\n' "$package_version" "$latest_version" >&2
  exit 1
fi

lock_tmp="$tmp_dir/zhihu-skill.lock.json"
printf '%s\n' \
  '{' \
  "  \"package\": \"zhihu-cli-skill\"," \
  "  \"version\": \"$latest_version\"," \
  "  \"url\": \"$skill_url\"," \
  "  \"sha256\": \"$expected_sha\"," \
  "  \"size\": $expected_size," \
  "  \"manifest_url\": \"$manifest_url\"" \
  '}' > "$lock_tmp"

target_backup="$tmp_dir/zhihu.previous"
lock_backup="$tmp_dir/zhihu-skill.lock.previous"
target_moved=0
target_installed=0
lock_moved=0
lock_installed=0

rollback() {
  exit_code=$?
  if [ "$exit_code" -ne 0 ]; then
    if [ "$target_installed" -eq 1 ]; then
      rm -rf "$target_dir"
    fi
    if [ "$target_moved" -eq 1 ] && [ -e "$target_backup" ]; then
      mv "$target_backup" "$target_dir"
    fi
    if [ "$lock_installed" -eq 1 ]; then
      rm -f "$lock_file"
    fi
    if [ "$lock_moved" -eq 1 ] && [ -e "$lock_backup" ]; then
      mv "$lock_backup" "$lock_file"
    fi
  fi
  rm -rf "$tmp_dir"
  trap - EXIT
  exit "$exit_code"
}
trap rollback EXIT

if [ -e "$target_dir" ]; then
  mv "$target_dir" "$target_backup"
  target_moved=1
fi
mv "$new_skill_dir" "$target_dir"
target_installed=1

if [ -e "$lock_file" ]; then
  mv "$lock_file" "$lock_backup"
  lock_moved=1
fi
mv "$lock_tmp" "$lock_file"
lock_installed=1

printf '知乎 Skill 已更新至 %s。\n' "$latest_version"
