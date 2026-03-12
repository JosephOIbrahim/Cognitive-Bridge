// BridgeTypes.h
// Shared data types and delegates for the Translators Bridge plugin.
// Included by both Runtime and Editor modules.

#pragma once

#include "CoreMinimal.h"
#include "BridgeTypes.generated.h"

// ============================================================================
// Enums
// ============================================================================

/** Bridge state machine states */
UENUM(BlueprintType)
enum class ETranslatorsBridgeState : uint8
{
    /** No file watcher running. StartGame() not called yet. */
    Idle            UMETA(DisplayName = "Idle"),

    /** File watcher running, waiting for Python bridge_orchestrator "ready" message. */
    WaitingForBridge UMETA(DisplayName = "Waiting For Bridge"),

    /** Python sent "ready". UE5 sent acknowledgment. Waiting for first question. */
    Connected       UMETA(DisplayName = "Connected"),

    /** A question is active and awaiting player input. */
    QuestionActive  UMETA(DisplayName = "Question Active"),

    /** Answer submitted. Waiting for next question from Python side. */
    AnswerPending   UMETA(DisplayName = "Answer Pending"),

    /** Scene transition in progress between questions. */
    Transitioning   UMETA(DisplayName = "Transitioning"),

    /** Profile complete and exported to disk. */
    Complete        UMETA(DisplayName = "Complete"),

    /** File I/O error, parse failure, or timeout. */
    Error           UMETA(DisplayName = "Error")
};

/** Error codes for bridge failures */
UENUM(BlueprintType)
enum class EBridgeErrorCode : uint8
{
    None                    UMETA(DisplayName = "None"),
    BridgeDirectoryMissing  UMETA(DisplayName = "Bridge Directory Missing"),
    FileReadFailure         UMETA(DisplayName = "File Read Failure"),
    FileWriteFailure        UMETA(DisplayName = "File Write Failure"),
    JsonParseFailure        UMETA(DisplayName = "JSON Parse Failure"),
    UsdParseFailure         UMETA(DisplayName = "USD Parse Failure"),
    AnswerTimeout           UMETA(DisplayName = "Answer Timeout"),
    ProfileParseFailure     UMETA(DisplayName = "Profile Parse Failure"),
    QuestionIdMismatch      UMETA(DisplayName = "Question ID Mismatch")
};

/** Depth tier for question progression */
UENUM(BlueprintType)
enum class EDepthTier : uint8
{
    Surface     UMETA(DisplayName = "SURFACE"),     // Q1-Q2
    Patterns    UMETA(DisplayName = "PATTERNS"),     // Q3-Q4
    Feelings    UMETA(DisplayName = "FEELINGS"),     // Q5-Q6
    Core        UMETA(DisplayName = "CORE")          // Q7-Q8
};

// ============================================================================
// Structs
// ============================================================================

/** Structured question data from the Python orchestrator */
USTRUCT(BlueprintType)
struct TRANSLATORSBRIDGERUNTIME_API FTranslatorsQuestion
{
    GENERATED_BODY()

    /** 0-based question index */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "0-based question index"))
    int32 Index = 0;

    /** Total number of questions (always 8 in current set) */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Total questions in the set"))
    int32 Total = 0;

    /** Unique question identifier (e.g. "load", "pace", "uncertainty") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Unique question ID"))
    FString QuestionId;

    /** Display text for the question */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Question display text"))
    FString Text;

    /** Scene identifier (e.g. "forest_edge", "mirror_pool") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Scene identifier for visual context"))
    FString Scene;

    /** Display labels for each option (length always 3) */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Answer option display labels"))
    TArray<FString> OptionLabels;

    /** Direction values for each option ("low", "mid", "high") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Option direction values"))
    TArray<FString> OptionDirections;

    /** Human-readable depth label: "SURFACE", "PATTERNS", "FEELINGS", "CORE" */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Depth tier label"))
    FString DepthLabel;

    /** Typed depth tier for Blueprint switch nodes */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Depth tier enum"))
    EDepthTier DepthTier = EDepthTier::Surface;

    /** Cognitive dimension this question maps to */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Cognitive dimension ID"))
    FString DimensionId;

    /** Returns true if this question has been populated */
    bool IsValid() const { return Total > 0 && !QuestionId.IsEmpty(); }
};


