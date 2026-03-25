$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcDir = Join-Path $projectRoot "src"
$buildRoot = Join-Path $projectRoot "build"
$distDir = Join-Path $projectRoot "dist"
$specDir = Join-Path $buildRoot "spec"
$runtimeTmpDir = "C:\Users\Public\Documents\ESTsoft\CreatorTemp\BizTeam_WorkRequestSplitter2"

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
New-Item -ItemType Directory -Force -Path $distDir | Out-Null
New-Item -ItemType Directory -Force -Path $specDir | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeTmpDir | Out-Null

$workRequestLabel = -join ([char[]](0xC791, 0xC5C5, 0xC694, 0xCCAD, 0xC11C))

$targets = @(
    @{
        Script = (Join-Path $srcDir "main.py")
        BuildName = "BizTeam_WorkRequestSplitter2_SN"
        FinalName = "BizTeam_WorkRequestSplitter2_SN.exe"
        WorkPath = (Join-Path $buildRoot "main_sn")
    },
    @{
        Script = (Join-Path $srcDir "main2.py")
        BuildName = "BizTeam_WorkRequestSplitter2_workrequest"
        FinalName = "BizTeam_WorkRequestSplitter2_{0}.exe" -f $workRequestLabel
        WorkPath = (Join-Path $buildRoot "main2_title")
    }
)

foreach ($target in $targets) {
    python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --console `
        --runtime-tmpdir $runtimeTmpDir `
        --paths $srcDir `
        --name $target.BuildName `
        --distpath $distDir `
        --workpath $target.WorkPath `
        --specpath $specDir `
        $target.Script

    $builtExe = Join-Path $distDir ($target.BuildName + ".exe")
    $finalExe = Join-Path $distDir $target.FinalName
    if ($builtExe -ne $finalExe) {
        if (Test-Path -LiteralPath $finalExe) {
            Remove-Item -LiteralPath $finalExe -Force
        }
        Rename-Item -LiteralPath $builtExe -NewName $target.FinalName
    }
}

Write-Host "Built executables:"
Get-ChildItem -LiteralPath $distDir -Filter *.exe | Select-Object FullName, Length, LastWriteTime
