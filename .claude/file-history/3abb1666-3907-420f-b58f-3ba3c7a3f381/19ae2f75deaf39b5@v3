// BridgeComponent.cpp
// Claude Code → UE5.7 File-Based Bridge Implementation
// v2.0.0: USD-native communication with JSON fallback

#include "BridgeComponent.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformFileManager.h"
#include "JsonObjectConverter.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#include "Internationalization/Regex.h"

// Directory watcher (editor-only)
#if WITH_DIRECTORY_WATCHER
#include "DirectoryWatcherModule.h"
#include "IDirectoryWatcher.h"
#endif


UBridgeComponent::UBridgeComponent()
{
    PrimaryComponentTick.bCanEverTick = true;

    // Resolve home directory reliably on Windows
    // FPlatformProcess::UserHomeDir() can return Documents folder on some configs
    FString HomePath;

#if PLATFORM_WINDOWS
    // Use USERPROFILE env var directly (most reliable on Windows)
    FString UserProfile = FPlatformMisc::GetEnvironmentVariable(TEXT("USERPROFILE"));
    if (!UserProfile.IsEmpty())
    {
        HomePath = UserProfile;
    }
    else
    {
        HomePath = FPlatformProcess::UserHomeDir();
    }
#else
    HomePath = FPlatformProcess::UserHomeDir();
#endif

    // Clean up path separators and trailing slashes
    FPaths::NormalizeDirectoryName(HomePath);

    BridgePath = FPaths::Combine(HomePath, TEXT(".translators"));
}


void UBridgeComponent::BeginPlay()
{
    Super::BeginPlay();

    BridgeLog(TEXT("========================================"));
    BridgeLog(TEXT("TRANSLATORS BRIDGE COMPONENT v2.0.0"));
    BridgeLog(TEXT("USD-native communication with JSON fallback"));
    BridgeLog(FString::Printf(TEXT("Bridge Path: %s"), *BridgePath));
    BridgeLog(FString::Printf(TEXT("Resolved state.json: %s"), *GetBridgeFilePath(TEXT("state.json"))));
    BridgeLog(TEXT("========================================"));

    // Ensure bridge directory exists
    IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
    if (!PlatformFile.DirectoryExists(*BridgePath))
    {
        PlatformFile.CreateDirectory(*BridgePath);
        BridgeLog(FString::Printf(TEXT("Created bridge directory: %s"), *BridgePath));
    }

    SetupFileWatcher();

    // Check for existing state files (Claude Code may have started first)
    // Prefer USD over JSON
    FString UsdFilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
    FString JsonFilePath = GetBridgeFilePath(TEXT("state.json"));

    if (PlatformFile.FileExists(*UsdFilePath))
    {
        BridgeLog(TEXT("Found existing bridge_state.usda - processing..."));
        ProcessStateFile();
    }
    else if (PlatformFile.FileExists(*JsonFilePath))
    {
        BridgeLog(TEXT("Found existing state.json - processing..."));
        ProcessStateFile();
    }
}


void UBridgeComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    TeardownFileWatcher();

    BridgeLog(TEXT("TRANSLATORS BRIDGE COMPONENT STOPPED"));

    Super::EndPlay(EndPlayReason);
}


void UBridgeComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

    // Polling fallback for non-editor builds
    if (bUsePolling)
    {
        PollTimer += DeltaTime;
        if (PollTimer >= PollInterval)
        {
            PollTimer = 0.0f;

            FString StateFilePath = GetBridgeFilePath(TEXT("state.json"));
            IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

            if (PlatformFile.FileExists(*StateFilePath))
            {
                FDateTime ModTime = PlatformFile.GetTimeStamp(*StateFilePath);
                if (ModTime > LastStateFileTime)
                {
                    LastStateFileTime = ModTime;
                    bStateChangePending = true;
                    TimeSinceLastStateChange = 0.0f;
                }
            }
        }
    }

    // Debounced state file processing
    if (bStateChangePending)
    {
        TimeSinceLastStateChange += DeltaTime;
        if (TimeSinceLastStateChange >= DebounceTime)
        {
            bStateChangePending = false;
            ProcessStateFile();
        }
    }

    // Debounced USD file processing
    if (bUsdChangePending)
    {
        TimeSinceLastUsdChange += DeltaTime;
        if (TimeSinceLastUsdChange >= DebounceTime)
        {
            bUsdChangePending = false;
            OnUsdFileChanged();
        }
    }
}


// === FILE WATCHING ===

void UBridgeComponent::SetupFileWatcher()
{
#if WITH_DIRECTORY_WATCHER
    FDirectoryWatcherModule& DirWatcherModule =
        FModuleManager::LoadModuleChecked<FDirectoryWatcherModule>(TEXT("DirectoryWatcher"));
    IDirectoryWatcher* DirWatcher = DirWatcherModule.Get();

    if (!DirWatcher)
    {
        BridgeLog(TEXT("ERROR: Could not get DirectoryWatcher module"));
        return;
    }

    IDirectoryWatcher::FDirectoryChanged Callback =
        IDirectoryWatcher::FDirectoryChanged::CreateUObject(
            this, &UBridgeComponent::OnDirectoryChanged);

    uint32 WatchFlags = 0; // No special flags needed

    bool bSuccess = DirWatcher->RegisterDirectoryChangedCallback_Handle(
        BridgePath, Callback, WatchHandle, WatchFlags);

    if (bSuccess)
    {
        BridgeLog(FString::Printf(TEXT("File watcher registered for: %s"), *BridgePath));
    }
    else
    {
        BridgeLog(TEXT("ERROR: Failed to register file watcher"));
    }
#else
    // Non-editor: Use polling in TickComponent
    BridgeLog(TEXT("DirectoryWatcher not available - using file polling"));
    bUsePolling = true;
#endif
}


