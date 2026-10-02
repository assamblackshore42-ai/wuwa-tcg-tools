$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $repositoryRoot 'apps/match-manager/assets/battle-icon-transparent.png'
$outputDirectory = Join-Path $repositoryRoot 'apps/match-manager-web/public'
$sourceImage = [System.Drawing.Image]::FromFile($sourcePath)

function Write-AppIcon {
    param(
        [string]$Name,
        [int]$Size,
        [int]$ArtworkSize,
        [bool]$Opaque
    )

    $bitmap = [System.Drawing.Bitmap]::new($Size, $Size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $attributes = [System.Drawing.Imaging.ImageAttributes]::new()
    try {
        $background = if ($Opaque) {
            [System.Drawing.ColorTranslator]::FromHtml('#070b12')
        } else {
            [System.Drawing.Color]::Transparent
        }
        $graphics.Clear($background)
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $attributes.SetWrapMode([System.Drawing.Drawing2D.WrapMode]::TileFlipXY)
        $offset = [int](($Size - $ArtworkSize) / 2)
        $destination = [System.Drawing.Rectangle]::new($offset, $offset, $ArtworkSize, $ArtworkSize)
        $graphics.DrawImage(
            $sourceImage, $destination, 0, 0, $sourceImage.Width, $sourceImage.Height,
            [System.Drawing.GraphicsUnit]::Pixel, $attributes
        )
        $bitmap.Save((Join-Path $outputDirectory $Name), [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $attributes.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

try {
    Write-AppIcon -Name 'pwa-192x192.png' -Size 192 -ArtworkSize 192 -Opaque $false
    Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $outputDirectory 'pwa-512x512.png')
    # A centered 280px square fits inside the maskable safe circle (radius 204.8px).
    Write-AppIcon -Name 'pwa-maskable-512x512.png' -Size 512 -ArtworkSize 280 -Opaque $true
    Write-AppIcon -Name 'apple-touch-icon.png' -Size 180 -ArtworkSize 160 -Opaque $true
} finally {
    $sourceImage.Dispose()
}
