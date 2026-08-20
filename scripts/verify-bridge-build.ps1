param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$UpstreamRoot
)

$ErrorActionPreference = "Stop"

$dll = Join-Path $UpstreamRoot "IAGrim/bin/Release/net10.0-windows/IAGrim.dll"
if (-not (Test-Path $dll)) {
    throw "Missing patched IAGrim.dll"
}

$text = [Text.Encoding]::Unicode.GetString([IO.File]::ReadAllBytes($dll))
if (-not $text.Contains("Decky item transfer bridge started")) {
    throw "Bridge marker missing"
}

# These project assemblies in the official Item Assistant installation all use
# assembly version 1.0.0.0. Global MSBuild version properties alter every
# project in the solution and make the patched IAGrim.dll impossible to load
# beside the official dependencies.
$expectedReferences = [ordered]@{
    "Cloud" = "1.0.0.0"
    "DataAccess" = "1.0.0.0"
    "DllInjector" = "1.0.0.0"
    "EvilsoftCommons" = "1.0.0.0"
    "Parser" = "1.0.0.0"
    "StatTranslator" = "1.0.0.0"
}

$stream = [IO.File]::OpenRead((Resolve-Path $dll))
try {
    $peReader = [Reflection.PortableExecutable.PEReader]::new($stream)
    try {
        $metadata = [Reflection.Metadata.PEReaderExtensions]::GetMetadataReader($peReader)
        $actualReferences = @{}
        foreach ($handle in $metadata.AssemblyReferences) {
            $reference = $metadata.GetAssemblyReference($handle)
            $name = $metadata.GetString($reference.Name)
            $actualReferences[$name] = $reference.Version.ToString()
        }

        foreach ($entry in $expectedReferences.GetEnumerator()) {
            if (-not $actualReferences.ContainsKey($entry.Key)) {
                throw "Missing assembly reference: $($entry.Key)"
            }
            if ($actualReferences[$entry.Key] -ne $entry.Value) {
                throw "Wrong assembly reference for $($entry.Key): expected $($entry.Value), found $($actualReferences[$entry.Key])"
            }
        }
    }
    finally {
        $peReader.Dispose()
    }
}
finally {
    $stream.Dispose()
}

Write-Host "Bridge marker and official dependency assembly versions verified."
