# Fix WireGuard firewall for Skylark access.
# Run elevated:  powershell -ExecutionPolicy Bypass -File scripts\fix_wg_firewall.ps1

$ErrorActionPreference = "Stop"

# 1. Re-categorize the WireGuard adapter as Private.
Write-Host "Setting 'tower' adapter to Private profile ..."
Set-NetConnectionProfile -InterfaceAlias "tower" -NetworkCategory Private

# 2. Add firewall rule for port 8765 from the WireGuard subnet.
$ruleName = "QTS-TUI-8765-WG"
$existing = netsh advfirewall firewall show rule name=$ruleName 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removing old rule '$ruleName' ..."
    netsh advfirewall firewall delete rule name=$ruleName | Out-Null
}
Write-Host "Adding firewall rule '$ruleName' (TCP 8765, remote 10.200.200.0/24) ..."
netsh advfirewall firewall add rule `
    name=$ruleName dir=in action=allow protocol=TCP `
    localport=8765 remoteip=10.200.200.0/24

# 3. Remove stale ZeroTier rule.
$ztRule = "QTS-TUI-8765-ZT"
$existing = netsh advfirewall firewall show rule name=$ztRule 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removing stale ZeroTier rule '$ztRule' ..."
    netsh advfirewall firewall delete rule name=$ztRule | Out-Null
}

# 4. Verify.
Write-Host ""
Write-Host "Current network profiles:"
Get-NetConnectionProfile | Format-Table Name, InterfaceAlias, NetworkCategory
Write-Host "Firewall rules for port 8765:"
netsh advfirewall firewall show rule name=all dir=in | Select-String "8765" -Context 1,0

Write-Host ""
Write-Host "Done. Try http://10.200.200.2:8765 from your laptop."
