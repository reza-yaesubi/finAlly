$ErrorActionPreference = "Stop"

$ContainerName = "finally-app"

$running = docker ps -q -f "name=$ContainerName" 2>$null
if ($running) {
    Write-Host "Stopping FinAlly..."
    docker stop $ContainerName | Out-Null
    docker rm $ContainerName | Out-Null
    Write-Host "Stopped."
} else {
    Write-Host "FinAlly is not running."
}
