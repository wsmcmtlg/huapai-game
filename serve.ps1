param(
    [int]$Port = 8765,
    [string]$Bind = "127.0.0.1",
    [string]$OpenUrl = "step5-hu.html"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($root)) { $root = (Get-Location).Path }
Set-Location $root

# --- 端口占用时自动 +1 重试（最多试 30 个端口） ---
$listener = $null
$actualPort = $Port
for ($i = 0; $i -lt 30; $i++) {
    $p = $Port + $i
    $l = New-Object System.Net.HttpListener
    try {
        $l.Prefixes.Add("http://$Bind`:$p/")
        $l.Start()
        $listener = $l
        $actualPort = $p
        break
    } catch {
        try { $l.Close() } catch {}
    }
}
if ($null -eq $listener) {
    Write-Host "ERROR: cannot bind port (all busy or blocked)."
    Read-Host "Press Enter to exit"
    exit 1
}

$mime = @{
    ".html"="text/html; charset=utf-8"; ".htm"="text/html; charset=utf-8";
    ".js"="text/javascript; charset=utf-8"; ".mjs"="text/javascript; charset=utf-8";
    ".css"="text/css; charset=utf-8"; ".json"="application/json; charset=utf-8";
    ".manifest"="application/manifest+json; charset=utf-8";
    ".png"="image/png"; ".jpg"="image/jpeg"; ".jpeg"="image/jpeg"; ".gif"="image/gif";
    ".svg"="image/svg+xml"; ".ico"="image/x-icon"; ".webp"="image/webp";
    ".mp3"="audio/mpeg"; ".wav"="audio/wav"; ".ogg"="audio/ogg"; ".m4a"="audio/mp4";
    ".woff"="font/woff"; ".woff2"="font/woff2"; ".ttf"="font/ttf";
    ".txt"="text/plain; charset=utf-8"; ".md"="text/plain; charset=utf-8";
    ".xml"="application/xml; charset=utf-8"
}

$url = "http://127.0.0.1:$actualPort/$OpenUrl"
Write-Host "================================================="
Write-Host "  Hubei Huapai Game - local static server (PowerShell)"
Write-Host "  URL:      $url"
Write-Host "  Serving:  $root"
Write-Host "  Press Ctrl+C or close this window to stop."
Write-Host "================================================="

# 浏览器在服务器就绪后才打开，避免"连接被拒绝"竞态
try { Start-Process $url } catch {}

$rootFull = [System.IO.Path]::GetFullPath($root)
while ($listener.IsListening) {
    $ctx = $null
    try { $ctx = $listener.GetContext() } catch { break }
    if ($null -eq $ctx) { continue }
    $req = $ctx.Request
    $resp = $ctx.Response
    try {
        $raw = $req.RawUrl
        $pathPart = ($raw -split '\?')[0]
        $pathPart = [System.Uri]::UnescapeDataString($pathPart)
        if ($pathPart -eq '/' -or $pathPart -eq '') { $pathPart = '/step5-hu.html' }
        $rel = $pathPart.TrimStart('/').Replace('/', '\')
        $file = [System.IO.Path]::GetFullPath((Join-Path $root $rel))
        # 目录穿越防护
        if (-not $file.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
            $resp.StatusCode = 403
            $resp.Close()
            continue
        }
        if (Test-Path -LiteralPath $file -PathType Leaf) {
            $ext = [System.IO.Path]::GetExtension($file).ToLower()
            $ct = "application/octet-stream"
            if ($mime.ContainsKey($ext)) { $ct = $mime[$ext] }
            $bytes = [System.IO.File]::ReadAllBytes($file)
            $resp.StatusCode = 200
            $resp.ContentType = $ct
            $resp.ContentLength64 = $bytes.Length
            $resp.OutputStream.Write($bytes, 0, $bytes.Length)
        } else {
            $resp.StatusCode = 404
            $resp.ContentType = "text/plain; charset=utf-8"
            $msg = [System.Text.Encoding]::UTF8.GetBytes("404 Not Found: $pathPart")
            $resp.ContentLength64 = $msg.Length
            $resp.OutputStream.Write($msg, 0, $msg.Length)
        }
    } catch {
        try { $resp.StatusCode = 500; $resp.Close() } catch {}
    } finally {
        try { $resp.OutputStream.Close() } catch {}
        try { $resp.Close() } catch {}
    }
}
