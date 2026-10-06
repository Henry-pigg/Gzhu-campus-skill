#!/usr/bin/env bash
# gzhu-credential-mac.sh
# macOS Keychain-backed credential store for GZHU portal (数字广大 / 教务系统).
#
# Security model (mirrors the Windows DPAPI script):
#   - Credentials live in the user's macOS Keychain, protected by the macOS
#     login keychain, which is encrypted with the user's login password.
#     Other macOS users on the same Mac, or processes running under another
#     identity, cannot read the plaintext without the user unlocking the
#     keychain (and on first read, macOS may prompt for permission).
#   - Nothing is written into this git repo. The Keychain is per-user,
#     per-mac, and never leaves the machine.
#
# Usage:
#   ./gzhu-credential-mac.sh set <student_id> <password>
#   ./gzhu-credential-mac.sh get
#   ./gzhu-credential-mac.sh remove
#   ./gzhu-credential-mac.sh status
#
# `get` prints one JSON line: {"student_id":"...","password":"...","updated_at":"..."}
# so an AI agent can feed it into browser automation for login.

set -euo pipefail

SERVICE="gzhu-campus"

action="${1:-status}"
student_id="${2:-}"
password="${3:-}"

# Basic JSON string escape (covers backslash and double quote; passwords
# with control chars are extremely rare and rejected by GZHU CAS anyway).
json_escape() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

case "$action" in
  set)
    if [ -z "$student_id" ] || [ -z "$password" ]; then
      echo "usage: $0 set <student_id> <password>" >&2
      exit 1
    fi
    security add-generic-password -U -s "$SERVICE" -a "student-id" -w "$student_id" >/dev/null
    security add-generic-password -U -s "$SERVICE" -a "password"    -w "$password"    >/dev/null
    echo "OK: credentials saved to macOS Keychain (service=$SERVICE)"
    echo "    student_id = $student_id  (password not echoed)"
    ;;

  get)
    if ! sid=$(security find-generic-password -s "$SERVICE" -a "student-id" -w 2>/dev/null); then
      echo '{"error":"no credentials stored"}'
      exit 2
    fi
    pw=$(security find-generic-password -s "$SERVICE" -a "password" -w 2>/dev/null) || {
      echo '{"error":"password item missing; run set again"}'
      exit 3
    }
    updated=$(date +%Y-%m-%dT%H:%M:%S)
    sid_j=$(json_escape "$sid")
    pw_j=$(json_escape  "$pw")
    printf '{"student_id":"%s","password":"%s","updated_at":"%s"}\n' "$sid_j" "$pw_j" "$updated"
    ;;

  remove)
    security delete-generic-password -s "$SERVICE" -a "student-id" >/dev/null 2>&1 || true
    security delete-generic-password -s "$SERVICE" -a "password"    >/dev/null 2>&1 || true
    echo "Removed from macOS Keychain (service=$SERVICE)"
    ;;

  status)
    if security find-generic-password -s "$SERVICE" -a "student-id" >/dev/null 2>&1; then
      echo "STORED in macOS Keychain (service=$SERVICE)"
    else
      echo "NOT STORED"
    fi
    ;;

  *)
    echo "usage: $0 {set <student_id> <password>|get|remove|status}" >&2
    exit 1
    ;;
esac
