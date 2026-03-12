// TranslatorsCard.Build.cs
// Build configuration for the TranslatorsCard game module.
//
// Phase 4: Game flow logic migrated to TranslatorsBridgeRuntime plugin.
// This module now depends on the plugin for BridgeTypes.h and the subsystem.
// BridgeComponent is a thin relay to UTranslatorsBridgeSubsystem.

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

        // TranslatorsBridge plugin — subsystem, BridgeTypes, delegates
        PublicDependencyModuleNames.Add("TranslatorsBridgeRuntime");

        // Editor-only features
        // DirectoryWatcher migrated to TranslatorsBridgeEditor plugin module (Phase 3).
        if (Target.bBuildEditor)
        {
            // USD Stage Actor support (editor-only)
            // Note: USDA text parsing works without this module
            // This is only needed for live USD Stage manipulation
            PrivateDefinitions.Add("WITH_USD_SUPPORT=1");

            // Remote Control API (editor-only)
            // Enables REST API on localhost:30010 for external tool access
            PrivateDependencyModuleNames.Add("RemoteControl");
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

        // Bridge version (matches plugin — defined in TranslatorsBridgeRuntime.Build.cs)
        // Kept here for legacy references; canonical version is BRIDGE_VERSION from the plugin.

        // Ensure generated headers are available
        PublicIncludePaths.Add(ModuleDirectory);
        PrivateIncludePaths.Add(ModuleDirectory + "/UI");
    }
}
