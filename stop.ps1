$targets = Get-CimInstance Win32_Process | Where-Object {

    $_.Name -eq 'python.exe' -and

    $_.CommandLine -match 'wfxl_openai_regst\.py' -and

    $_.CommandLine -match '\\.venv\\Scripts\\python\.exe'

}



if (-not $targets) {

    Write-Host 'No running project process found.'

    exit 0

}



$targets | ForEach-Object {

    Stop-Process -Id $_.ProcessId -Force

    Write-Host ("Stopped PID=" + $_.ProcessId)

}