void UBridgeComponent::TeardownFileWatcher()
{
#if WITH_DIRECTORY_WATCHER
    if (WatchHandle.IsValid())
    {
        FDirectoryWatcherModule& DirWatcherModule =
            FModuleManager::LoadModuleChecked<FDirectoryWatcherModule>(TEXT("DirectoryWatcher"));
        IDirectoryWatcher* DirWatcher = DirWatcherModule.Get();

        if (DirWatcher)
        {
            DirWatcher->UnregisterDirectoryChangedCallback_Handle(BridgePath, WatchHandle);
            BridgeLog(TEXT("File watcher unregistered"));
        }
    }
#endif
}


#if WITH_DIRECTORY_WATCHER
void UBridgeComponent::OnDirectoryChanged(const TArray<FFileChangeData>& Changes)
{
    for (const FFileChangeData& Change : Changes)
    {
        if (bVerboseLogging)
        {
            BridgeLog(FString::Printf(TEXT("File changed: %s"), *Change.Filename));
        }

        // State file changes (JSON or USD bridge state)
        if (Change.Filename.EndsWith(TEXT("state.json")) ||
            Change.Filename.EndsWith(TEXT("bridge_state.usda")))
        {
            // Debounce state file changes
            TimeSinceLastStateChange = 0.0f;
            bStateChangePending = true;
        }
        // USD cognitive profile changes (separate from bridge state)
        else if (Change.Filename.EndsWith(TEXT("cognitive_profile.usda")) ||
                 Change.Filename.EndsWith(TEXT("cognitive_substrate.usda")))
        {
            // Debounce USD profile file changes
            TimeSinceLastUsdChange = 0.0f;
            bUsdChangePending = true;
        }
    }
}
#endif


// === STATE HANDLING ===

void UBridgeComponent::ProcessStateFile()
{
    // Try USD mode first (v2.0.0)
    FString UsdFilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
    IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

    if (PlatformFile.FileExists(*UsdFilePath))
    {
        if (ProcessBridgeStateUsda())
        {
            return; // Successfully processed USD
        }
    }

    // Fall back to JSON mode (v1.0.0)
    FString FilePath = GetBridgeFilePath(TEXT("state.json"));
    FString Content;

    BridgeLog(FString::Printf(TEXT("Attempting to read: %s"), *FilePath));

    if (!FFileHelper::LoadFileToString(Content, *FilePath))
    {
        BridgeLog(FString::Printf(TEXT("FAILED to read: %s (exists: %d)"),
            *FilePath, PlatformFile.FileExists(*FilePath) ? 1 : 0));
        return;
    }

    // Parse JSON
    TSharedPtr<FJsonObject> JsonObj;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Content);

    if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
    {
        BridgeLog(TEXT("ERROR: Invalid JSON in state.json"));
        return;
    }

    CurrentStateJson = Content;
    bUsingUsdMode = false;

    // Route by type
    FString StateType;
    if (JsonObj->TryGetStringField(TEXT("type"), StateType))
    {
        if (StateType == TEXT("ready"))
        {
            HandleReadyState(JsonObj);
        }
        else if (StateType == TEXT("question"))
        {
            HandleQuestionState(JsonObj);
        }
        else if (StateType == TEXT("transition"))
        {
            HandleTransitionState(JsonObj);
        }
        else if (StateType == TEXT("finale"))
        {
            HandleFinaleState(JsonObj);
        }
        else
        {
            BridgeLog(FString::Printf(TEXT("Unknown state type: %s"), *StateType));
        }
    }
}


void UBridgeComponent::HandleReadyState(const TSharedPtr<FJsonObject>& JsonObj)
{
    // Support both flat and nested "ready" object
    const TSharedPtr<FJsonObject>* ReadyObjPtr;
    const TSharedPtr<FJsonObject>& ReadyData =
        JsonObj->TryGetObjectField(TEXT("ready"), ReadyObjPtr) ? *ReadyObjPtr : JsonObj;

    int32 TotalQuestions = ReadyData->GetIntegerField(TEXT("total_questions"));
    FString FirstScene = ReadyData->GetStringField(TEXT("first_scene"));

    BridgeLog(FString::Printf(TEXT("Claude Code ready! Total questions: %d, First scene: %s"),
        TotalQuestions, *FirstScene));

    bIsConnected = true;
    OnBridgeReady.Broadcast(TotalQuestions);
}


void UBridgeComponent::HandleQuestionState(const TSharedPtr<FJsonObject>& JsonObj)
{
    // Protocol nests question data under "question" key, but also support flat format
    const TSharedPtr<FJsonObject>* QuestionObjPtr;
    const TSharedPtr<FJsonObject>& QuestionData =
        JsonObj->TryGetObjectField(TEXT("question"), QuestionObjPtr) ? *QuestionObjPtr : JsonObj;

    // Parse into struct
    CurrentQuestion = FTranslatorsQuestion();
    CurrentQuestion.Index = QuestionData->GetIntegerField(TEXT("index"));
    CurrentQuestion.Total = QuestionData->GetIntegerField(TEXT("total"));
    CurrentQuestion.QuestionId = QuestionData->GetStringField(TEXT("id"));
    CurrentQuestion.Text = QuestionData->GetStringField(TEXT("text"));
    CurrentQuestion.Scene = QuestionData->GetStringField(TEXT("scene"));

    // Parse options array
    const TArray<TSharedPtr<FJsonValue>>* OptionsArray;
    if (QuestionData->TryGetArrayField(TEXT("options"), OptionsArray))
    {
        for (const TSharedPtr<FJsonValue>& OptionVal : *OptionsArray)
        {
            const TSharedPtr<FJsonObject>& OptionObj = OptionVal->AsObject();
            if (OptionObj.IsValid())
            {
                CurrentQuestion.OptionLabels.Add(OptionObj->GetStringField(TEXT("label")));
                CurrentQuestion.OptionDirections.Add(OptionObj->GetStringField(TEXT("direction")));
            }
        }
    }

    // Assign depth label based on question index
    CurrentQuestion.DepthLabel = GetDepthLabelForIndex(CurrentQuestion.Index);

    BridgeLog(FString::Printf(TEXT("Question %d/%d [%s]: %s"),
        CurrentQuestion.Index + 1, CurrentQuestion.Total, *CurrentQuestion.DepthLabel, *CurrentQuestion.QuestionId));

    // Broadcast raw JSON for flexible handling
    OnQuestionReceived.Broadcast(CurrentStateJson);
}


