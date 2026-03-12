// BridgeEditorSubsystem.cpp
// Editor subsystem implementation.
// Phase 3: DirectoryWatcher logic migrated from BridgeComponent.

#include "BridgeEditorSubsystem.h"
#include "TranslatorsBridgeRuntime.h"
#include "DirectoryWatcherModule.h"
#include "IDirectoryWatcher.h"

void UBridgeEditorSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    UE_LOG(LogTranslatorsBridge, Log, TEXT("BridgeEditorSubsystem initialized"));
}

void UBridgeEditorSubsystem::Deinitialize()
{
    StopWatching();
    StopBridgeProcess();

    UE_LOG(LogTranslatorsBridge, Log, TEXT("BridgeEditorSubsystem deinitialized"));
    Super::Deinitialize();
}


// === FILE WATCHING ===

void UBridgeEditorSubsystem::StartWatching(const FString& BridgePath)
{
    if (bIsWatching)
    {
        if (WatchedPath == BridgePath)
        {
            return; // Already watching this path
        }
        StopWatching(); // Switch to new path
    }

    FDirectoryWatcherModule& DirWatcherModule =
        FModuleManager::LoadModuleChecked<FDirectoryWatcherModule>(TEXT("DirectoryWatcher"));
    IDirectoryWatcher* DirWatcher = DirWatcherModule.Get();

    if (!DirWatcher)
    {
        UE_LOG(LogTranslatorsBridge, Error, TEXT("Could not get DirectoryWatcher module"));
        return;
    }

    IDirectoryWatcher::FDirectoryChanged Callback =
        IDirectoryWatcher::FDirectoryChanged::CreateUObject(
            this, &UBridgeEditorSubsystem::OnDirectoryChanged);

    bool bSuccess = DirWatcher->RegisterDirectoryChangedCallback_Handle(
        BridgePath, Callback, WatchHandle, 0);

    if (bSuccess)
    {
        WatchedPath = BridgePath;
        bIsWatching = true;
        UE_LOG(LogTranslatorsBridge, Log, TEXT("Editor file watcher registered for: %s"), *BridgePath);
    }
    else
    {
        UE_LOG(LogTranslatorsBridge, Error, TEXT("Failed to register editor file watcher for: %s"), *BridgePath);
    }
}


void UBridgeEditorSubsystem::StopWatching()
{
    if (!bIsWatching || !WatchHandle.IsValid())
    {
        return;
    }

    FDirectoryWatcherModule& DirWatcherModule =
        FModuleManager::LoadModuleChecked<FDirectoryWatcherModule>(TEXT("DirectoryWatcher"));
    IDirectoryWatcher* DirWatcher = DirWatcherModule.Get();

    if (DirWatcher)
    {
        DirWatcher->UnregisterDirectoryChangedCallback_Handle(WatchedPath, WatchHandle);
        UE_LOG(LogTranslatorsBridge, Log, TEXT("Editor file watcher unregistered"));
    }

    bIsWatching = false;
    WatchedPath.Empty();
}


void UBridgeEditorSubsystem::OnDirectoryChanged(const TArray<FFileChangeData>& Changes)
{
    for (const FFileChangeData& Change : Changes)
    {
        bool bIsUsdProfile = Change.Filename.EndsWith(TEXT("cognitive_profile.usda")) ||
                             Change.Filename.EndsWith(TEXT("cognitive_substrate.usda"));

        bool bIsBridgeState = Change.Filename.EndsWith(TEXT("state.json")) ||
                              Change.Filename.EndsWith(TEXT("bridge_state.usda"));

        if (bIsBridgeState || bIsUsdProfile)
        {
            // Broadcast to any listeners (BridgeComponents, editor tools, etc.)
            OnBridgeFileChanged.Broadcast(Change.Filename, bIsUsdProfile);
        }
    }
}


// === PYTHON PROCESS ===

void UBridgeEditorSubsystem::StartBridgeProcess()
{
    if (bBridgeProcessRunning)
    {
        UE_LOG(LogTranslatorsBridge, Warning, TEXT("Bridge process already running"));
        return;
    }

    // TODO: Launch bridge_orchestrator.py via IPythonScriptPlugin or FPlatformProcess::CreateProc()
    // For now this is a stub — the artist launches the bridge externally via
    // Launch-TranslatorsBridge.ps1 or manually running bridge_orchestrator.py.
    UE_LOG(LogTranslatorsBridge, Log, TEXT("StartBridgeProcess: external launch required (Launch-TranslatorsBridge.ps1)"));
}

void UBridgeEditorSubsystem::StopBridgeProcess()
{
    if (!bBridgeProcessRunning)
    {
        return;
    }

    // TODO: Terminate the Python bridge process cleanly
    UE_LOG(LogTranslatorsBridge, Log, TEXT("StopBridgeProcess: stub"));
    bBridgeProcessRunning = false;
}

bool UBridgeEditorSubsystem::IsBridgeProcessRunning() const
{
    return bBridgeProcessRunning;
}
