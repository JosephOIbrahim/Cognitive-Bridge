// BridgeComponent.h
// Claude Code <-> UE5 File-Based Bridge
// Part of "The Translators" cognitive profiling game
//
// This component watches ~/.translators/ for file changes and handles:
// - bridge_state.usda: USD-native communication (v2.0.0)
// - state.json / answer.json: JSON fallback (v1.0.0)
// - cognitive_profile.usda: Exported cognitive profile
//
// Data types (structs, enums, delegates) live in BridgeTypes.h
// and are shared between Runtime and Editor modules.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Dom/JsonObject.h"

// Shared types from the TranslatorsBridge plugin
// During migration: types are defined in both BridgeTypes.h (plugin) and here (legacy).
// Once the C++ module rename is complete, only BridgeTypes.h will be canonical.
// For now, we keep the original definitions below for compilation compatibility.

#include "BridgeComponent.generated.h"

// DirectoryWatcher is now editor-only (BridgeEditorSubsystem).
// This runtime component uses polling for file change detection.

// ============================================================================
// Legacy delegates (v1.0.0 — raw JSON payloads)
// These will be replaced by typed delegates from BridgeTypes.h in Phase 4.
// ============================================================================

// Delegate for question received from Claude Code (raw JSON)
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnQuestionReceived, const FString&, QuestionJson);

// Delegate for transition command
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnTransitionReceived, const FString&, Direction, const FString&, NextScene);

// Delegate for finale
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnFinaleReceived, const FString&, UsdPath);

// Delegate for USD file update
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnUsdUpdated);

// Delegate for ready state
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBridgeReady, int32, TotalQuestions);

// ============================================================================
// Data types — will migrate to BridgeTypes.h in Phase 4 (subsystem creation)
// ============================================================================

/** Structured question data for Blueprints */
USTRUCT(BlueprintType)
struct FTranslatorsQuestion
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "0-based question index"))
    int32 Index = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Total questions in the set"))
    int32 Total = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Unique question ID"))
    FString QuestionId;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Question display text"))
    FString Text;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Scene identifier"))
    FString Scene;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Answer option display labels"))
    TArray<FString> OptionLabels;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Option direction values"))
    TArray<FString> OptionDirections;

    /** Depth tier label: SURFACE, PATTERNS, FEELINGS, CORE */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Depth tier label"))
    FString DepthLabel;

    bool IsValid() const { return Total > 0 && !QuestionId.IsEmpty(); }
};


/** Cognitive profile trait (from profile USDA) */
USTRUCT(BlueprintType)
struct FTranslatorsTrait
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Dimension identifier"))
    FString Dimension;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Human-readable label"))
    FString Label;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Normalized score 0.0 - 1.0"))
    float Score = 0.0f;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Behavioral description"))
    FString Behavior;
};


/** Full cognitive profile result */
USTRUCT(BlueprintType)
struct FTranslatorsProfile
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    TArray<FTranslatorsTrait> Traits;

    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    TArray<FString> Insights;

    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString Checksum;

    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString Anchor;

    bool IsValid() const { return Traits.Num() > 0; }
};


