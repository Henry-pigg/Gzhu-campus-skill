#!/usr/bin/env bash
# gzhu-credential-linux.sh
# Linux Secret Service (GNOME Keyring / KWallet) backed credential store
# for GZHU portal (数字广大 / 教务系统).
#
# Requirements:
#   - `secret-tool` command (package: libsecret-tools on Debian/Ubuntu,
#     libsecret on Fedora/RHEL, libsecret on Arch).
#   - An unlocked keyring, normally auto-unlocked at desktop login.
#     On headless servers without a keyring daemon this script will fail;
#     that's intentional — do NOT fall back to plaintext files.
#
# Security model (mirrors Windows DPAPI / macOS Keychain):
#   - Credentials live in the user's login keyring, encrypted at rest by
#     the desktop keyring daemon and unlocked only after the user logs in.
#   - Nothing is written into this git repo. Each user stores their own
#     credentials on their own machine.
#
# Usage:
#   ./gzhu-credential-linux.sh set <student_id> <password>
#   ./gzhu-credential-linux.sh get
#   ./gzhu-credential-linux.sh remove
#   ./gzhu-credential-linux.sh status
#
# `get` prints one JSON line: {"student_id":"...","password":"...","updated_at":"..."}

set -euo pipefail

SERVICE="gzhu-campus"

if ! command -v secret-tool >/dev/null 2>&1; then
  echo "error: secret-tool not found. Install libsecret-tools (Debian/Ubuntu) / libsecret (Fedora/Arch)," >&2
  echo "       and make sure your login keyring is unlocked (desktop session)." >&2
  exit 127
fi

action="${1:-status}"
student_id="${2:-}"
password="${3:-}"

json_escape() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

case "$action" in
  set)
    if [ -z "$student_id" ] || [ -z "$password" ]; then
      echo "usage: $0 set <student_id> <password>" >&2
      exit 1
    fi
    printf '%s' "$student_id" | secret-tool store --label="GZHU Campus student-id" service "$SERVICE" account "student-id"
    printf '%s' "$password"    | secret-tool store --label="GZHU Campus password"    service "$SERVICE" account "password"
    echo "OK: credentials saved to Secret Service (service=$SERVICE)"
    echo "    student_id = $student_id  (password not echoed)"
    ;;

  get)
    if ! sid=$(secret-tool lookup service "$SERVICE" account "student-id" 2>/dev/null); then
      echo '{"error":"no credentials stored"}'
      exit 2
    fi
    pw=$(secret-tool lookup service "$SERVICE" account "password" 2>/dev/null) || {
      echo '{"error":"password item missing; run set again"}'
      exit 3
    }
    updated=$(date +%Y-%m-%dT%H:%M:%S)
    sid_j=$(json_escape "$sid")
    pw_j=$(json_escape  "$pw")
    printf '{"student_id":"%s","password":"%s","updated_at":"%s"}\n' "$sid_j" "$pw_j" "$updated"
    ;;

  remove)
    secret-tool clear service "$SERVICE" account "student-id" >/dev/null 2>&1 || true
    secret-tool clear service "$SERVICE" account "password"    >/dev/null 2>&1 || true
    echo "Removed from Secret Service (service=$SERVICE)"
    ;;

  status)
    if secret-tool lookup service "$SERVICE" account "student-id" >/dev/null 2>&1; then
      echo "STORED in Secret Service (service=$SERVICE)"
    else
      echo "NOT STORED"
    fi
    ;;

  *)
    echo "usage: $0 {set <student_id> <password>|get|remove|status}" >&2
    exit 1
    ;;
esac
