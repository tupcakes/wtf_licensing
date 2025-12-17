<#
.SYNOPSIS
    Generate simplified JSON file of all O365 licenses with embedded supersedence relationships.

.DESCRIPTION
    This script downloads the Microsoft licensing CSV, parses all product SKUs and 
    service plans, identifies supersedence relationships, and generates a simplified
    JSON file where each product includes arrays of licenses it supersedes and is superseded by.

.PARAMETER UseLocal
    Use the local CSV file in tests/ directory instead of downloading from Microsoft.

.EXAMPLE
    .\Generate-LicenseData-Simple.ps1
    Downloads latest data from Microsoft and generates o365_licenses_simple.json

.EXAMPLE
    .\Generate-LicenseData-Simple.ps1 -UseLocal
    Uses local test file instead of downloading
#>

[CmdletBinding()]
param(
    [switch]$UseLocal
)

# Configuration
$CSV_URL = "https://download.microsoft.com/download/e/3/e/e3e9faf2-f28b-490a-9ada-c6089a1fc5b0/Product%20names%20and%20service%20plan%20identifiers%20for%20licensing.csv"
$LOCAL_CSV_PATH = Join-Path $PSScriptRoot "tests\Product names and service plan identifiers for licensing.csv"
$OUTPUT_JSON = Join-Path $PSScriptRoot "o365_licenses_simple.json"
$TEMP_CSV = Join-Path $PSScriptRoot "o365_licenses_temp.csv"

function Download-LicenseCSV {
    param(
        [string]$Url,
        [string]$OutputPath
    )
    
    Write-Host "Downloading CSV from $Url..." -ForegroundColor Cyan
    try {
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($Url, $OutputPath)
        Write-Host "Downloaded to $OutputPath" -ForegroundColor Green
    }
    catch {
        Write-Error "Error downloading CSV: $_"
        throw
    }
    finally {
        if ($webClient) {
            $webClient.Dispose()
        }
    }
}

function Parse-LicenseCSV {
    param(
        [string]$CsvPath
    )
    
    $products = @{}
    
    Write-Host "Parsing CSV and building license structure..." -ForegroundColor Cyan
    Write-Host "  (filtering out self-referencing service plans...)" -ForegroundColor Gray
    
    $csvData = Import-Csv -Path $CsvPath -Encoding UTF8
    
    foreach ($row in $csvData) {
        $productName = $row.Product_Display_Name.Trim()
        $stringId = $row.String_Id.Trim()
        $guid = $row.GUID.Trim()
        
        $servicePlanName = $row.Service_Plan_Name.Trim()
        $servicePlanId = $row.Service_Plan_Id.Trim()
        $servicePlanFriendlyName = $row.Service_Plans_Included_Friendly_Names.Trim()
        
        if (-not $products.ContainsKey($guid)) {
            $products[$guid] = @{
                guid = $guid
                product_display_name = $productName
                string_id = $stringId
                included_service_plans = @()
                supersedes = @()
                superseded_by = @()
            }
        }
        
        if ($servicePlanName -ne $stringId) {
            $servicePlanEntry = @{
                service_plan_name = $servicePlanName
                service_plan_id = $servicePlanId
                service_plan_friendly_name = $servicePlanFriendlyName
            }
            $products[$guid].included_service_plans += $servicePlanEntry
        }
    }
    
    return $products
}

function Get-ExpandedServicePlans {
    param(
        [string]$ProductGuid,
        [hashtable]$Products,
        [hashtable]$ServicePlanNameToProductGuid,
        [hashtable]$ExpandedCache,
        [System.Collections.Generic.HashSet[string]]$VisitedProducts
    )
    
    if ($ExpandedCache.ContainsKey($ProductGuid)) {
        return $ExpandedCache[$ProductGuid]
    }
    
    if ($VisitedProducts.Contains($ProductGuid)) {
        return @()
    }
    
    $null = $VisitedProducts.Add($ProductGuid)
    
    $allPlans = New-Object System.Collections.Generic.HashSet[string]
    $product = $Products[$ProductGuid]
    
    foreach ($servicePlan in $product.included_service_plans) {
        $planId = $servicePlan.service_plan_id
        $planName = $servicePlan.service_plan_name
        
        $null = $allPlans.Add($planId)
        
        if ($ServicePlanNameToProductGuid.ContainsKey($planName)) {
            $referencedProductGuid = $ServicePlanNameToProductGuid[$planName]
            
            if ($referencedProductGuid -ne $ProductGuid) {
                $expandedPlans = Get-ExpandedServicePlans -ProductGuid $referencedProductGuid `
                    -Products $Products `
                    -ServicePlanNameToProductGuid $ServicePlanNameToProductGuid `
                    -ExpandedCache $ExpandedCache `
                    -VisitedProducts $VisitedProducts
                
                foreach ($expandedPlan in $expandedPlans) {
                    $null = $allPlans.Add($expandedPlan)
                }
            }
        }
    }
    
    $ExpandedCache[$ProductGuid] = @($allPlans)
    return @($allPlans)
}