void UBridgeComponent::HandleTransitionState(const TSharedPtr<FJsonObject>& JsonObj)
{
    const TSharedPtr<FJsonObject>* TransObjPtr;
    const TSharedPtr<FJsonObject>& TransData =
        JsonObj->TryGetObjectField(TEXT("transition"), TransObjPtr) ? *TransObjPtr : JsonObj;

    FString Direction = TransData->GetStringField(TEXT("direction"));
    FString NextScene = TransData->GetStringField(TEXT("next_scene"));
    float Progress = TransData->GetNumberField(TEXT("progress"));

    BridgeLog(FString::Printf(TEXT("Transition: %s -> %s (%.0f%%)"),
        *Direction, *NextScene, Progress * 100.0f));

    OnTransitionReceived.Broadcast(Direction, NextScene);
}


void UBridgeComponent::HandleFinaleState(const TSharedPtr<FJsonObject>& JsonObj)
{
    const TSharedPtr<FJsonObject>* FinaleObjPtr;
    const TSharedPtr<FJsonObject>& FinaleData =
        JsonObj->TryGetObjectField(TEXT("finale"), FinaleObjPtr) ? *FinaleObjPtr : JsonObj;

    FString UsdPath = FinaleData->GetStringField(TEXT("usd_path"));
    FString Message = FinaleData->GetStringField(TEXT("message"));

    BridgeLog(FString::Printf(TEXT("FINALE: %s"), *Message));
    BridgeLog(FString::Printf(TEXT("USD Path: %s"), *UsdPath));

    OnFinaleReceived.Broadcast(UsdPath);
}


// === USD HANDLING ===

void UBridgeComponent::OnUsdFileChanged()
{
    BridgeLog(TEXT("USD file changed - reloading stage"));
    ReloadUsdStage();
    OnUsdUpdated.Broadcast();
}


void UBridgeComponent::ReloadUsdStage()
{
    // USD Stage reload is handled via Blueprint event OnUsdUpdated
    // Blueprints can call the USD Stage Actor's reload methods directly
    // This avoids C++ dependency on USDImporter module at runtime

    BridgeLog(TEXT("USD file changed - Broadcast OnUsdUpdated for Blueprint handling"));

    // The OnUsdUpdated delegate has already been broadcast in OnUsdFileChanged()
    // Blueprint implementations should handle the actual reload
}


void UBridgeComponent::ForceReloadUsdStage()
{
    ReloadUsdStage();
}


// === BLUEPRINT CALLABLE FUNCTIONS ===

void UBridgeComponent::SendAcknowledge()
{
    TSharedPtr<FJsonObject> JsonObj = MakeShared<FJsonObject>();
    JsonObj->SetStringField(TEXT("$schema"), TEXT("translators-answer-v1"));
    JsonObj->SetStringField(TEXT("type"), TEXT("ack"));
    JsonObj->SetStringField(TEXT("timestamp"), FDateTime::UtcNow().ToIso8601());

    TSharedPtr<FJsonObject> AckObj = MakeShared<FJsonObject>();
    AckObj->SetBoolField(TEXT("ready"), true);
    AckObj->SetStringField(TEXT("ue_version"), TEXT("5.7.2"));
    AckObj->SetStringField(TEXT("project"), TEXT("TranslatorsCard"));
    JsonObj->SetObjectField(TEXT("ack"), AckObj);

    WriteJsonToFile(TEXT("answer.json"), JsonObj);
    BridgeLog(TEXT("Sent acknowledgment to Claude Code"));
}


void UBridgeComponent::SendAnswer(const FString& QuestionId, int32 OptionIndex, float ResponseTimeMs)
{
    TSharedPtr<FJsonObject> JsonObj = MakeShared<FJsonObject>();
    JsonObj->SetStringField(TEXT("$schema"), TEXT("translators-answer-v1"));
    JsonObj->SetStringField(TEXT("type"), TEXT("answer"));
    JsonObj->SetStringField(TEXT("timestamp"), FDateTime::UtcNow().ToIso8601());

    TSharedPtr<FJsonObject> AnswerObj = MakeShared<FJsonObject>();
    AnswerObj->SetStringField(TEXT("question_id"), QuestionId);
    AnswerObj->SetNumberField(TEXT("option_index"), OptionIndex);
    AnswerObj->SetNumberField(TEXT("response_time_ms"), ResponseTimeMs);
    JsonObj->SetObjectField(TEXT("answer"), AnswerObj);

    WriteJsonToFile(TEXT("answer.json"), JsonObj);

    BridgeLog(FString::Printf(TEXT("Sent answer: %s = option %d (%.0fms)"),
        *QuestionId, OptionIndex, ResponseTimeMs));
}


FTranslatorsQuestion UBridgeComponent::GetCurrentQuestion() const
{
    return CurrentQuestion;
}


// === UTILITY ===

void UBridgeComponent::WriteJsonToFile(const FString& Filename, const TSharedPtr<FJsonObject>& JsonObj)
{
    FString FilePath = GetBridgeFilePath(Filename);
    FString OutputString;

    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    FJsonSerializer::Serialize(JsonObj.ToSharedRef(), Writer);

    // Write with retry logic (file may be locked by Claude Code reading it)
    int32 MaxRetries = 3;
    for (int32 Retry = 0; Retry < MaxRetries; ++Retry)
    {
        if (FFileHelper::SaveStringToFile(OutputString, *FilePath))
        {
            return; // Success
        }

        if (Retry < MaxRetries - 1)
        {
            BridgeLog(FString::Printf(TEXT("Write failed, retry %d/%d..."), Retry + 1, MaxRetries));
            FPlatformProcess::Sleep(0.1f);
        }
    }

    BridgeLog(FString::Printf(TEXT("ERROR: Failed to write %s after %d retries"), *Filename, MaxRetries));
}


FString UBridgeComponent::GetBridgeFilePath(const FString& Filename) const
{
    return FPaths::Combine(BridgePath, Filename);
}


