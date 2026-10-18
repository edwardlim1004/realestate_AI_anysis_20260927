$TaskName="Edward Seoul Apt R2 Sync"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Sync schedule removed. No collected files deleted."
