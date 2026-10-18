# Windows PowerShell 5.1+; current user only, least privileges, no wake up, no admin.
$ErrorActionPreference="Stop"
$TaskName="Edward Seoul Apt R2 Sync"
$File=Join-Path $PSScriptRoot "윈도우_R2_동기화.bat"
if (!(Test-Path -LiteralPath $File)) { throw "Sync BAT file not found." }
$Action=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\cmd.exe" -Argument ('/d /c ""{0}""' -f $File) -WorkingDirectory $PSScriptRoot
$Trigger=New-ScheduledTaskTrigger -Daily -At "23:00"
$Settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -DisallowStartIfOnBatteries -StopIfGoingOnBatteries
$Principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null
Write-Host "Task installed: $TaskName; 23:00 local time; only while user logged in and AC connected."
Write-Host "Skipped schedules run at next opportunity; no PC wake; no elevation."
