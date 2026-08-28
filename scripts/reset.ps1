$ErrorActionPreference='Stop'
$data=Join-Path $PSScriptRoot '..\backend\data'
if(Test-Path $data){Remove-Item -LiteralPath $data -Recurse -Force}
New-Item -ItemType Directory -Force -Path (Join-Path $data 'uploads'),(Join-Path $data 'vector_store')|Out-Null
Write-Host 'Local data reset.'
