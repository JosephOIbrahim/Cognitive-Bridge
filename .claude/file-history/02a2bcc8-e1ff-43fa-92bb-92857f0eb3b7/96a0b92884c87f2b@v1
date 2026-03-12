// TranslatorsCard.Build.cs
// Build configuration for Claude Code → UE5.7 Bridge v2.0.0
//
// v2.0.0 Changes:
// - USD-native communication via text-based USDA parsing
// - Behavioral signals for ADHD_MoE expert routing
// - JSON fallback for backward compatibility
//
// Key modules:
// - DirectoryWatcher: For file change detection
// - Json/JsonUtilities: For protocol message handling
// - Regex: For USDA text parsing
// - USDImporter: Optional, for USD Stage Actor integration (editor-only)

using UnrealBuildTool;

public class TranslatorsCard : ModuleRules
{
    public TranslatorsCard(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        // Core modules
        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore"
        });

        // JSON handling for protocol messages (v1.0.0 fallback)
        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Json",
            "JsonUtilities"
        });

        // File watching (Editor-only - use polling in packaged builds)
        if (Target.bBuildEditor)
        {
            PrivateDependencyModuleNames.Add("DirectoryWatcher");
            PrivateDefinitions.Add("WITH_DIRECTORY_WATCHER=1");

            // USD Stage Actor support (editor-only)
            // Note: USDA text parsing works without this module
            // This is only needed for live USD Stage manipulation
            PrivateDefinitions.Add("WITH_USD_SUPPORT=1");
        }

        // UMG / Slate UI support (required for question display widgets)
        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "Slate",
            "SlateCore",
            "UMG"
        });

        // Enable IWYU (Include What You Use)
        IWYUSupport = IWYUSupport.Full;

        // v2.0.0: Bridge version definition
        PrivateDefinitions.Add("BRIDGE_VERSION=TEXT(\"2.0.0\")");

        // Ensure generated headers are available
        PublicIncludePaths.Add(ModuleDirectory);
        PrivateIncludePaths.Add(ModuleDirectory + "/UI");
    }
}