/** A submitted player answer */
USTRUCT(BlueprintType)
struct TRANSLATORSBRIDGERUNTIME_API FTranslatorsAnswer
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString QuestionId;

    /** 0-based option index. -1 means skipped. */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    int32 OptionIndex = -1;

    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString SelectedLabel;

    /** "low", "mid", or "high" */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString SelectedDirection;

    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    float ResponseTimeMs = 0.0f;

    /** ISO 8601 timestamp */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString Timestamp;

    bool IsValid() const { return OptionIndex >= 0 && !QuestionId.IsEmpty(); }
};


/** A single cognitive profile trait */
USTRUCT(BlueprintType)
struct TRANSLATORSBRIDGERUNTIME_API FTranslatorsTrait
{
    GENERATED_BODY()

    /** Dimension identifier (e.g. "cognitive_density") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString Dimension;

    /** Human-readable label (e.g. "Balanced") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString Label;

    /** Normalized score 0.0 - 1.0 */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    float Score = 0.0f;

    /** Behavioral description (e.g. "You can hold moderate complexity") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString Behavior;
};


/** Complete cognitive profile result */
USTRUCT(BlueprintType)
struct TRANSLATORSBRIDGERUNTIME_API FTranslatorsProfile
{
    GENERATED_BODY()

    /** One trait per question/dimension */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    TArray<FTranslatorsTrait> Traits;

    /** Generated insights from the profile */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    TArray<FString> Insights;

    /** 8-char hex DJB2 checksum (e.g. "101bfab5") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString Checksum;

    /** Anchor string: "[TRANSLATORS:checksum]" */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString Anchor;

    /** Raw dimension scores keyed by dimension ID */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    TMap<FString, float> Dimensions;

    /** Ordered answer history */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    TArray<FTranslatorsAnswer> Answers;

    /** Disk path to exported cognitive_profile.usda */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString UsdExportPath;

    /** Bridge version that generated this profile */
    UPROPERTY(BlueprintReadOnly, Category = "Translators")
    FString GeneratorVersion;

    /** Returns true if profile has been populated */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "Translators", meta = (ToolTip = "True if profile has valid trait data"))
    bool IsValid() const { return Traits.Num() > 0 && !Checksum.IsEmpty(); }
};


/** Accumulated behavioral signals for ADHD_MoE expert routing */
USTRUCT(BlueprintType)
struct TRANSLATORSBRIDGERUNTIME_API FBehavioralSignals
{
    GENERATED_BODY()

    /** Responses longer than 10 seconds */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    int32 HesitationCount = 0;

    /** Responses shorter than 500ms */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    int32 RapidClickCount = 0;

    /** Skipped questions (reserved) */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    int32 SkipCount = 0;

    /** Back navigation count (reserved) */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    int32 BackNavigationCount = 0;

    /** Most recent response time in ms */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    float LastResponseTimeMs = 0.0f;

    /** Running average response time in ms */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    float AverageResponseTimeMs = 0.0f;

    /** MoE detected cognitive state (e.g. "focused", "stuck", "frustrated") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    FString DetectedState;

    /** MoE recommended expert (e.g. "Direct", "Scaffolder", "Validator") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    FString RecommendedExpert;

    /** Burnout level: "GREEN", "YELLOW", "ORANGE", "RED" */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    FString BurnoutLevel;

    /** Momentum phase: "building", "rolling", "peak", "declining", "crashed" */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    FString MomentumPhase;

    /** Total answers recorded */
    UPROPERTY(BlueprintReadOnly, Category = "Translators|Behavioral")
    int32 TotalResponsesRecorded = 0;
};


// ============================================================================
// Delegates
// ============================================================================

/** Fired when Python bridge_orchestrator signals ready */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBridgeReady, int32, TotalQuestions);

/** Fired when a new question arrives (fully parsed) */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnQuestionReady, const FTranslatorsQuestion&, Question);

/** Fired during scene transitions between questions */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FOnTransitionReady, const FString&, Direction, const FString&, NextScene, float, Progress);

/** Fired when the cognitive profile is complete and exported */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnProfileComplete, const FTranslatorsProfile&, Profile, const FString&, UsdPath);

/** Fired on any bridge error */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBridgeError, EBridgeErrorCode, ErrorCode, const FString&, Message);

/** Fired when a USD profile file changes on disk */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnUsdProfileUpdated, const FString&, UpdatedFilePath);