void UBridgeComponent::BridgeLog(const FString& Message) const
{
    UE_LOG(LogTemp, Log, TEXT("[TranslatorsBridge] %s"), *Message);

    // Also log to console for Blueprint visibility
    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(-1, 5.0f, FColor::Cyan,
            FString::Printf(TEXT("[Bridge] %s"), *Message));
    }
}


// === USD NATIVE COMMUNICATION (v2.0.0) ===

bool UBridgeComponent::ProcessBridgeStateUsda()
{
    FString FilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
    FString Content;

    if (!FFileHelper::LoadFileToString(Content, *FilePath))
    {
        return false;
    }

    // Parse sync_status variant
    FString SyncStatus = ParseUsdaVariant(Content, TEXT("sync_status"));
    FString MessageType = ParseUsdaVariant(Content, TEXT("message_type"));

    if (bVerboseLogging)
    {
        BridgeLog(FString::Printf(TEXT("USD sync_status=%s, message_type=%s"), *SyncStatus, *MessageType));
    }

    // Route based on message type
    if (MessageType == TEXT("ready"))
    {
        HandleUsdaReadyState(Content);
    }
    else if (MessageType == TEXT("question") && SyncStatus == TEXT("question_pending"))
    {
        HandleUsdaQuestionState(Content);
    }
    else if (MessageType == TEXT("transition"))
    {
        HandleUsdaTransitionState(Content);
    }
    else if (MessageType == TEXT("finale"))
    {
        HandleUsdaFinaleState(Content);
    }

    return true;
}


FString UBridgeComponent::ParseUsdaVariant(const FString& Content, const FString& VariantSetName)
{
    // Parse variant selection from: variants = { string variantName = "value" }
    FString Pattern = FString::Printf(TEXT("string %s = \"([^\"]*)\""), *VariantSetName);
    FRegexPattern RegexPattern(Pattern);
    FRegexMatcher Matcher(RegexPattern, Content);

    if (Matcher.FindNext())
    {
        return Matcher.GetCaptureGroup(1);
    }
    return TEXT("");
}


FString UBridgeComponent::ParseUsdaAttribute(const FString& Content, const FString& PrimPath, const FString& AttrName)
{
    // Find the prim section and extract attribute value
    // This is a simplified parser - handles basic string/int/float attributes

    // First find the prim section
    FString PrimPattern = FString::Printf(TEXT("def [^\"]*\"%s\"[^{]*\\{([^}]*)\\}"), *PrimPath);
    FRegexPattern PrimRegex(PrimPattern);
    FRegexMatcher PrimMatcher(PrimRegex, Content);

    FString PrimContent;
    if (PrimMatcher.FindNext())
    {
        PrimContent = PrimMatcher.GetCaptureGroup(1);
    }
    else
    {
        // Try finding nested prim
        PrimContent = Content;
    }

    // Parse string attribute
    FString StringPattern = FString::Printf(TEXT("string %s = \"([^\"]*)\""), *AttrName);
    FRegexPattern StringRegex(StringPattern);
    FRegexMatcher StringMatcher(StringRegex, PrimContent);
    if (StringMatcher.FindNext())
    {
        return StringMatcher.GetCaptureGroup(1);
    }

    // Parse int attribute
    FString IntPattern = FString::Printf(TEXT("int %s = (-?\\d+)"), *AttrName);
    FRegexPattern IntRegex(IntPattern);
    FRegexMatcher IntMatcher(IntRegex, PrimContent);
    if (IntMatcher.FindNext())
    {
        return IntMatcher.GetCaptureGroup(1);
    }

    // Parse float/double attribute
    FString FloatPattern = FString::Printf(TEXT("(?:float|double) %s = ([\\d.]+)"), *AttrName);
    FRegexPattern FloatRegex(FloatPattern);
    FRegexMatcher FloatMatcher(FloatRegex, PrimContent);
    if (FloatMatcher.FindNext())
    {
        return FloatMatcher.GetCaptureGroup(1);
    }

    return TEXT("");
}


void UBridgeComponent::HandleUsdaReadyState(const FString& Content)
{
    int32 TotalQuestions = FCString::Atoi(*ParseUsdaAttribute(Content, TEXT("Ready"), TEXT("total_questions")));
    FString FirstScene = ParseUsdaAttribute(Content, TEXT("Ready"), TEXT("first_scene"));

    if (TotalQuestions <= 0) TotalQuestions = 8;

    BridgeLog(FString::Printf(TEXT("USD Ready: %d questions, first scene: %s"), TotalQuestions, *FirstScene));

    bIsConnected = true;
    bUsingUsdMode = true;
    OnBridgeReady.Broadcast(TotalQuestions);
}


void UBridgeComponent::HandleUsdaQuestionState(const FString& Content)
{
    // Parse Message prim
    CurrentQuestion = FTranslatorsQuestion();
    CurrentQuestion.Index = FCString::Atoi(*ParseUsdaAttribute(Content, TEXT("Message"), TEXT("index")));
    CurrentQuestion.Total = FCString::Atoi(*ParseUsdaAttribute(Content, TEXT("Message"), TEXT("total")));
    CurrentQuestion.QuestionId = ParseUsdaAttribute(Content, TEXT("Message"), TEXT("question_id"));
    CurrentQuestion.Text = ParseUsdaAttribute(Content, TEXT("Message"), TEXT("text"));
    CurrentQuestion.Scene = ParseUsdaAttribute(Content, TEXT("Message"), TEXT("scene"));

    // Parse Options
    for (int32 i = 0; i < 3; ++i)
    {
        FString OptionPrim = FString::Printf(TEXT("Option_%d"), i);
        FString Label = ParseUsdaAttribute(Content, OptionPrim, TEXT("label"));
        FString Direction = ParseUsdaAttribute(Content, OptionPrim, TEXT("direction"));

        if (!Label.IsEmpty())
        {
            CurrentQuestion.OptionLabels.Add(Label);
            CurrentQuestion.OptionDirections.Add(Direction);
        }
    }

    // Assign depth label based on question index
    CurrentQuestion.DepthLabel = GetDepthLabelForIndex(CurrentQuestion.Index);

    BridgeLog(FString::Printf(TEXT("USD Question %d/%d [%s]: %s"),
        CurrentQuestion.Index + 1, CurrentQuestion.Total, *CurrentQuestion.DepthLabel, *CurrentQuestion.QuestionId));

    // Build JSON for backward-compatible delegate
    CurrentStateJson = BuildQuestionJson();
    OnQuestionReceived.Broadcast(CurrentStateJson);
}


