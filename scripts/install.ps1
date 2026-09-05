[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('codex', 'claude-code', 'cursor')]
    [string]$Platform,

    [ValidateSet('user', 'project')]
    [string]$Scope = 'user',

    [string]$ProjectPath = (Get-Location).Path,
    [switch]$DryRun,

    [Parameter(DontShow = $true)]
    [ValidateSet('install', 'update')]
    [string]$Mode = 'install'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 重定向输出时 PowerShell 5.1 使用系统代码页编码；固定为 UTF-8，
# 保证中文提示在被 Agent 或 CI 捕获时不乱码。
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# 公共包版本必须使用两段版本（X.X）；validate-package 负责拒绝三段版本。
# references/ 会携带 documentation-contract.md、personal-execution-loop.md、
# level4-capability-routing.md、github-plugin-routing.md；templates/ 会携带
# change-record.md、release-record.md、architecture.md、progress-record.md。

function Resolve-InstallTarget {
    param([string]$SelectedPlatform, [string]$SelectedScope, [string]$SelectedProject)

    if ($SelectedScope -eq 'project') {
        if (-not (Test-Path -LiteralPath $SelectedProject -PathType Container)) {
            throw "错误：项目目录不存在：$SelectedProject"
        }
        $base = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $SelectedProject).Path)
        $relative = switch ($SelectedPlatform) {
            'codex' { '.codex/skills/elx-level' }
            'claude-code' { '.claude/skills/elx-level' }
            'cursor' { '.cursor/skills/elx-level' }
        }
        return [System.IO.Path]::GetFullPath((Join-Path $base $relative))
    }

    $userRoot = [System.IO.Path]::GetFullPath($env:USERPROFILE)
    $resolved = switch ($SelectedPlatform) {
        'codex' {
            $codexRoot = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
                Join-Path $userRoot '.codex'
            } else {
                [System.IO.Path]::GetFullPath($env:CODEX_HOME)
            }
            [System.IO.Path]::GetFullPath((Join-Path $codexRoot 'skills/elx-level'))
        }
        'claude-code' { [System.IO.Path]::GetFullPath((Join-Path $userRoot '.claude/skills/elx-level')) }
        'cursor' { [System.IO.Path]::GetFullPath((Join-Path $userRoot '.cursor/skills/elx-level')) }
    }
    return $resolved
}

function Assert-SafeTarget {
    param([string]$TargetPath)

    $leaf = Split-Path -Leaf $TargetPath
    if ($leaf -ne 'elx-level') {
        throw "错误：拒绝操作非托管目标：$TargetPath"
    }
    $root = [System.IO.Path]::GetPathRoot($TargetPath)
    if ($TargetPath -eq $root -or $TargetPath.Length -le $root.Length + 8) {
        throw "错误：目标路径过宽，已停止：$TargetPath"
    }
}

function Copy-Package {
    param([string]$SourceRoot, [string]$TargetPath)

    $manifest = Get-Content -LiteralPath (Join-Path $SourceRoot 'package-files.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $items = $manifest.items
    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    foreach ($item in $items) {
        $sourceItem = Join-Path $SourceRoot $item
        if (Test-Path -LiteralPath $sourceItem) {
            Copy-Item -LiteralPath $sourceItem -Destination $TargetPath -Recurse -Force
        }
    }
}

$packageRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$versionPath = Join-Path $packageRoot 'VERSION'
if (-not (Test-Path -LiteralPath $versionPath -PathType Leaf)) {
    throw "错误：找不到 VERSION，当前目录不是完整的 elx-level 包。"
}
$version = (Get-Content -LiteralPath $versionPath -Raw -Encoding UTF8).Trim()
$workflow = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'workflow.py'))
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    $pythonCommand = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $pythonCommand -or -not (Test-Path -LiteralPath $workflow -PathType Leaf)) {
    throw "错误：安装前包校验需要 Python 3.10+ 和 scripts/workflow.py。"
}
& $pythonCommand.Source $workflow validate-package --package-root $packageRoot
if ($LASTEXITCODE -ne 0) {
    throw "错误：elx-level 包校验未通过，已停止安装。"
}

$pvsRoot = Join-Path $packageRoot 'core/project-vibe-spec'
$pvsFiles = @(Get-ChildItem -LiteralPath $pvsRoot -Recurse -File)
Write-Host "PVS 内核：$($pvsFiles.Count) 个文件"
$target = Resolve-InstallTarget -SelectedPlatform $Platform -SelectedScope $Scope -SelectedProject $ProjectPath
Assert-SafeTarget -TargetPath $target
$legacyTarget = Join-Path (Split-Path -Parent $target) 'project-level-workflow'
if (Test-Path -LiteralPath $legacyTarget) {
    Write-Host "提示：检测到旧 Skill：$legacyTarget；将保留且不会覆盖。"
}
$independentPvs = Join-Path (Split-Path -Parent $target) 'project-vibe-spec'
if (Test-Path -LiteralPath $independentPvs) {
    Write-Host "提示：检测到独立 project-vibe-spec：$independentPvs；本安装不处理该目录。"
}

$installedVersionPath = Join-Path $target 'VERSION'
if ($Mode -eq 'update' -and -not (Test-Path -LiteralPath $installedVersionPath -PathType Leaf)) {
    throw "错误：目标未安装，不能更新：$target"
}

$backup = $null
if (Test-Path -LiteralPath $target) {
    $installedVersion = if (Test-Path -LiteralPath $installedVersionPath -PathType Leaf) {
        (Get-Content -LiteralPath $installedVersionPath -Raw -Encoding UTF8).Trim()
    } else {
        'unknown'
    }
    if ($Mode -eq 'install' -and $installedVersion -eq $version) {
        & $pythonCommand.Source $workflow validate-package --package-root $target
        if ($LASTEXITCODE -eq 0) {
            Write-Host "elx-level $version 已安装且校验通过：$target"
            exit 0
        }
        Write-Host '同版本安装不完整，将保留原目录并重新安装。'
    }
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = "$target.backup-$timestamp"
    if (Test-Path -LiteralPath $backup) {
        throw "错误：冲突备份已存在，请稍后重试：$backup"
    }
}

Write-Host "模式：$Mode；平台：$Platform；范围：$Scope；版本：$version"
Write-Host "目标：$target"
if ($backup) {
    Write-Host "检测到现有安装或修改，将先创建 conflict backup：$backup"
}
if ($DryRun) {
    Write-Host 'DryRun：仅显示计划，不写入文件。'
    exit 0
}

$parent = Split-Path -Parent $target
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$staging = "$target.installing-$PID"
if (Test-Path -LiteralPath $staging) {
    throw "错误：安装暂存目录已存在：$staging"
}

try {
    Copy-Package -SourceRoot $packageRoot -TargetPath $staging
    & $pythonCommand.Source $workflow validate-package --package-root $staging
    if ($LASTEXITCODE -ne 0) { throw '错误：安装暂存包校验失败，未替换原安装。' }
    if ($backup) {
        Move-Item -LiteralPath $target -Destination $backup
    }
    Move-Item -LiteralPath $staging -Destination $target
} catch {
    if ((Test-Path -LiteralPath $staging) -and (Split-Path -Leaf $staging) -eq "elx-level.installing-$PID") {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    if ((-not (Test-Path -LiteralPath $target)) -and $backup -and (Test-Path -LiteralPath $backup)) {
        Move-Item -LiteralPath $backup -Destination $target
    }
    throw
}

Write-Host "完成：elx-level $version 已安装到 $target"
if ($backup) {
    Write-Host "原版本已保留在：$backup"
}
