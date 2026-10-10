$ErrorActionPreference = 'Stop'
$root  = Split-Path $PSScriptRoot -Parent
$tools = Join-Path $root 'tools'
New-Item -ItemType Directory -Force (Join-Path $tools 'llama'), (Join-Path $tools 'models') | Out-Null

function Get-File([string]$url, [string]$dest) {
    if (Test-Path $dest) { Write-Host "ja existe: $dest"; return }
    curl.exe -L --fail -o "$dest.part" $url
    if ($LASTEXITCODE -ne 0) { throw "download falhou ($LASTEXITCODE): $url" }
    Move-Item "$dest.part" $dest
}

# llama.cpp com Vulkan (ultima release)
if (-not (Test-Path (Join-Path $tools 'llama\llama-server.exe'))) {
    # /releases/latest pode apontar para outra serie de tags (ex.: v0.6.0): olhar as releases recentes.
    $rels  = Invoke-RestMethod 'https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10'
    $asset = $rels | ForEach-Object { $_.assets } | Where-Object { $_.name -like 'llama-*-bin-win-vulkan-x64.zip' } | Select-Object -First 1
    if (-not $asset) { throw 'a release mais recente do llama.cpp nao tem binario Vulkan x64' }
    $zip = Join-Path $env:TEMP $asset.name
    Get-File $asset.browser_download_url $zip
    Expand-Archive -Force $zip (Join-Path $tools 'llama')
    $nested = Get-ChildItem (Join-Path $tools 'llama') -Recurse -Filter 'llama-server.exe' | Select-Object -First 1
    if (-not $nested) { throw 'llama-server.exe nao veio no zip' }
    if ($nested.DirectoryName -ne (Join-Path $tools 'llama')) {
        Get-ChildItem $nested.DirectoryName | Move-Item -Destination (Join-Path $tools 'llama') -Force
    }
}

# Modelos
Get-File 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q8_0.bin' (Join-Path $tools 'models\ggml-large-v3-turbo-q8_0.bin')
Get-File 'https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf' (Join-Path $tools 'models\Qwen2.5-7B-Instruct-Q4_K_M.gguf')
Write-Host '[OK] ferramentas em' $tools