void UBridgeComponent::HandleUsdaTransitionState(const FString& Content)
{
    FString Direction = ParseUsdaAttribute(Content, TEXT("Transition"), TEXT("direction"));
    FString NextScene = ParseUsdaAttribute(Content, TEXT("Transition"), TEXT("next_scene"));
    float Progress = FCString::Atof(*ParseUsdaAttribute(Content, TEXT("Transition"), TEXT("progress")));

    BridgeLog(FString::Printf(TEXT("USD Transition: %s -> %s (%.0f%%)"),
        *Direction, *NextScene, Progress * 100.0f));

    OnTransitionReceived.Broadcast(Direction, NextScene);
}


void UBridgeComponent::HandleUsdaFinaleState(const FString& Content)
{
    FString UsdPath = ParseUsdaAttribute(Content, TEXT("Finale"), TEXT("usd_path"));
    FString Message = ParseUsdaAttribute(Content, TEXT("Finale"), TEXT("message"));
    FString Checksum = ParseUsdaAttribute(Content, TEXT("Finale"), TEXT("checksum"));

    BridgeLog(FString::Printf(TEXT("USD FINALE: %s (checksum: %s)"), *Message, *Checksum));
    BridgeLog(FString::Printf(TEXT("Profile path: %s"), *UsdPath));

    OnFinaleReceived.Broadcast(UsdPath);
}


FString UBridgeComponent::BuildQuestionJson()
{
    // Build JSON representation for backward-compatible delegates
    TSharedPtr<FJsonObject> JsonObj = MakeShared<FJsonObject>();
    JsonObj->SetStringField(TEXT("type"), TEXT("question"));
    JsonObj->SetNumberField(TEXT("index"), CurrentQuestion.Index);
    JsonObj->SetNumberField(TEXT("total"), CurrentQuestion.Total);
    JsonObj->SetStringField(TEXT("id"), CurrentQuestion.QuestionId);
    JsonObj->SetStringField(TEXT("text"), CurrentQuestion.Text);
    JsonObj->SetStringField(TEXT("scene"), CurrentQuestion.Scene);

    TArray<TSharedPtr<FJsonValue>> OptionsArray;
    for (int32 i = 0; i < CurrentQuestion.OptionLabels.Num(); ++i)
    {
        TSharedPtr<FJsonObject> OptionObj = MakeShared<FJsonObject>();
        OptionObj->SetNumberField(TEXT("index"), i);
        OptionObj->SetStringField(TEXT("label"), CurrentQuestion.OptionLabels[i]);
        OptionObj->SetStringField(TEXT("direction"), CurrentQuestion.OptionDirections[i]);
        OptionsArray.Add(MakeShared<FJsonValueObject>(OptionObj));
    }
    JsonObj->SetArrayField(TEXT("options"), OptionsArray);

    FString OutputString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    FJsonSerializer::Serialize(JsonObj.ToSharedRef(), Writer);
    return OutputString;
}


void UBridgeComponent::SendAnswerUsda(const FString& QuestionId, int32 OptionIndex, float ResponseTimeMs)
{
    FString FilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
    FString Content;

    if (!FFileHelper::LoadFileToString(Content, *FilePath))
    {
        BridgeLog(TEXT("ERROR: Could not read bridge_state.usda for answer"));
        // Fall back to JSON
        SendAnswer(QuestionId, OptionIndex, ResponseTimeMs);
        return;
    }

    FString Timestamp = FDateTime::UtcNow().ToIso8601();
    FString SelectedLabel = (OptionIndex >= 0 && OptionIndex < CurrentQuestion.OptionLabels.Num())
        ? CurrentQuestion.OptionLabels[OptionIndex] : TEXT("");
    FString SelectedDirection = (OptionIndex >= 0 && OptionIndex < CurrentQuestion.OptionDirections.Num())
        ? CurrentQuestion.OptionDirections[OptionIndex] : TEXT("");

    // Update sync_status variant to "answer_received"
    Content = UpdateUsdaVariant(Content, TEXT("sync_status"), TEXT("answer_received"));
    Content = UpdateUsdaVariant(Content, TEXT("message_type"), TEXT("answer"));

    // Update Answer prim attributes
    Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("question_id"), QuestionId, true);
    Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("option_index"), FString::FromInt(OptionIndex), false);
    Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("response_time_ms"), FString::SanitizeFloat(ResponseTimeMs), false);
    Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("selected_label"), SelectedLabel, true);
    Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("selected_direction"), SelectedDirection, true);
    Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("timestamp"), Timestamp, true);

    // Update behavioral signals
    UpdateBehavioralSignals(Content, ResponseTimeMs);

    // Write back
    int32 MaxRetries = 3;
    for (int32 Retry = 0; Retry < MaxRetries; ++Retry)
    {
        if (FFileHelper::SaveStringToFile(Content, *FilePath))
        {
            BridgeLog(FString::Printf(TEXT("USD answer sent: %s = option %d (%.0fms)"),
                *QuestionId, OptionIndex, ResponseTimeMs));
            return;
        }
        FPlatformProcess::Sleep(0.1f);
    }

    BridgeLog(TEXT("ERROR: Failed to write USD answer, falling back to JSON"));
    SendAnswer(QuestionId, OptionIndex, ResponseTimeMs);
}


