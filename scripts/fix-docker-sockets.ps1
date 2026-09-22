<#
.SYNOPSIS
    Destrava o Docker Desktop quando ele abre e fecha sozinho no Windows.

.DESCRIPTION
    O backend do Docker Desktop abre sockets Unix dentro de %LOCALAPPDATA%.
    Quando o processo morre de forma anormal (crash, desligamento abrupto),
    esses arquivos ficam orfaos: tem 0 byte, atributo ReparsePoint, e nao
    podem ser apagados por Remove-Item, `del /f` nem `fsutil`.

    No boot seguinte o Docker tenta REMOVER o socket antigo antes de recriar,
    falha, e o processo inteiro morre poucos minutos depois de abrir - sem
    mensagem visivel. O sintoma e "o Docker Desktop abre e fecha sozinho".

    Este script contorna renomeando o diretorio que contem o socket travado
    (a operacao age na entrada do diretorio, nao no arquivo) e criando uma
    pasta limpa no lugar. Os diretorios antigos ficam ao lado, com sufixo
    .orfao-<data>, e podem ser apagados depois de um reboot.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\fix-docker-sockets.ps1
#>

[CmdletBinding()]
param(
    # Encerra processos do Docker antes de limpar.
    [switch]$PararDocker,
    # Inicia o Docker Desktop ao final.
    [switch]$IniciarDocker
)

$ErrorActionPreference = "Stop"

$sockets = @(
    "$env:LOCALAPPDATA\Docker\run\dockerInference",
    "$env:LOCALAPPDATA\docker-secrets-engine\engine.sock"
)

if ($PararDocker) {
    Write-Host "Encerrando processos do Docker..."
    Get-Process -Name "*docker*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

$emUso = (Get-Process -Name "*docker*" -ErrorAction SilentlyContinue | Measure-Object).Count
if ($emUso -gt 0) {
    # Abortar, e nao apenas avisar: mexer nos diretorios de socket com o
    # Docker no ar e imprevisivel, e este script existe justamente para o
    # caso em que ele NAO esta rodando.
    Write-Error @"
Ha $emUso processo(s) do Docker em execucao.

Este script so deve rodar com o Docker parado. Use uma das opcoes:
  - feche o Docker Desktop e rode de novo, ou
  - rode com -PararDocker para encerra-lo automaticamente.
"@
    exit 1
}

$carimbo = Get-Date -Format "yyyyMMdd-HHmmss"
$limpou = $false

foreach ($socket in $sockets) {
    if (-not (Test-Path $socket)) {
        Write-Host "ok, ja limpo: $socket"
        continue
    }

    $limpou = $true
    try {
        Remove-Item -LiteralPath $socket -Force -ErrorAction Stop
        Write-Host "apagado: $socket"
        continue
    }
    catch {
        Write-Host "nao deu para apagar (esperado em socket orfao); renomeando o diretorio..."
    }

    $diretorio = Split-Path $socket -Parent
    $novoNome = "$(Split-Path $diretorio -Leaf).orfao-$carimbo"
    try {
        Rename-Item -LiteralPath $diretorio -NewName $novoNome -ErrorAction Stop
        New-Item -ItemType Directory -Force -Path $diretorio | Out-Null
        Write-Host "resolvido: $diretorio (antigo salvo como $novoNome)"
    }
    catch {
        Write-Error "FALHOU em $diretorio : $($_.Exception.Message)"
    }
}

if (-not $limpou) {
    Write-Host ""
    Write-Host "Nenhum socket orfao encontrado. Se o Docker ainda nao sobe, veja o erro real em:"
    Write-Host "  $env:LOCALAPPDATA\Docker\log\host\com.docker.backend.exe.log"
    Write-Host "  (procure por 'backend crashed')"
}

if ($IniciarDocker) {
    Write-Host ""
    Write-Host "Iniciando Docker Desktop..."
    Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    Write-Host "Aguarde o icone ficar verde e rode: docker info"
}
