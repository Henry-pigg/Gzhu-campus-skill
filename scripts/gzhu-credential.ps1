# gzhu-credential.ps1
# DPAPI-encrypted credential store for GZHU portal (数字广大 / 教务系统).
#
# Security model:
#   - Credentials are encrypted with Windows DPAPI (CurrentUser scope).
#     Only THIS Windows user on THIS machine can decrypt the blob.
#     Other Windows users, other machines, or any process running under a
#     different identity cannot read the plaintext password.
#   - The encrypted file lives OUTSIDE the git repository, at
#     %USERPROFILE%\.gzhu-campus\credentials.enc, so it can never be
#     committed or pushed to GitHub.
#   - The plaintext password is never written to disk in cleartext.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File gzhu-credential.ps1 set -StudentId <学号> -Password "<密码>"
#   powershell -NoProfile -ExecutionPolicy Bypass -File gzhu-credential.ps1 get
#   powershell -NoProfile -ExecutionPolicy Bypass -File gzhu-credential.ps1 remove
#   powershell -NoProfile -ExecutionPolicy Bypass -File gzhu-credential.ps1 status
#
# `get` prints a single JSON line: {"student_id":"...","password":"...","updated_at":"..."}
# so that an AI agent can feed it into browser automation for login.

param(
    [Parameter(Position=0)]
    [ValidateSet("set","get","remove","status")]
    [string]$Action = "status",

    [string]$StudentId = "",
    [string]$Password = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Security

$Dir  = Join-Path $env:USERPROFILE ".gzhu-campus"
$File = Join-Path $Dir "credentials.enc"

function Ensure-Dir {
    if (-not (Test-Path $Dir)) {
        New-Item -ItemType Directory -Path $Dir -Force | Out-Null
    }
}

switch ($Action) {

    "set" {
        if ([string]::IsNullOrWhiteSpace($StudentId) -or [string]::IsNullOrWhiteSpace($Password)) {
            Write-Error "set requires -StudentId and -Password."
            exit 1
        }
        $payload = @{
            student_id = $StudentId
            password   = $Password
            updated_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
        } | ConvertTo-Json -Compress
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
        $entropy = [System.Text.Encoding]::UTF8.GetBytes("gzhu-campus-portal-v1")
        $cipher = [System.Security.Cryptography.ProtectedData]::Protect(
            $bytes, $entropy,
            [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
        Ensure-Dir
        [System.IO.File]::WriteAllBytes($File, $cipher)
        # Restrict ACL: only current user + SYSTEM can read.
        $acl = Get-Acl $File
        $acl.SetAccessRuleProtection($true, $false)
        $me = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            $me, "FullControl", "Allow")))
        $acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            "NT AUTHORITY\SYSTEM", "FullControl", "Allow")))
        Set-Acl -Path $File -AclObject $acl
        Write-Output ("OK: credentials saved to " + $File)
        Write-Output ("    student_id = " + $StudentId + "  (password not echoed)")
    }

    "get" {
        if (-not (Test-Path $File)) {
            Write-Error "No credentials stored. Run 'set' first."
            exit 2
        }
        $cipher = [System.IO.File]::ReadAllBytes($File)
        $entropy = [System.Text.Encoding]::UTF8.GetBytes("gzhu-campus-portal-v1")
        try {
            $bytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
                $cipher, $entropy,
                [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
        } catch {
            Write-Error "Failed to decrypt (wrong Windows user or file corrupted)."
            exit 3
        }
        $plain = [System.Text.Encoding]::UTF8.GetString($bytes)
        Write-Output $plain
    }

    "remove" {
        if (Test-Path $File) {
            Remove-Item $File -Force
            Write-Output ("Removed: " + $File)
        } else {
            Write-Output "No credentials file found; nothing to do."
        }
    }

    "status" {
        if (Test-Path $File) {
            $info = Get-Item $File
            Write-Output ("STORED at " + $File)
            Write-Output ("  last modified: " + $info.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
        } else {
            Write-Output "NOT STORED"
        }
    }
}