FString UBridgeComponent::UpdateUsdaVariant(const FString& Content, const FString& VariantSetName, const FString& NewValue)
{
    // Simple string replacement for variant - more reliable than regex
    FString SearchPattern = FString::Printf(TEXT("string %s = \""), *VariantSetName);
    int32 StartIdx = Content.Find(SearchPattern);
    if (StartIdx == INDEX_NONE)
    {
        return Content;
    }

    StartIdx += SearchPattern.Len();
    int32 EndIdx = Content.Find(TEXT("\""), ESearchCase::CaseSensitive, ESearchDir::FromStart, StartIdx);
    if (EndIdx == INDEX_NONE)
    {
        return Content;
    }

    // Build new content
    FString Result = Content.Left(StartIdx) + NewValue + Content.Mid(EndIdx);
    return Result;
}


FString UBridgeComponent::UpdateUsdaAttribute(const FString& Content, const FString& PrimName, const FString& AttrName, const FString& NewValue, bool bIsString)
{
    // Find attribute pattern and replace value
    // For string: string attrName = "value"
    // For numeric: int/float/double attrName = value

    FString Result = Content;

    if (bIsString)
    {
        // Find: string attrName = "..."
        FString SearchPattern = FString::Printf(TEXT("string %s = \""), *AttrName);
        int32 StartIdx = Result.Find(SearchPattern);
        if (StartIdx != INDEX_NONE)
        {
            StartIdx += SearchPattern.Len();
            int32 EndIdx = Result.Find(TEXT("\""), ESearchCase::CaseSensitive, ESearchDir::FromStart, StartIdx);
            if (EndIdx != INDEX_NONE)
            {
                FString EscapedValue = NewValue.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("\""), TEXT("\\\""));
                Result = Result.Left(StartIdx) + EscapedValue + Result.Mid(EndIdx);
            }
        }
    }
    else
    {
        // Find numeric attributes: int/float/double attrName = value
        TArray<FString> TypePrefixes = { TEXT("int"), TEXT("float"), TEXT("double"), TEXT("bool") };

        for (const FString& TypePrefix : TypePrefixes)
        {
            FString SearchPattern = FString::Printf(TEXT("%s %s = "), *TypePrefix, *AttrName);
            int32 StartIdx = Result.Find(SearchPattern);
            if (StartIdx != INDEX_NONE)
            {
                StartIdx += SearchPattern.Len();
                // Find end of value (newline or space or semicolon)
                int32 EndIdx = StartIdx;
                while (EndIdx < Result.Len())
                {
                    TCHAR C = Result[EndIdx];
                    if (C == '\n' || C == '\r' || C == ';' || C == ' ' || C == '\t')
                    {
                        break;
                    }
                    EndIdx++;
                }
                Result = Result.Left(StartIdx) + NewValue + Result.Mid(EndIdx);
                break;
            }
        }
    }

    return Result;
}


void UBridgeComponent::UpdateBehavioralSignals(FString& Content, float ResponseTimeMs)
{
    // ═══════════════════════════════════════════════════════════════════════════════
    // THINKINGMACHINES [He2025] BATCH-INVARIANCE COMPLIANT
    // Same signals → Same routing → Same behavior
    // FIXED thresholds ensure deterministic expert selection regardless of load
    // ═══════════════════════════════════════════════════════════════════════════════

    // PHASE 1: DETECT - Collect signals
    ResponseTimes.Add(ResponseTimeMs);

    // Calculate average response time (FIXED algorithm - sum/count)
    float TotalTime = 0.0f;
    for (float Time : ResponseTimes)
    {
        TotalTime += Time;
    }
    float AvgResponseTime = ResponseTimes.Num() > 0 ? TotalTime / ResponseTimes.Num() : 0.0f;

    // FIXED THRESHOLDS (batch-invariant - same across all sessions)
    const float HESITATION_THRESHOLD_MS = 10000.0f;   // 10 seconds
    const float RAPID_CLICK_THRESHOLD_MS = 500.0f;    // 0.5 seconds
    const float DEPLETED_AVG_THRESHOLD_MS = 15000.0f; // 15 seconds average
    const int32 HESITATION_COUNT_THRESHOLD = 2;
    const int32 RAPID_CLICK_COUNT_THRESHOLD = 3;

    // Detect hesitation
    bool bLongHesitation = ResponseTimeMs > HESITATION_THRESHOLD_MS;
    if (bLongHesitation)
    {
        HesitationCount++;
    }

    // Detect rapid clicking
    bool bRapidClick = ResponseTimeMs < RAPID_CLICK_THRESHOLD_MS && ResponseTimes.Num() > 1;
    if (bRapidClick)
    {
        RapidClickCount++;
    }

    // PHASE 2: CASCADE - ADHD_MoE FIXED PRIORITY ROUTING
    // Priority: Validator(1) > Scaffolder(2) > Restorer(3) > Refocuser(4) > Celebrator(5) > Socratic(6) > Direct(7)
    // First match wins - NEVER skip or reorder

    FString DetectedState = TEXT("focused");
    FString RecommendedExpert = TEXT("Direct");
    FString BurnoutLevel = TEXT("GREEN");
    FString MomentumPhase = TEXT("rolling");

    // Priority 1: Validator - frustrated, RED burnout, caps, negative signals
    if (RapidClickCount > RAPID_CLICK_COUNT_THRESHOLD)
    {
        DetectedState = TEXT("frustrated");
        RecommendedExpert = TEXT("Validator");
        BurnoutLevel = TEXT("RED");
        MomentumPhase = TEXT("crashed");
    }
    // Priority 2: Scaffolder - overwhelmed, stuck, too_many signals
    else if (bLongHesitation || HesitationCount > HESITATION_COUNT_THRESHOLD)
    {
        DetectedState = TEXT("stuck");
        RecommendedExpert = TEXT("Scaffolder");
        BurnoutLevel = TEXT("ORANGE");
        MomentumPhase = TEXT("declining");
    }
    // Priority 3: Restorer - depleted, ORANGE burnout, post-crash
    else if (AvgResponseTime > DEPLETED_AVG_THRESHOLD_MS)
    {
        DetectedState = TEXT("depleted");
        RecommendedExpert = TEXT("Restorer");
        BurnoutLevel = TEXT("ORANGE");
        MomentumPhase = TEXT("crashed");
    }
    // Priority 4: Refocuser - distracted, tangent signals
    else if (ResponseTimes.Num() > 3 && ResponseTimeMs > AvgResponseTime * 2.0f)
    {
        DetectedState = TEXT("distracted");
        RecommendedExpert = TEXT("Refocuser");
        BurnoutLevel = TEXT("YELLOW");
        MomentumPhase = TEXT("declining");
    }
    // Priority 5: Celebrator - task_complete, milestone reached
    else if (CurrentQuestion.Index == CurrentQuestion.Total - 1)
    {
        DetectedState = TEXT("completing");
        RecommendedExpert = TEXT("Celebrator");
        BurnoutLevel = TEXT("GREEN");
        MomentumPhase = TEXT("peak");
    }
    // Priority 6: Socratic - exploring, high energy, "what if" signals
    else if (ResponseTimes.Num() >= 2 && ResponseTimeMs > 3000.0f && ResponseTimeMs < 8000.0f)
    {
        DetectedState = TEXT("exploring");
        RecommendedExpert = TEXT("Socratic");
        BurnoutLevel = TEXT("GREEN");
        MomentumPhase = TEXT("building");
    }
    // Priority 7: Direct - focused, hyperfocused, flow state (DEFAULT)
    else
    {
        DetectedState = TEXT("focused");
        RecommendedExpert = TEXT("Direct");
        BurnoutLevel = TEXT("GREEN");
        MomentumPhase = (ResponseTimes.Num() > 5) ? TEXT("rolling") : TEXT("building");
    }

    // PHASE 3: LOCK - Parameters locked for this response (no further changes)

    // PHASE 4: EXECUTE - Update signals in USD content
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("last_response_time_ms"), FString::SanitizeFloat(ResponseTimeMs), false);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("average_response_time_ms"), FString::SanitizeFloat(AvgResponseTime), false);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("hesitation_count"), FString::FromInt(HesitationCount), false);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("long_hesitation_detected"), bLongHesitation ? TEXT("true") : TEXT("false"), false);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("rapid_click_count"), FString::FromInt(RapidClickCount), false);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("detected_state"), DetectedState, true);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("recommended_expert"), RecommendedExpert, true);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("burnout_level"), BurnoutLevel, true);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("momentum_phase"), MomentumPhase, true);

    // PHASE 5: UPDATE - Log routing decision for traceability
    if (bVerboseLogging)
    {
        BridgeLog(FString::Printf(TEXT("[EXEC] State=%s Expert=%s Burnout=%s Momentum=%s"),
            *DetectedState, *RecommendedExpert, *BurnoutLevel, *MomentumPhase));
    }
}


