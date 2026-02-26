#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Creates and configures a Hyper-V VM for running the D2R Pindlebot.
    Keeps the host mouse free by isolating the bot in its own Windows session.

.DESCRIPTION
    Run this script in an elevated PowerShell on the host.
    It will:
      1. Enable Hyper-V features (if not already enabled)
      2. Create a Generation 2 VM with 8GB RAM, 4 vCPUs, 100GB disk
      3. Configure GPU-PV (GPU Paravirtualization) for NVIDIA
      4. Copy host GPU driver files into the VM's virtual disk

.PARAMETER VMName
    Name of the VM to create. Default: "D2R-Bot"

.PARAMETER ISOPath
    Path to a Windows 11 ISO file. Required for initial creation.

.PARAMETER VHDXPath
    Path for the VM's virtual hard disk. Default: auto-generated in Hyper-V default path.

.PARAMETER RAM
    Memory in bytes. Default: 8GB.

.PARAMETER CPUs
    Number of virtual processors. Default: 4.

.PARAMETER DiskSizeGB
    Virtual hard disk size in GB. Default: 100.

.PARAMETER SkipHyperVEnable
    Skip the Hyper-V feature enablement step.

.PARAMETER SkipVMCreation
    Skip VM creation (only configure GPU-PV on existing VM).

.PARAMETER SkipGPUPV
    Skip GPU-PV configuration.

.PARAMETER CopyDrivers
    Copy host NVIDIA driver files into the VM's mounted VHDX.

.EXAMPLE
    # Full setup with ISO
    .\setup_hyperv_vm.ps1 -ISOPath "C:\Users\craig\Downloads\Win11.iso"

    # Just add GPU-PV to existing VM
    .\setup_hyperv_vm.ps1 -SkipHyperVEnable -SkipVMCreation

    # Copy drivers after Windows is installed in the VM
    .\setup_hyperv_vm.ps1 -SkipHyperVEnable -SkipVMCreation -SkipGPUPV -CopyDrivers
#>

param(
    [string]$VMName = "Valbot D2R",
    [string]$ISOPath = "",
    [string]$VHDXPath = "",
    [long]$RAM = 8GB,
    [int]$CPUs = 8,
    [int]$DiskSizeGB = 100,
    [switch]$SkipHyperVEnable,
    [switch]$SkipVMCreation,
    [switch]$SkipGPUPV,
    [switch]$CopyDrivers
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Write-Info {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor Gray
}

function Write-OK {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [WARN] $Message" -ForegroundColor Yellow
}

# -- Step 1: Enable Hyper-V --------------------------------------------------

if (-not $SkipHyperVEnable) {
    Write-Step "Step 1: Enabling Hyper-V features"

    $feature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
    if ($feature.State -eq "Enabled") {
        Write-OK "Hyper-V is already enabled"
    } else {
        Write-Info "Enabling Hyper-V (requires restart after completion)..."
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -NoRestart
        Write-Warn "RESTART REQUIRED. After restarting, re-run this script with -SkipHyperVEnable"
        exit 0
    }
} else {
    Write-Info "Skipping Hyper-V enablement"
}

# -- Step 2: Create VM -------------------------------------------------------

if (-not $SkipVMCreation) {
    Write-Step "Step 2: Creating VM '$VMName'"

    # Check if VM already exists
    $existingVM = Get-VM -Name $VMName -ErrorAction SilentlyContinue
    if ($existingVM) {
        Write-Warn "VM '$VMName' already exists. Skipping creation."
        Write-Info "To reconfigure GPU-PV, use -SkipVMCreation flag"
    } else {
        if (-not $ISOPath -or -not (Test-Path $ISOPath)) {
            Write-Host "ERROR: Windows 11 ISO required. Download from:" -ForegroundColor Red
            Write-Host "  https://www.microsoft.com/software-download/windows11" -ForegroundColor Yellow
            Write-Host "Then run: .\setup_hyperv_vm.ps1 -ISOPath 'C:\path\to\Win11.iso'" -ForegroundColor Yellow
            exit 1
        }

        # Determine VHDX path
        if (-not $VHDXPath) {
            $defaultPath = (Get-VMHost).VirtualHardDiskPath
            $VHDXPath = Join-Path $defaultPath "$VMName.vhdx"
        }

        Write-Info "VHDX: $VHDXPath"
        Write-Info "RAM: $($RAM / 1GB) GB"
        Write-Info "CPUs: $CPUs"
        Write-Info "Disk: $DiskSizeGB GB"

        # Get default switch
        $switch = Get-VMSwitch -SwitchType Internal -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $switch) {
            $switch = Get-VMSwitch -Name "Default Switch" -ErrorAction SilentlyContinue
        }
        if (-not $switch) {
            Write-Warn "No virtual switch found. Creating 'Default Switch'..."
            New-VMSwitch -Name "Default Switch" -SwitchType Internal
            $switch = Get-VMSwitch -Name "Default Switch"
        }

        # Create VHDX
        Write-Info "Creating virtual hard disk..."
        New-VHD -Path $VHDXPath -SizeBytes ($DiskSizeGB * 1GB) -Dynamic | Out-Null

        # Create VM
        Write-Info "Creating Generation 2 VM..."
        New-VM -Name $VMName `
            -MemoryStartupBytes $RAM `
            -Generation 2 `
            -VHDPath $VHDXPath `
            -SwitchName $switch.Name | Out-Null

        # Configure VM
        Set-VM -Name $VMName -ProcessorCount $CPUs -DynamicMemory:$false
        Set-VM -Name $VMName -AutomaticCheckpointsEnabled $false

        # Disable Secure Boot (required for GPU-PV)
        # Set-VMFirmware -VMName $VMName -EnableSecureBoot Off

        # Mount ISO
        Add-VMDvdDrive -VMName $VMName -Path $ISOPath

        # Set boot order: DVD first, then hard disk
        $dvd = Get-VMDvdDrive -VMName $VMName
        $hdd = Get-VMHardDiskDrive -VMName $VMName
        Set-VMFirmware -VMName $VMName -BootOrder $dvd, $hdd

        # Enable Enhanced Session Mode for the VM
        Set-VM -Name $VMName -EnhancedSessionTransportType HvSocket

        Write-OK "VM '$VMName' created successfully"
        Write-Info "Boot the VM to install Windows 11, then proceed to GPU-PV setup"
    }
} else {
    Write-Info "Skipping VM creation"
}

