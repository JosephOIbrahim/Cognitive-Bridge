// BridgeEditorSubsystem.cpp
// Editor subsystem implementation.
// Phase 1: Stub. Phase 3 will migrate DirectoryWatcher and process management here.

#include "BridgeEditorSubsystem.h"
#include "TranslatorsBridgeRuntime.h"

void UBridgeEditorSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    UE_LOG(LogTranslatorsBridge, Log, TEXT("BridgeEditorSubsystem initialized"));

    // Phase 3 TODO: Set up IDirectoryWatcher for BridgePath
    // Phase 3 TODO: Auto-launch bridge_orchestrator.py if configured
}

void UBridgeEditorSubsystem::Deinitialize()
{
    StopBridgeProcess();

    // Phase 3 TODO: Tear down IDirectoryWatcher

    UE_LOG(LogTranslatorsBridge, Log, TEXT("BridgeEditorSubsystem deinitialized"));
    Super::Deinitialize();
}

void UBridgeEditorSubsystem::StartBridgeProcess()
{
    if (bBridgeProcessRunning)
    {
        UE_LOG(LogTranslatorsBridge, Warning, TEXT("Bridge process already running"));
        return;
    }

    // Phase 3 TODO: Launch bridge_orchestrator.py via IPythonScriptPlugin
    // or FPlatformProcess::CreateProc()
    UE_LOG(LogTranslatorsBridge, Log, TEXT("StartBridgeProcess called (stub — implement in Phase 3)"));
}

void UBridgeEditorSubsystem::StopBridgeProcess()
{
    if (!bBridgeProcessRunning)
    {
        return;
    }

    // Phase 3 TODO: Terminate the Python bridge process cleanly
    UE_LOG(LogTranslatorsBridge, Log, TEXT("StopBridgeProcess called (stub — implement in Phase 3)"));
    bBridgeProcessRunning = false;
}

bool UBridgeEditorSubsystem::IsBridgeProcessRunning() const
{
    return bBridgeProcessRunning;
}