void UBridgeComponent::SendAcknowledgeUsda()
{
    FString FilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
    FString Content;

    if (!FFileHelper::LoadFileToString(Content, *FilePath))
    {
        BridgeLog(TEXT("USD ack: bridge_state.usda not found, sending JSON ack"));
        SendAcknowledge();
        return;
    }

    FString Timestamp = FDateTime::UtcNow().ToIso8601();

    // Update message_type to "ack"
    Content = UpdateUsdaVariant(Content, TEXT("message_type"), TEXT("ack"));

    // Update Ack prim
    Content = UpdateUsdaAttribute(Content, TEXT("Ack"), TEXT("ready"), TEXT("true"), false);
    Content = UpdateUsdaAttribute(Content, TEXT("Ack"), TEXT("ue_version"), TEXT("5.7.2"), true);
    Content = UpdateUsdaAttribute(Content, TEXT("Ack"), TEXT("project"), TEXT("TranslatorsCard"), true);
    Content = UpdateUsdaAttribute(Content, TEXT("Ack"), TEXT("timestamp"), Timestamp, true);

    if (FFileHelper::SaveStringToFile(Content, *FilePath))
    {
        BridgeLog(TEXT("USD acknowledgment sent"));
        bUsingUsdMode = true;
    }
    else
    {
        BridgeLog(TEXT("USD ack failed, sending JSON"));
        SendAcknowledge();
    }
}


// === DEPTH LABELS ===

FString UBridgeComponent::GetDepthLabelForIndex(int32 Index)
{
    // Q1-Q2: SURFACE, Q3-Q4: PATTERNS, Q5-Q6: FEELINGS, Q7-Q8: CORE
    switch (Index / 2)
    {
    case 0: return TEXT("SURFACE");
    case 1: return TEXT("PATTERNS");
    case 2: return TEXT("FEELINGS");
    case 3: return TEXT("CORE");
    default: return TEXT("CORE");
    }
}


// === COGNITIVE PROFILE PARSING ===