// ============================================================================
// Component
// ============================================================================

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent, DisplayName="Translators Bridge", ToolTip="File-based bridge between UE5 and the Python cognitive profiling orchestrator"))
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
    UPROPERTY(BlueprintAssignable, Category = "Translators Bridge", meta = (ToolTip = "Fires when a new question arrives"))
    FOnQuestionReceived OnQuestionReceived;

    /** Fired when Claude Code sends transition command */
    UPROPERTY(BlueprintAssignable, Category = "Translators Bridge", meta = (ToolTip = "Fires on scene transitions"))
    FOnTransitionReceived OnTransitionReceived;

    /** Fired when questionnaire completes */
    UPROPERTY(BlueprintAssignable, Category = "Translators Bridge", meta = (ToolTip = "Fires when profile is complete"))
    FOnFinaleReceived OnFinaleReceived;

    /** Fired when cognitive_substrate.usda updates */
    UPROPERTY(BlueprintAssignable, Category = "Translators Bridge", meta = (ToolTip = "Fires when USD profile file changes"))
    FOnUsdUpdated OnUsdUpdated;

    /** Fired when Claude Code is ready to start */
    UPROPERTY(BlueprintAssignable, Category = "Translators Bridge", meta = (ToolTip = "Fires when Python bridge connects"))
    FOnBridgeReady OnBridgeReady;

    // === BLUEPRINT CALLABLE FUNCTIONS ===

    /** Send acknowledgment that UE5 is ready (JSON mode) */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge", meta = (ToolTip = "Send JSON acknowledgment to Python bridge", DeprecatedFunction, DeprecationMessage = "Use SendAcknowledgeUsda for USD mode (v2.0.0)"))
    void SendAcknowledge();

    /** Send user's answer to Claude Code (JSON mode) */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge", meta = (ToolTip = "Send answer via JSON", DeprecatedFunction, DeprecationMessage = "Use SendAnswerUsda for USD mode (v2.0.0)"))
    void SendAnswer(const FString& QuestionId, int32 OptionIndex, float ResponseTimeMs);

    /** Parse current question into structured data */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge", meta = (ToolTip = "Get the currently active question"))
    FTranslatorsQuestion GetCurrentQuestion() const;

    /** Force reload the USD stage (use if auto-detection fails) */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge", meta = (ToolTip = "Force USD Stage Actor to reload"))
    void ForceReloadUsdStage();

    /** Parse cognitive profile from exported USDA file */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge", meta = (ToolTip = "Parse a cognitive profile from a .usda file"))
    FTranslatorsProfile ParseCognitiveProfile(const FString& UsdPath);

    /** Check if bridge is connected */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "Translators Bridge", meta = (ToolTip = "True if Python bridge is connected"))
    bool IsBridgeConnected() const { return bIsConnected; }

    /** Check if using USD mode (v2.0.0) */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "Translators Bridge", meta = (ToolTip = "True if using USD-native transport"))
    bool IsUsingUsdMode() const { return bUsingUsdMode; }

    /** Send acknowledgment via USD (v2.0.0) */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge", meta = (ToolTip = "Send USD acknowledgment to Python bridge"))
    void SendAcknowledgeUsda();

    /** Send answer via USD (v2.0.0) */
    UFUNCTION(BlueprintCallable, Category = "Translators Bridge", meta = (ToolTip = "Send answer via USD-native transport"))
    void SendAnswerUsda(const FString& QuestionId, int32 OptionIndex, float ResponseTimeMs);

    // === CONFIGURATION ===

    /** Bridge directory path (default: ~/.translators) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Translators Bridge", meta = (ToolTip = "Path to the bridge exchange directory"))
    FString BridgePath;

    /** Enable verbose logging */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Translators Bridge", meta = (ToolTip = "Show detailed bridge logs on screen"))
    bool bVerboseLogging = false;

    /** Debounce time in seconds for file change detection */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Translators Bridge", meta = (ToolTip = "Debounce window for file watcher events", ClampMin = "0.01", ClampMax = "1.0"))
    float DebounceTime = 0.05f;

private:
    // === FILE WATCHING ===

    void SetupFileWatcher();
    void TeardownFileWatcher();

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

    /** Assign depth label based on question index (0-based) */
    static FString GetDepthLabelForIndex(int32 Index);

    void WriteJsonToFile(const FString& Filename, const TSharedPtr<FJsonObject>& JsonObj);
    FString GetBridgeFilePath(const FString& Filename) const;
    void BridgeLog(const FString& Message) const;

    // === STATE ===

    bool bIsConnected = false;
    bool bUsePolling = false;
    bool bUsingUsdMode = false;

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

    // === BEHAVIORAL SIGNALS (ADHD_MoE routing) ===

    TArray<float> ResponseTimes;
    int32 HesitationCount = 0;
    int32 RapidClickCount = 0;
};
