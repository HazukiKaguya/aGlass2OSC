# Recover only an idle cezanne USB/IP virtual controller. Never restart USB roots.
param([switch]$Restart)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskLog = Join-Path $taskRoot 'tmp\vhci-recovery.log'
[void](New-Item -ItemType Directory -Path (Split-Path -Parent $taskLog) -Force)
Start-Transcript -Path $taskLog -Append | Out-Null
$taskMutex = $null
try {
    $taskCreated = $false
    $taskMutex = [System.Threading.Mutex]::new($false, 'Local\aGlass2OSC.VirtualUSBKey', [ref]$taskCreated)
    if (-not $taskCreated) { throw 'Virtual Key is running or another recovery is active. Stop it first.' }
    $taskControllers = @(Get-PnpDevice -PresentOnly | Where-Object {
        $_.InstanceId -like 'USBIPWIN\VHCI\*' -and $_.FriendlyName -eq 'usbip-win VHCI'
    })
    if ($taskControllers.Count -ne 1) { throw 'Expected exactly one cezanne VHCI controller; nothing was changed.' }
    $taskController = $taskControllers[0]
    $taskChildren = @((Get-PnpDeviceProperty -InstanceId $taskController.InstanceId -KeyName DEVPKEY_Device_Children).Data | Where-Object { $_ })
    foreach ($taskChild in $taskChildren) {
        $taskDevice = Get-PnpDevice -InstanceId $taskChild
        if ($taskDevice.FriendlyName -ne 'usbip-win VHUB') { throw 'Controller has an unexpected child; nothing was changed.' }
        $taskGrandchildren = @((Get-PnpDeviceProperty -InstanceId $taskChild -KeyName DEVPKEY_Device_Children).Data | Where-Object { $_ })
        if ($taskGrandchildren.Count -gt 0) { throw 'Virtual hub has connected devices; nothing was changed.' }
    }
    Write-Output ('Idle virtual controller: ' + $taskController.InstanceId)
    if ($Restart) {
        $taskAdmin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
        if (-not $taskAdmin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'Restart requires an Administrator PowerShell window. No device was changed.'
        }
        & "$env:SystemRoot\System32\pnputil.exe" /restart-device $taskController.InstanceId
        if ($LASTEXITCODE -eq 3010) {
            Write-Output 'Windows requires a computer restart to complete recovery (3010). Slots may remain occupied until then. This script will not reboot Windows.'
            exit 3010
        }
        if ($LASTEXITCODE -ne 0) { throw ('PnP restart did not complete successfully: ' + $LASTEXITCODE) }
        Write-Output 'Virtual controller restart completed. Use Detect driver in aGlass2OSC to verify its slots.'
    } else {
        Write-Output 'Preflight passed. No device changed. Add -Restart in Administrator PowerShell to recover this controller.'
    }
} catch {
    Write-Output ('Recovery failed: ' + $_.Exception.Message)
    exit 1
} finally {
    if ($taskMutex) { $taskMutex.Dispose() }
    Stop-Transcript | Out-Null
}
