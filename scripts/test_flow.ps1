#requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$PSDefaultParameterValues['Set-Content:Encoding'] = 'utf8'

function U([int]$codepoint) { [char]$codepoint }
$Ate = "at" + (U 0x00E9)
$ExpiresText = $Ate + " 22h"
$Doacao   = "doa" + (U 0x00E7) + (U 0x00E3) + "o"
$Doacoes  = "doa" + (U 0x00E7) + (U 0x00F5) + "es"

# Configuracao inicial (sem param)
$BaseUrl = if ($env:BASE_URL) { $env:BASE_URL } else { "http://127.0.0.1:8000" }
$Phone = "5511999999999"
$PhoneAlt = "5511999999998"

function HttpGet($url) {
  return Invoke-RestMethod -Method Get -Uri $url -Headers @{ "Accept" = "application/json" }
}

function HttpPostJsonUtf8($url, $obj) {
  $json  = $obj | ConvertTo-Json -Depth 20 -Compress
  $utf8  = New-Object System.Text.UTF8Encoding($false)
  $bytes = $utf8.GetBytes($json)
  return Invoke-RestMethod -Method Post -Uri $url -Body $bytes -ContentType "application/json; charset=utf-8" -Headers @{ "Accept" = "application/json" }
}

function Send-Message([string]$Text) {
  HttpPostJsonUtf8 "$BaseUrl/webhook/whatsapp" @{
    object = "whatsapp_business_account"
    entry  = @(
      @{
        id = "test"
        changes = @(
          @{
            value = @{
              messaging_product = "whatsapp"
              metadata = @{ display_phone_number = "5511999999999"; phone_number_id = "test" }
              messages = @(
                @{
                  from = $Phone
                  id   = "wamid.test.$([Guid]::NewGuid().ToString('N'))"
                  timestamp = [string][int][double]::Parse((Get-Date -UFormat %s))
                  text = @{ body = $Text }
                  type = "text"
                }
              )
            }
            field = "messages"
          }
        )
      }
    )
  } | Out-Null
}

function RunFlow($messages, $label, $expectDonateStart) {
  Write-Host (">> Iniciando fluxo (" + $label + ")")
  $i = 1
  foreach ($m in $messages) {
    Send-Message $m
    $state = HttpGet "$BaseUrl/admin/conversation-state/$Phone"
    $stateJson = $state | ConvertTo-Json -Depth 20
    Write-Host ("State after msg-{0}: {1}" -f $i, $stateJson)
    if ($expectDonateStart -and $i -eq 1) {
      $stateName = if ($state) { $state.state } else { "<null>" }
      if ($stateName -eq "DONATE_FOOD_TYPE") {
        Write-Host "State msg-1 OK: DONATE_FOOD_TYPE"
      } else {
        Write-Host ("ALERTA: state apos msg-1 nao eh DONATE_FOOD_TYPE: " + $stateName)
      }
    }
    $i++
  }
}

# Fluxo padrao iniciando por "1"
$messages = @("1", "marmitas", "10", $ExpiresText, "Rocinha", "sim")
RunFlow -messages $messages -label "opcao-1" -expectDonateStart $false

# Fluxo alternativo iniciando por "doar" (intencao)
$Phone = $PhoneAlt
$messagesAlt = @("doar", "marmitas", "10", $ExpiresText, "Rocinha", "sim")
RunFlow -messages $messagesAlt -label "intencao-doar" -expectDonateStart $true

# Restaura phone padrao para consultas finais
$Phone = "5511999999999"

Write-Host (">> Consultando " + $Doacoes + " e matches")
$donations = HttpGet "$BaseUrl/admin/donations"
$matches   = HttpGet "$BaseUrl/admin/matches"

if ($donations) {
  Write-Host ("Donations count: {0}" -f $donations.Count)
  ($donations | Select-Object -First 5) | ConvertTo-Json -Depth 20 | Write-Host
} else {
  Write-Host "Donations: null"
}

if ($matches) {
  Write-Host ("Matches count: {0}" -f $matches.Count)
  ($matches | Select-Object -First 5) | ConvertTo-Json -Depth 20 | Write-Host
} else {
  Write-Host "Matches: null"
}

Write-Host (">> Ultima " + $Doacao + " cadastrada (para inspecionar campos)")
if ($donations) {
  $latest = $donations | Sort-Object id -Descending | Select-Object -First 1
  if ($latest) {
    $latest | ConvertTo-Json -Depth 20 | Write-Host
  } else {
    Write-Host ("Nenhuma " + $Doacao + " encontrada.")
  }
} else {
  Write-Host ("Nenhuma " + $Doacao + " encontrada.")
}

