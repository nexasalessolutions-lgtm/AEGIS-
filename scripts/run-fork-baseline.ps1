param(
  [Parameter(Mandatory=$true)][string]$RpcUrl,
  [Parameter(Mandatory=$true)][long]$ForkBlock,
  [Parameter(Mandatory=$true)][string]$Target
)
$ErrorActionPreference = "Stop"
if ($ForkBlock -le 0) { throw "ForkBlock must be a positive block number." }
if ($Target -notmatch '^0x[a-fA-F0-9]{40}$') { throw "Target must be a valid EVM address." }
$env:RPC_URL = $RpcUrl
$env:FORK_BLOCK = "$ForkBlock"
$env:TARGET = $Target
forge test --match-contract ForkBaseline -vv
if ($LASTEXITCODE -ne 0) { throw "Fork baseline failed. Review the Foundry output." }