# -- Step 3: Configure GPU-PV ------------------------------------------------

if (-not $SkipGPUPV) {
    Write-Step "Step 3: Configuring GPU Paravirtualization"

    $vm = Get-VM -Name $VMName -ErrorAction SilentlyContinue
    if (-not $vm) {
        Write-Host "ERROR: VM '$VMName' not found" -ForegroundColor Red
        exit 1
    }

    if ($vm.State -ne "Off") {
        Write-Host "ERROR: VM must be shut down for GPU-PV configuration. Current state: $($vm.State)" -ForegroundColor Red
        Write-Host "  Run: Stop-VM -Name '$VMName'" -ForegroundColor Yellow
        exit 1
    }

    # Remove existing GPU adapter if present
    $existingAdapter = Get-VMGpuPartitionAdapter -VMName $VMName -ErrorAction SilentlyContinue
    if ($existingAdapter) {
        Write-Info "Removing existing GPU partition adapter..."
        Remove-VMGpuPartitionAdapter -VMName $VMName
    }

    # Add GPU partition adapter — prefer NVIDIA (VEN_10DE) over AMD iGPU if both present
    Write-Info "Adding GPU partition adapter..."
    $nvidiaGpu = Get-VMHostPartitionableGpu | Where-Object { $_.InstancePath -match "VEN_10DE" } | Select-Object -First 1
    if ($nvidiaGpu) {
        Write-Info "Using NVIDIA GPU: $($nvidiaGpu.Name)"
        Add-VMGpuPartitionAdapter -VMName $VMName -InstancePath $nvidiaGpu.InstancePath
    } else {
        Write-Warn "No NVIDIA GPU found, using first available GPU"
        Add-VMGpuPartitionAdapter -VMName $VMName
    }

    # Configure GPU partition resources
    Write-Info "Setting GPU partition resource limits..."
    $gpuParams = @{
        VMName                = $VMName
        MinPartitionVRAM      = 1
        MaxPartitionVRAM      = 1000000000
        OptimalPartitionVRAM  = 1000000000
        MinPartitionEncode    = 1
        MaxPartitionEncode    = 1000000000
        OptimalPartitionEncode = 1000000000
        MinPartitionDecode    = 1
        MaxPartitionDecode    = 1000000000
        OptimalPartitionDecode = 1000000000
        MinPartitionCompute   = 1
        MaxPartitionCompute   = 1000000000
        OptimalPartitionCompute = 1000000000
    }
    Set-VMGpuPartitionAdapter @gpuParams

    # Configure memory-mapped I/O
    Write-Info "Setting memory-mapped I/O space..."
    Set-VM -Name $VMName `
        -GuestControlledCacheTypes $true `
        -LowMemoryMappedIoSpace 1GB `
        -HighMemoryMappedIoSpace 32GB

    Write-OK "GPU-PV configured"
    Write-Warn "You still need to copy NVIDIA driver files into the VM (see Step 4)"
}

# -- Step 4: Copy GPU drivers ------------------------------------------------

if ($CopyDrivers) {
    Write-Step "Step 4: Copying NVIDIA driver files to VM"

    $vm = Get-VM -Name $VMName -ErrorAction SilentlyContinue
    if (-not $vm) {
        Write-Host "ERROR: VM '$VMName' not found" -ForegroundColor Red
        exit 1
    }

    if ($vm.State -ne "Off") {
        Write-Host "ERROR: VM must be shut down to mount its VHDX. Current state: $($vm.State)" -ForegroundColor Red
        exit 1
    }

    # Find the host NVIDIA driver folder
    $driverStoreBase = "C:\Windows\System32\DriverStore\FileRepository"
    $nvDriverFolders = Get-ChildItem -Path $driverStoreBase -Directory -Filter "nv_dispi.inf_amd64_*" |
        Sort-Object LastWriteTime -Descending
    if (-not $nvDriverFolders) {
        Write-Host "ERROR: No NVIDIA driver folder found in $driverStoreBase" -ForegroundColor Red
        Write-Host "  Expected: nv_dispi.inf_amd64_*" -ForegroundColor Yellow
        exit 1
    }
    $hostDriverPath = $nvDriverFolders[0].FullName
    $hostDriverFolderName = $nvDriverFolders[0].Name
    Write-Info "Host driver folder: $hostDriverPath"

    # Also need nvapi64.dll and other system files
    $systemFiles = @(
        "C:\Windows\System32\nvapi64.dll",
        "C:\Windows\System32\nvcuda.dll",
        "C:\Windows\System32\nvd3dumx.dll"
    )

    # Mount the VM's VHDX
    $vhdx = (Get-VMHardDiskDrive -VMName $VMName).Path
    if (-not $vhdx) {
        Write-Host "ERROR: Could not find VHDX path for VM '$VMName'" -ForegroundColor Red
        exit 1
    }
    Write-Info "Mounting VHDX: $vhdx"

    # Clean up any leftover mount from a previous failed run
    $vhdInfo = Get-VHD -Path $vhdx -ErrorAction SilentlyContinue
    if ($vhdInfo -and $vhdInfo.Attached) {
        Write-Warn "VHDX was already mounted — dismounting first for clean state..."
        Dismount-VHD -Path $vhdx
        Start-Sleep -Seconds 2
    }

    Mount-VHD -Path $vhdx

    # Wait for disk enumeration to complete, retrying until DiskNumber is available
    $vhdInfo = $null
    $disk = $null
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 2
        $vhdInfo = Get-VHD -Path $vhdx -ErrorAction SilentlyContinue
        if ($vhdInfo -and $null -ne $vhdInfo.DiskNumber) {
            $disk = Get-Disk -Number $vhdInfo.DiskNumber -ErrorAction SilentlyContinue
            if ($disk) { break }
        }
        Write-Info "Waiting for disk to enumerate (attempt $($i+1)/10)..."
    }

    if (-not $disk) {
        Dismount-VHD -Path $vhdx
        Write-Host "ERROR: Could not resolve disk from mounted VHDX (DiskNumber=$($vhdInfo.DiskNumber))" -ForegroundColor Red
        exit 1
    }
    Write-Info "VHDX mounted as Disk $($disk.Number)"

    # Bring disk online and writable — Hyper-V VHDXs often land Offline/ReadOnly
    if ($disk.IsOffline) {
        Write-Info "Bringing disk online..."
        $disk | Set-Disk -IsOffline $false
    }
    if ($disk.IsReadOnly) {
        Write-Info "Clearing read-only flag..."
        $disk | Set-Disk -IsReadOnly $false
    }

    $driveLetter = ($disk | Get-Partition | Get-Volume |
        Where-Object { $_.DriveLetter } | Select-Object -First 1).DriveLetter

    if (-not $driveLetter) {
        # No drive letter assigned yet — find the largest partition (Windows OS partition)
        # and assign one. Skips EFI (~100MB) and MSR (~16MB) partitions.
        $partition = $disk | Get-Partition | Where-Object { $_.Size -gt 1GB } | Select-Object -First 1
        if ($partition) {
            $driveLetter = ($partition | Add-PartitionAccessPath -AssignDriveLetter -PassThru).DriveLetter
        }
    }

    if (-not $driveLetter) {
        Dismount-VHD -Path $vhdx
        Write-Host "ERROR: Could not determine drive letter for mounted VHDX" -ForegroundColor Red
        exit 1
    }

    Write-Info "VHDX mounted at ${driveLetter}:"

    # Create target directories
    $targetDriverStore = "${driveLetter}:\Windows\System32\DriverStore\FileRepository\$hostDriverFolderName"
    $targetSystem32 = "${driveLetter}:\Windows\System32"

    if (-not (Test-Path $targetDriverStore)) {
        New-Item -Path $targetDriverStore -ItemType Directory -Force | Out-Null
    }

    # Copy driver folder
    Write-Info "Copying driver files (this may take a few minutes)..."
    Copy-Item -Path "$hostDriverPath\*" -Destination $targetDriverStore -Recurse -Force
    Write-OK "Driver files copied to $targetDriverStore"

    # Copy system DLLs
    foreach ($file in $systemFiles) {
        if (Test-Path $file) {
            $fileName = Split-Path $file -Leaf
            Copy-Item -Path $file -Destination "$targetSystem32\$fileName" -Force
            Write-OK "Copied $fileName"
        } else {
            Write-Warn "$file not found on host, skipping"
        }
    }

    # Dismount
    Dismount-VHD -Path $vhdx
    Write-OK "VHDX dismounted. Driver files are in place."
    Write-Info "Start the VM and run 'dxdiag' to verify the NVIDIA adapter appears."
}

# -- Summary ------------------------------------------------------------------

Write-Step "Setup Summary"

$vm = Get-VM -Name $VMName -ErrorAction SilentlyContinue
if ($vm) {
    Write-Info "VM Name:    $VMName"
    Write-Info "State:      $($vm.State)"
    Write-Info "RAM:        $($vm.MemoryStartup / 1GB) GB"
    Write-Info "CPUs:       $($vm.ProcessorCount)"

    $gpu = Get-VMGpuPartitionAdapter -VMName $VMName -ErrorAction SilentlyContinue
    if ($gpu) {
        Write-OK "GPU-PV: Configured"
    } else {
        Write-Warn "GPU-PV: Not configured"
    }
}

Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. If Windows isn't installed yet: Start-VM -Name '$VMName'" -ForegroundColor White
Write-Host "     Install Windows 11, then shut down the VM" -ForegroundColor Gray
Write-Host "  2. Copy GPU drivers:  .\setup_hyperv_vm.ps1 -SkipHyperVEnable -SkipVMCreation -SkipGPUPV -CopyDrivers" -ForegroundColor White
Write-Host "  3. Start VM, verify GPU with dxdiag" -ForegroundColor White
Write-Host "  4. Install Battle.net + D2R + Python 3.13 in VM" -ForegroundColor White
Write-Host "  5. Copy pindlebot-v2 into VM, install requirements" -ForegroundColor White
Write-Host "  6. Run bot: python src/main.py" -ForegroundColor White
Write-Host ""
Write-Host "  Alternative: If GPU-PV is too fiddly, use Easy-GPU-PV:" -ForegroundColor Gray
Write-Host "    https://github.com/jamesstringerparsec/Easy-GPU-PV" -ForegroundColor Gray
Write-Host "  Or switch to VMware Workstation Player (simpler 3D accel)" -ForegroundColor Gray
