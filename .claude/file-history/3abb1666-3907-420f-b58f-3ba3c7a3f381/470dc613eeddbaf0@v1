// BridgeComponent.h
// Claude Code → UE5.7 File-Based Bridge
// Part of "The Translators" cognitive profiling game
//
// This component watches ~/.translators/ for file changes and handles:
// - state.json: Questions from Claude Code
// - answer.json: User responses back to Claude
// - cognitive_substrate.usda: USD cognitive profile
//
// CRITICAL: USD Stage Actor does NOT auto-reload files.
// We must trigger SetRootLayer() manually on file change.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Dom/JsonObject.h"
#include "BridgeComponent.generated.h"

// Forward declare for editor-only directory watcher
#if WITH_DIRECTORY_WATCHER
struct FFileChangeData;
#endif

// Note: USD Stage Actor integration is handled via Blueprint
// The OnUsdUpdated delegate notifies when cognitive_substrate.usda changes

// Delegate for question received from Claude Code
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnQuestionReceived, const FString&, QuestionJson);

// Delegate for transition command
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnTransitionReceived, const FString&, Direction, const FString&, NextScene);

// Delegate for finale
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnFinaleReceived, const FString&, UsdPath);

// Delegate for USD file update
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnUsdUpdated);

// Delegate for ready state
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBridgeReady, int32, TotalQuestions);

// Structured question data for Blueprints
USTRUCT(BlueprintType)
struct FTranslatorsQuestion
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly)
    int32 Index = 0;

    UPROPERTY(BlueprintReadOnly)
    int32 Total = 0;

    UPROPERTY(BlueprintReadOnly)
    FString QuestionId;

    UPROPERTY(BlueprintReadOnly)
    FString Text;

    UPROPERTY(BlueprintReadOnly)
    FString Scene;

    UPROPERTY(BlueprintReadOnly)
    TArray<FString> OptionLabels;

    UPROPERTY(BlueprintReadOnly)
    TArray<FString> OptionDirections;
};


UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class TRANSLATORSCARD_API UBridgeComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UBridgeComponent();

    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

    // === DELEGATES (Bind in Blueprint) ===

    /** Fired when a new question arrives from Claude Code */
    UPROPERTY(BlueprintAssignable, Category = "Translators Bridge")
    FOnQuestionReceived OnQuestionReceived;

    /** Fired when Claude Code sends transition command */
    UPROPERTY(BlueprintAssignable, Category = "Translators Bridge")
    FOnTransitionReceived OnTransitionReceived;

    /** Fired when questionnaire completes */
    UPROPERTY(BlueprintAssignable, Category = "Translators Bridge")
    FOnFinaleReceived OnFinaleReceived;

    /** Fired when cognitive_substrate.usda updates */
    UPROPERTY(BlueprintAssignable, Category = "Translators Bridge")
    FOnUsdUpdated OnUsdUpdated;

    /** Fired when Claude Code is ready to start */
    UPROPERTY(BlueprintAssignable, Category = "Translators Bridge")
    FOnBridgeReady OnBridgeReady;

    // === BLUEPRINT CALLABLE FUNCTIONS ===

    /** Send acknowledgment that UE5 is ready */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge")
    void SendAcknowledge();

    /** Send user's answer to Claude Code */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge")
    void SendAnswer(const FString& QuestionId, int32 OptionIndex, float ResponseTimeMs);

    /** Parse current question into structured data */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge")
    FTranslatorsQuestion GetCurrentQuestion() const;

    /** Force reload the USD stage (use if auto-detection fails) */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge")
    void ForceReloadUsdStage();

    /** Check if bridge is connected */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge")
    bool IsBridgeConnected() const { return bIsConnected; }

    /** Check if using USD mode (v2.0.0) */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge")
    bool IsUsingUsdMode() const { return bUsingUsdMode; }

    /** Send acknowledgment via USD (v2.0.0) */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge")
    void SendAcknowledgeUsda();

    /** Send answer via USD (v2.0.0) */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge")
    void SendAnswerUsda(const FString& QuestionId, int32 OptionIndex, float ResponseTimeMs);

    // === CONFIGURATION ===

    /** Bridge directory path (default: ~/.translators) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Translators Bridge")
    FString BridgePath;

    /** Enable verbose logging */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Translators Bridge")
    bool bVerboseLogging = false;

    /** Debounce time in seconds for file change detection */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Translators Bridge")
    float DebounceTime = 0.05f;

private:
    // === FILE WATCHING ===

    void SetupFileWatcher();
    void TeardownFileWatcher();

#if WITH_DIRECTORY_WATCHER
    void OnDirectoryChanged(const TArray<FFileChangeData>& Changes);
#endif

    // === STATE HANDLING ===

    void ProcessStateFile();
    void HandleReadyState(const TSharedPtr<FJsonObject>& JsonObj);
    void HandleQuestionState(const TSharedPtr<FJsonObject>& JsonObj);
    void HandleTransitionState(const TSharedPtr<FJsonObject>& JsonObj);
    void HandleFinaleState(const TSharedPtr<FJsonObject>& JsonObj);

    // === USD NATIVE COMMUNICATION (v2.0.0) ===

    bool ProcessBridgeStateUsda();
    FString ParseUsdaVariant(const FString& Content, const FString& VariantSetName);
    FString ParseUsdaAttribute(const FString& Content, const FString& PrimPath, const FString& AttrName);
    void HandleUsdaReadyState(const FString& Content);
    void HandleUsdaQuestionState(const FString& Content);
    void HandleUsdaTransitionState(const FString& Content);
    void HandleUsdaFinaleState(const FString& Content);
    FString BuildQuestionJson();
    FString UpdateUsdaVariant(const FString& Content, const FString& VariantSetName, const FString& NewValue);
    FString UpdateUsdaAttribute(const FString& Content, const FString& PrimName, const FString& AttrName, const FString& NewValue, bool bIsString);
    void UpdateBehavioralSignals(FString& Content, float ResponseTimeMs);

    // === USD PROFILE HANDLING ===

    void OnUsdFileChanged();
    void ReloadUsdStage();

    // === UTILITY ===

    void WriteJsonToFile(const FString& Filename, const TSharedPtr<FJsonObject>& JsonObj);
    FString GetBridgeFilePath(const FString& Filename) const;
    void BridgeLog(const FString& Message) const;

    // === STATE ===

#if WITH_DIRECTORY_WATCHER
    FDelegateHandle WatchHandle;
#endif

    bool bIsConnected = false;
    bool bUsePolling = false;
    bool bUsingUsdMode = false;  // v2.0.0: USD-native mode active

    // Debouncing
    float TimeSinceLastStateChange = 0.0f;
    bool bStateChangePending = false;
    float TimeSinceLastUsdChange = 0.0f;
    bool bUsdChangePending = false;

    // Polling (non-editor fallback)
    float PollTimer = 0.0f;
    float PollInterval = 0.5f;
    FDateTime LastStateFileTime;

    // Current state
    FString CurrentStateJson;
    FTranslatorsQuestion CurrentQuestion;

    // === BEHAVIORAL SIGNALS (v2.0.0 ADHD_MoE routing) ===

    TArray<float> ResponseTimes;  // Track response times for pattern detection
    int32 HesitationCount = 0;    // Count of long hesitations (>10s)
    int32 RapidClickCount = 0;    // Count of rapid clicks (<500ms)
    int32 SkipCount = 0;          // Count of skipped questions
    int32 BackNavigationCount = 0; // Count of back navigations
};