function Add-SupersedenceRelationships {
    param(
        [hashtable]$Products
    )
    
    Write-Host "Analyzing supersedence relationships..." -ForegroundColor Cyan
    Write-Host "  (expanding transitive service plan relationships...)" -ForegroundColor Gray
    
    $servicePlanNameToProductGuid = @{}
    foreach ($guid in $Products.Keys) {
        $stringId = $Products[$guid].string_id
        $servicePlanNameToProductGuid[$stringId] = $guid
    }
    
    $expandedCache = @{}
    $productServicePlans = @{}
    
    Write-Host "  (calculating expanded service plans for each product...)" -ForegroundColor Gray
    foreach ($guid in $Products.Keys) {
        $visited = New-Object System.Collections.Generic.HashSet[string]
        $expandedPlans = Get-ExpandedServicePlans -ProductGuid $guid `
            -Products $Products `
            -ServicePlanNameToProductGuid $servicePlanNameToProductGuid `
            -ExpandedCache $expandedCache `
            -VisitedProducts $visited
        
        $productServicePlans[$guid] = $expandedPlans
    }
    
    Write-Host "  (comparing products to find supersedence...)" -ForegroundColor Gray
    $productList = @($Products.Keys)
    $totalComparisons = ($productList.Count * ($productList.Count - 1)) / 2
    $comparisonsDone = 0
    $lastProgressUpdate = 0
    
    for ($i = 0; $i -lt $productList.Count; $i++) {
        $guid1 = $productList[$i]
        $product1 = $Products[$guid1]
        $plans1 = @($productServicePlans[$guid1])
        
        for ($j = $i + 1; $j -lt $productList.Count; $j++) {
            $guid2 = $productList[$j]
            $product2 = $Products[$guid2]
            $plans2 = @($productServicePlans[$guid2])
            
            $comparisonsDone++
            $percentComplete = [int](($comparisonsDone / $totalComparisons) * 100)
            if ($percentComplete -ge $lastProgressUpdate + 10) {
                Write-Host "    Progress: $percentComplete% complete..." -ForegroundColor Gray
                $lastProgressUpdate = $percentComplete
            }
            
            if ($plans1.Count -gt 0) {
                $isSubset = $true
                foreach ($plan in $plans1) {
                    if ($plans2 -notcontains $plan) {
                        $isSubset = $false
                        break
                    }
                }
                
                if ($isSubset) {
                    $Products[$guid1].superseded_by += @{
                        guid = $guid2
                        string_id = $product2.string_id
                        name = $product2.product_display_name
                    }
                    
                    $Products[$guid2].supersedes += @{
                        guid = $guid1
                        string_id = $product1.string_id
                        name = $product1.product_display_name
                    }
                }
            }
            
            if ($plans2.Count -gt 0) {
                $isSubset = $true
                foreach ($plan in $plans2) {
                    if ($plans1 -notcontains $plan) {
                        $isSubset = $false
                        break
                    }
                }
                
                if ($isSubset) {
                    $Products[$guid2].superseded_by += @{
                        guid = $guid1
                        string_id = $product1.string_id
                        name = $product1.product_display_name
                    }
                    
                    $Products[$guid1].supersedes += @{
                        guid = $guid2
                        string_id = $product2.string_id
                        name = $product2.product_display_name
                    }
                }
            }
        }
    }
}

# Main execution
try {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  O365 License Data Generator - Simplified Structure" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    if ($UseLocal) {
        $csvPath = $LOCAL_CSV_PATH
        if (-not (Test-Path $csvPath)) {
            Write-Error "Local CSV file not found at $csvPath"
            exit 1
        }
        Write-Host "Using local CSV file: $csvPath" -ForegroundColor Yellow
    }
    else {
        $csvPath = $TEMP_CSV
        Download-LicenseCSV -Url $CSV_URL -OutputPath $csvPath
    }
    
    $products = Parse-LicenseCSV -CsvPath $csvPath
    
    Add-SupersedenceRelationships -Products $products
    
    $totalSupersedes = 0
    foreach ($guid in $products.Keys) {
        $totalSupersedes += $products[$guid].supersedes.Count
    }
    
    $licenseData = @{
        products = $products
        metadata = @{
            total_products = $products.Count
            total_supersedence_relationships = $totalSupersedes
            source_url = $CSV_URL
            description = "Simplified O365 license structure with embedded supersedence relationships. Each product includes arrays of licenses it supersedes and is superseded by."
            generated_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
        }
    }
    
    Write-Host "Writing simplified license data to $OUTPUT_JSON..." -ForegroundColor Cyan
    
    $jsonOutput = $licenseData | ConvertTo-Json -Depth 10 -Compress:$false
    $jsonOutput | Out-File -FilePath $OUTPUT_JSON -Encoding UTF8
    
    $fileSize = (Get-Item $OUTPUT_JSON).Length / 1MB
    
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "SUMMARY" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "Total Products: $($products.Count)" -ForegroundColor White
    Write-Host "Total Supersedence Relationships: $totalSupersedes" -ForegroundColor White
    Write-Host ""
    Write-Host "Output file: $OUTPUT_JSON" -ForegroundColor White
    Write-Host "File size: $("{0:N2}" -f $fileSize) MB" -ForegroundColor White
    Write-Host "============================================================" -ForegroundColor Green
    
    if (-not $UseLocal -and (Test-Path $TEMP_CSV)) {
        Remove-Item $TEMP_CSV
        Write-Host "Temporary CSV file cleaned up." -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "[SUCCESS] Simplified license data generated successfully!" -ForegroundColor Green
    Write-Host ""
}
catch {
    Write-Host ""
    Write-Host "[ERROR] $_" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Red
    Write-Host ""
    exit 1
}
