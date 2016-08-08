$env:PSModulePath = $env:PSModulePath + ";C:\Program Files (x86)\VMware\Infrastructure\vSphere PowerCLI\Modules"

# Load Windows PowerShell cmdlets for managing vSphere
Add-PsSnapin VMware.VimAutomation.Core -ea "SilentlyContinue"

$scriptdir = "C:\Users\Administrator\Documents"
#
# Sourcing Master configuration - these should come from a config file
#-----------------------------------------------------
. "$scriptdir\config.ps1"

#Retrieve Password
$VSphereCredential=New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $VSphereUser, (Get-Content $VSphereCredentialFile | ConvertTo-SecureString)
$visession = Connect-VIserver $vchost -Credential $VSphereCredential

$action = $args[0]
$instanceVmName=$args[1]

$vms = @(get-VM -Name $instanceVmName | Select -ExpandProperty Name)


foreach ($vm in $vms) {
    
    if ($action -ieq 'snapshot') {
        $snap_name = $vm + '_Snapshot'
        $desc = "This snapshot is created right after the OS installation"
        Try
        {
            if (-not (get-snapshot -vm $vm -name $snap_name)) 
            {
                New-Snapshot -VM $vm -Name $snap_name -Description $desc -confirm:$false -Quiesce -Memory -RunAsync
            } 
            Else 
            {
                Write-Host("Snapshot exists. Skipping...")
            }
        }
        Catch
        {
            $ErrorMessage = $_.Exception.Message
            Write-Host($ErrorMessage)
        }
    } Elseif ($action -ieq 'remove') {
        Try
        {
            Write-Host("Removing VM : ", $vm)
            $active = Get-VM $vm
            if($active.PowerState -eq "PoweredOn"){
                Stop-VM -VM $vm -Confirm:$false
                Start-Sleep -Seconds 10
            }
            Remove-VM $vm -DeletePermanently -confirm:$false
        }
        Catch
        {
            $ErrorMessage = $_.Exception.Message
            Write-Host($ErrorMessage)
        }
    }
}

Disconnect-VIServer -Server $visession -confirm:$false


