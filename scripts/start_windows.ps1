$ErrorActionPreference = "Stop"

$ContainerName = "finally-app"
$ImageName = "finally"
$DbVolume = "finally-data"

# Parse flags
$Build = $args -contains "--build"

# Check .env exists
if (-not (Test-Path ".env")) {
    Write-Host "Error: .env file not found. Copy .env.example to .env and fill in your API key."
    exit 1
}

# Stop existing container if running
$running = docker ps -q -f "name=$ContainerName" 2>$null
if ($running) {
    Write-Host "Stopping existing container..."
    docker stop $ContainerName | Out-Null
    docker rm $ContainerName | Out-Null
}

# Build image if needed
$imageExists = docker image inspect $ImageName 2>$null
if ($Build -or -not $imageExists) {
    Write-Host "Building Docker image..."
    docker build -t $ImageName .
}

# Run container
Write-Host "Starting FinAlly..."
docker run -d `
    --name $ContainerName `
    -p 8000:8000 `
    -v "${DbVolume}:/app/db" `
    --env-file .env `
    $ImageName

Write-Host ""
Write-Host "FinAlly is running at http://localhost:8000"
Write-Host "Run '.\scripts\stop_windows.ps1' to stop."