FTranslatorsProfile UBridgeComponent::ParseCognitiveProfile(const FString& UsdPath)
{
    FTranslatorsProfile Profile;

    FString Content;
    if (!FFileHelper::LoadFileToString(Content, *UsdPath))
    {
        BridgeLog(FString::Printf(TEXT("Could not read profile: %s"), *UsdPath));
        return Profile;
    }

    BridgeLog(FString::Printf(TEXT("Parsing cognitive profile from: %s"), *UsdPath));

    // Parse checksum
    {
        FRegexPattern Pattern(TEXT("string checksum = \"([^\"]*)\""));
        FRegexMatcher Matcher(Pattern, Content);
        if (Matcher.FindNext())
        {
            Profile.Checksum = Matcher.GetCaptureGroup(1);
        }
    }

    // Parse anchor
    {
        FRegexPattern Pattern(TEXT("string anchor = \"([^\"]*)\""));
        FRegexMatcher Matcher(Pattern, Content);
        if (Matcher.FindNext())
        {
            Profile.Anchor = Matcher.GetCaptureGroup(1);
        }
    }

    // Parse anchor from customData
    {
        FRegexPattern Pattern(TEXT("string translators_anchor = \"([^\"]*)\""));
        FRegexMatcher Matcher(Pattern, Content);
        if (Matcher.FindNext())
        {
            Profile.Anchor = Matcher.GetCaptureGroup(1);
        }
    }

    // Parse Profile dimensions (float cognitive_density = 0.5)
    // and Traits labels (string load = "adaptive")
    // Combine them into FTranslatorsTrait entries
    TMap<FString, float> DimensionScores;
    TMap<FString, FString> TraitLabels;

    // Extract Profile section: float <name> = <value>
    {
        int32 ProfileStart = Content.Find(TEXT("def Xform \"Profile\""));
        if (ProfileStart != INDEX_NONE)
        {
            int32 BlockStart = Content.Find(TEXT("{"), ESearchCase::CaseSensitive, ESearchDir::FromStart, ProfileStart);
            if (BlockStart != INDEX_NONE)
            {
                int32 BraceDepth = 1;
                int32 BlockEnd = BlockStart + 1;
                while (BlockEnd < Content.Len() && BraceDepth > 0)
                {
                    if (Content[BlockEnd] == TEXT('{')) BraceDepth++;
                    else if (Content[BlockEnd] == TEXT('}')) BraceDepth--;
                    BlockEnd++;
                }

                FString ProfileBlock = Content.Mid(BlockStart, BlockEnd - BlockStart);
                FRegexPattern Pattern(TEXT("float (\\w+) = ([\\d.]+)"));
                FRegexMatcher Matcher(Pattern, ProfileBlock);
                while (Matcher.FindNext())
                {
                    FString Name = Matcher.GetCaptureGroup(1);
                    float Value = FCString::Atof(*Matcher.GetCaptureGroup(2));
                    DimensionScores.Add(Name, Value);
                }
            }
        }
    }

    // Extract Traits section: string <question_id> = "<trait_label>"
    // These are inside def Xform "Traits" { ... }
    {
        // Find the Traits block
        int32 TraitsStart = Content.Find(TEXT("def Xform \"Traits\""));
        if (TraitsStart != INDEX_NONE)
        {
            // Find the closing brace for this block
            int32 BlockStart = Content.Find(TEXT("{"), ESearchCase::CaseSensitive, ESearchDir::FromStart, TraitsStart);
            if (BlockStart != INDEX_NONE)
            {
                int32 BraceDepth = 1;
                int32 BlockEnd = BlockStart + 1;
                while (BlockEnd < Content.Len() && BraceDepth > 0)
                {
                    if (Content[BlockEnd] == TEXT('{')) BraceDepth++;
                    else if (Content[BlockEnd] == TEXT('}')) BraceDepth--;
                    BlockEnd++;
                }

                FString TraitsBlock = Content.Mid(BlockStart, BlockEnd - BlockStart);
                FRegexPattern Pattern(TEXT("string (\\w+) = \"([^\"]*)\""));
                FRegexMatcher Matcher(Pattern, TraitsBlock);
                while (Matcher.FindNext())
                {
                    TraitLabels.Add(Matcher.GetCaptureGroup(1), Matcher.GetCaptureGroup(2));
                }
            }
        }
    }

    // Map between question IDs and dimension names
    // Question IDs: load, pace, uncertainty, feedback, recovery, starting, completion, essence
    // Dimension names: cognitive_density, processing_pace, uncertainty_tolerance, feedback_style,
    //                  home_altitude, guidance_frequency, default_paradigm, tangent_tolerance
    TMap<FString, FString> QuestionToDimension;
    QuestionToDimension.Add(TEXT("load"), TEXT("cognitive_density"));
    QuestionToDimension.Add(TEXT("pace"), TEXT("processing_pace"));
    QuestionToDimension.Add(TEXT("uncertainty"), TEXT("uncertainty_tolerance"));
    QuestionToDimension.Add(TEXT("feedback"), TEXT("feedback_style"));
    QuestionToDimension.Add(TEXT("recovery"), TEXT("home_altitude"));
    QuestionToDimension.Add(TEXT("starting"), TEXT("guidance_frequency"));
    QuestionToDimension.Add(TEXT("completion"), TEXT("default_paradigm"));
    QuestionToDimension.Add(TEXT("essence"), TEXT("tangent_tolerance"));

    // Build traits from combined data
    for (const auto& Pair : TraitLabels)
    {
        FTranslatorsTrait Trait;
        Trait.Label = Pair.Value;

        // Find matching dimension
        FString* DimName = QuestionToDimension.Find(Pair.Key);
        if (DimName)
        {
            Trait.Dimension = *DimName;
            float* Score = DimensionScores.Find(*DimName);
            Trait.Score = Score ? *Score : 0.5f;
        }
        else
        {
            Trait.Dimension = Pair.Key;
            Trait.Score = 0.5f;
        }

        // Generate behavior description from score
        if (Trait.Score >= 0.7f)
        {
            Trait.Behavior = FString::Printf(TEXT("Strong %s tendency"), *Trait.Label);
        }
        else if (Trait.Score <= 0.3f)
        {
            Trait.Behavior = FString::Printf(TEXT("Measured %s approach"), *Trait.Label);
        }
        else
        {
            Trait.Behavior = FString::Printf(TEXT("Balanced %s style"), *Trait.Label);
        }

        Profile.Traits.Add(Trait);
    }

    // Generate insights from the profile data
    // (The USDA doesn't contain explicit insights, so derive them from scores)
    for (const FTranslatorsTrait& Trait : Profile.Traits)
    {
        if (Trait.Score >= 0.7f)
        {
            Profile.Insights.Add(FString::Printf(TEXT("High %s (%s) suggests strong preference in this dimension"),
                *Trait.Dimension.Replace(TEXT("_"), TEXT(" ")), *Trait.Label));
        }
        else if (Trait.Score <= 0.3f)
        {
            Profile.Insights.Add(FString::Printf(TEXT("Low %s (%s) indicates a focused approach here"),
                *Trait.Dimension.Replace(TEXT("_"), TEXT(" ")), *Trait.Label));
        }
    }

    BridgeLog(FString::Printf(TEXT("Parsed profile: %d traits, %d insights, checksum=%s"),
        Profile.Traits.Num(), Profile.Insights.Num(), *Profile.Checksum));

    return Profile;
}
