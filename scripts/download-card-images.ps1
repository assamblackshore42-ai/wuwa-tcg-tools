[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..\assets\cards'),
    [ValidateSet('ja-jp', 'zh-cn', 'zh-hk', 'zh-tw', 'ko-kr', 'en-us')]
    [string]$Language = 'ja-jp',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$apiBase = 'https://mc-api.ucp-jp.com/api/web/card/list'
$headers = @{ 'x-lang' = $Language }
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
$null = New-Item -ItemType Directory -Path $resolvedOutput -Force

function Get-SafeFileName {
    param([Parameter(Mandatory)][string]$Name)

    $invalidPattern = '[{0}]' -f [regex]::Escape((-join [System.IO.Path]::GetInvalidFileNameChars()))
    $safeName = [regex]::Replace($Name, $invalidPattern, '_').Trim().TrimEnd('.')
    if ([string]::IsNullOrWhiteSpace($safeName)) {
        return 'unnamed'
    }
    return $safeName
}

Write-Host "公式カード一覧を取得しています: $apiBase"
$cards = [System.Collections.Generic.List[object]]::new()
$page = 1

do {
    $uri = "${apiBase}?page=$page"
    $response = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get
    if ($response.code -ne 1) {
        throw "カード一覧APIがエラーを返しました: $($response.msg)"
    }

    foreach ($card in $response.data.list) {
        $cards.Add($card)
    }

    Write-Host ("  ページ {0}/{1}: 累計 {2}/{3} 件" -f $page, $response.data.last_page, $cards.Count, $response.data.total)
    $hasMore = [bool]$response.data.has_more
    $page++
    if ($hasMore) {
        Start-Sleep -Milliseconds 150
    }
} while ($hasMore)

$downloaded = 0
$skipped = 0
$failed = [System.Collections.Generic.List[object]]::new()
$manifest = [System.Collections.Generic.List[object]]::new()
$usedNames = @{}

foreach ($card in $cards) {
    $extension = [System.IO.Path]::GetExtension(([uri]$card.img).AbsolutePath)
    if ([string]::IsNullOrWhiteSpace($extension)) {
        $extension = '.webp'
    }

    $safeCode = Get-SafeFileName ([string]$card.code)
    $safeName = Get-SafeFileName ([string]$card.name)
    $baseName = "${safeCode}_${safeName}"
    if ($usedNames.ContainsKey($baseName)) {
        $usedNames[$baseName]++
        $baseName = "${baseName}_$($card.id)"
    } else {
        $usedNames[$baseName] = 1
    }

    $fileName = "$baseName$extension"
    $destination = Join-Path $resolvedOutput $fileName
    $status = 'downloaded'

    try {
        if ((Test-Path -LiteralPath $destination) -and -not $Force) {
            $status = 'skipped'
            $skipped++
        } else {
            Invoke-WebRequest -Uri $card.img -OutFile $destination -UseBasicParsing
            $downloaded++
            Start-Sleep -Milliseconds 75
        }

        $fileInfo = Get-Item -LiteralPath $destination
        $manifest.Add([pscustomobject]@{
            id        = $card.id
            code      = $card.code
            name      = $card.name
            type_id   = $card.type_id
            card_type = $card.card_type
            file_name = $fileName
            bytes     = $fileInfo.Length
            image_url = $card.img
            status    = $status
        })
    } catch {
        $failed.Add([pscustomobject]@{
            id        = $card.id
            code      = $card.code
            name      = $card.name
            image_url = $card.img
            error     = $_.Exception.Message
        })
        Write-Warning "取得失敗: $($card.code) $($card.name) - $($_.Exception.Message)"
    }
}

$manifestPath = Join-Path $resolvedOutput 'cards.csv'
$manifest | Export-Csv -LiteralPath $manifestPath -NoTypeInformation -Encoding utf8BOM

$metadataPath = Join-Path $resolvedOutput 'metadata.json'
$metadata = [ordered]@{
    source_page  = 'https://wwcg.ucp-jp.com/jp/card'
    source_api   = $apiBase
    language     = $Language
    retrieved_at = (Get-Date).ToUniversalTime().ToString('o')
    total        = $cards.Count
    downloaded   = $downloaded
    skipped      = $skipped
    failed       = $failed.Count
    cards        = $manifest
    failures     = $failed
}
$metadata | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $metadataPath -Encoding utf8

Write-Host ''
Write-Host "完了: 全 $($cards.Count) 件 / 新規 $downloaded 件 / スキップ $skipped 件 / 失敗 $($failed.Count) 件"
Write-Host "保存先: $resolvedOutput"
Write-Host "索引:   $manifestPath"

if ($failed.Count -gt 0) {
    exit 1
}
