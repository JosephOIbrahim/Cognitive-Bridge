// BridgeEditorSubsystem.h
// Editor subsystem that owns:
// - IDirectoryWatcher for ~/.translators/ file change detection
// - Python bridge_orchestrator.py process lifecycle
// - MCP server startup/shutdown
//
// Created during the plugin split (Phase 1). Logic migrated from
// BridgeComponent's WITH_EDITOR blocks in Phase 3.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/EditorSubsystem.h"
#include "BridgeEditorSubsystem.generated.h"

UCLASS()
class TRANSLATORSBRIDGEEDITOR_API UBridgeEditorSubsystem : public UEditorSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    /** Launch the Python bridge_orchestrator process */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge|Editor")
    void StartBridgeProcess();

    /** Terminate the Python bridge_orchestrator process */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge|Editor")
    void StopBridgeProcess();

    /** Check if the Python bridge process is running */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "Translators Bridge|Editor")
    bool IsBridgeProcessRunning() const;

private:
    // Directory watcher handle (migrated from BridgeComponent in Phase 3)
    FDelegateHandle WatchHandle;

    // Python process handle
    FProcHandle BridgeProcessHandle;
    bool bBridgeProcessRunning = false;
};
