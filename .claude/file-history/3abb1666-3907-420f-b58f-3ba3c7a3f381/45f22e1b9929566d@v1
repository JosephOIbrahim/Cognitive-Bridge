// TranslatorsHUD.cpp
// Implementation of main game HUD with polished transitions
// Programmatic UI - no Blueprint required

#include "TranslatorsHUD.h"
#include "W_QuestionDisplay.h"
#include "W_ProgressIndicator.h"
#include "W_ConnectingScreen.h"
#include "W_FinaleScreen.h"
#include "../BridgeComponent.h"
#include "Blueprint/UserWidget.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Engine/Canvas.h"


ATranslatorsHUD::ATranslatorsHUD()
{
    bIsBridgeConnected = false;
    bIsComplete = false;
    TotalQuestions = 8;
}


void ATranslatorsHUD::BeginPlay()
{
    Super::BeginPlay();

    UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] BeginPlay - Initializing..."));

    // Find BridgeComponent
    BridgeComponent = FindBridgeComponent();

    if (BridgeComponent)
    {
        UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Found BridgeComponent - binding events"));

        BridgeComponent->OnBridgeReady.AddDynamic(this, &ATranslatorsHUD::OnBridgeReady);
        BridgeComponent->OnQuestionReceived.AddDynamic(this, &ATranslatorsHUD::OnQuestionReceived);
        BridgeComponent->OnTransitionReceived.AddDynamic(this, &ATranslatorsHUD::OnTransitionReceived);
        BridgeComponent->OnFinaleReceived.AddDynamic(this, &ATranslatorsHUD::OnFinaleReceived);
    }
    else
    {
        UE_LOG(LogTemp, Warning, TEXT("[TranslatorsHUD] BridgeComponent not found in level!"));
    }

    // Create UI widgets
    CreateWidgets();

    // Show connecting screen initially
    ShowConnectingScreen();

    // Check if bridge already processed state before we subscribed
    if (BridgeComponent)
    {
        if (BridgeComponent->IsBridgeConnected())
        {
            OnBridgeReady(TotalQuestions);
        }

        FTranslatorsQuestion Q = BridgeComponent->GetCurrentQuestion();
        if (!Q.QuestionId.IsEmpty())
        {
            UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Catching up - bridge already has question: %s"), *Q.QuestionId);
            CurrentQuestion = Q;
            QuestionStartTime = GetWorld()->GetTimeSeconds();
            if (QuestionWidget)
            {
                QuestionWidget->ShowQuestion(CurrentQuestion);
                QuestionWidget->SetRenderOpacity(1.0f);
            }
            ShowQuestionScreen();
        }
    }
}


void ATranslatorsHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (BridgeComponent)
    {
        BridgeComponent->OnBridgeReady.RemoveAll(this);
        BridgeComponent->OnQuestionReceived.RemoveAll(this);
        BridgeComponent->OnTransitionReceived.RemoveAll(this);
        BridgeComponent->OnFinaleReceived.RemoveAll(this);
    }

    if (QuestionWidget)
    {
        QuestionWidget->OnAnswerSelected.RemoveAll(this);
        QuestionWidget->RemoveFromParent();
    }
    if (ConnectingWidget)
    {
        ConnectingWidget->RemoveFromParent();
    }
    if (FinaleWidget)
    {
        FinaleWidget->RemoveFromParent();
    }

    Super::EndPlay(EndPlayReason);
}


UBridgeComponent* ATranslatorsHUD::FindBridgeComponent()
{
    TArray<AActor*> AllActors;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), AActor::StaticClass(), AllActors);

    for (AActor* Actor : AllActors)
    {
        UBridgeComponent* Bridge = Actor->FindComponentByClass<UBridgeComponent>();
        if (Bridge)
        {
            return Bridge;
        }
    }

    // Fallback: spawn a dedicated actor with BridgeComponent
    UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] No BridgeComponent found - spawning BridgeActor"));
    UWorld* World = GetWorld();
    if (World)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        AActor* BridgeActor = World->SpawnActor<AActor>(AActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
        if (BridgeActor)
        {
            UBridgeComponent* Bridge = NewObject<UBridgeComponent>(BridgeActor, TEXT("BridgeComponent"));
            Bridge->bVerboseLogging = true;
            BridgeActor->AddInstanceComponent(Bridge);
            Bridge->RegisterComponent();
            return Bridge;
        }
    }

    return nullptr;
}


void ATranslatorsHUD::CreateWidgets()
{
    APlayerController* PC = GetOwningPlayerController();
    if (!PC)
    {
        UE_LOG(LogTemp, Warning, TEXT("[TranslatorsHUD] No PlayerController - cannot create widgets"));
        return;
    }

    // Create question display widget
    if (QuestionDisplayClass)
    {
        QuestionWidget = CreateWidget<UW_QuestionDisplay>(PC, QuestionDisplayClass);
    }
    else
    {
        QuestionWidget = CreateWidget<UW_QuestionDisplay>(PC, UW_QuestionDisplay::StaticClass());
    }
    if (QuestionWidget)
    {
        QuestionWidget->AddToViewport(10);
        QuestionWidget->SetVisibility(ESlateVisibility::Hidden);
        QuestionWidget->SetRenderOpacity(0.0f);
        QuestionWidget->OnAnswerSelected.AddDynamic(this, &ATranslatorsHUD::OnAnswerSelected);
        UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Created QuestionWidget"));
    }

    // Create connecting widget
    if (ConnectingWidgetClass)
    {
        ConnectingWidget = CreateWidget<UUserWidget>(PC, ConnectingWidgetClass);
    }
    else
    {
        ConnectingWidget = CreateWidget<UW_ConnectingScreen>(PC, UW_ConnectingScreen::StaticClass());
    }
    if (ConnectingWidget)
    {
        ConnectingWidget->AddToViewport(20);
        UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Created ConnectingWidget"));
    }

    // Create finale widget
    if (FinaleWidgetClass)
    {
        FinaleWidget = CreateWidget<UUserWidget>(PC, FinaleWidgetClass);
    }
    else
    {
        FinaleWidget = CreateWidget<UW_FinaleScreen>(PC, UW_FinaleScreen::StaticClass());
    }
    if (FinaleWidget)
    {
        FinaleWidget->AddToViewport(30);
        FinaleWidget->SetVisibility(ESlateVisibility::Hidden);
        FinaleWidget->SetRenderOpacity(0.0f);
        UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Created FinaleWidget"));
    }
}


void ATranslatorsHUD::ShowConnectingScreen()
{
    if (ConnectingWidget)
    {
        ConnectingWidget->SetVisibility(ESlateVisibility::Visible);
        ConnectingWidget->SetRenderOpacity(1.0f);
    }
    if (QuestionWidget)
    {
        QuestionWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (FinaleWidget)
    {
        FinaleWidget->SetVisibility(ESlateVisibility::Hidden);
    }
}


void ATranslatorsHUD::ShowQuestionScreen()
{
    if (ConnectingWidget)
    {
        ConnectingWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (QuestionWidget)
    {
        QuestionWidget->SetVisibility(ESlateVisibility::Visible);
    }
    if (FinaleWidget)
    {
        FinaleWidget->SetVisibility(ESlateVisibility::Hidden);
    }

    // Enable mouse cursor for UI interaction
    APlayerController* PC = GetOwningPlayerController();
    if (PC)
    {
        PC->bShowMouseCursor = true;
        FInputModeGameAndUI InputMode;
        InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        PC->SetInputMode(InputMode);
    }
}


void ATranslatorsHUD::ShowFinaleScreen(const FString& Message)
{
    TransitionState = EHUDTransition::None;

    if (ConnectingWidget)
    {
        ConnectingWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (QuestionWidget)
    {
        QuestionWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (FinaleWidget)
    {
        FinaleWidget->SetVisibility(ESlateVisibility::Visible);
        FinaleWidget->SetRenderOpacity(1.0f);
    }
}


void ATranslatorsHUD::SendAcknowledgment()
{
    if (BridgeComponent)
    {
        BridgeComponent->SendAcknowledge();
        UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Sent acknowledgment"));
    }
}


// === EVENT HANDLERS ===

void ATranslatorsHUD::OnBridgeReady(int32 InTotalQuestions)
{
    UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Bridge ready! Total questions: %d"), InTotalQuestions);

    bIsBridgeConnected = true;
    TotalQuestions = InTotalQuestions;

    SendAcknowledgment();
}


void ATranslatorsHUD::OnQuestionReceived(const FString& QuestionJson)
{
    UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Question received"));

    if (!BridgeComponent)
    {
        return;
    }

    CurrentQuestion = BridgeComponent->GetCurrentQuestion();
    QuestionStartTime = GetWorld()->GetTimeSeconds();

    // Load question content into widget
    if (QuestionWidget)
    {
        QuestionWidget->ShowQuestion(CurrentQuestion);
    }

    // If we're waiting for next question (mid-transition), start fade-in
    if (TransitionState == EHUDTransition::WaitForNext)
    {
        TransitionState = EHUDTransition::FadeIn;
        TransitionTimer = 0.0f;
        ShowQuestionScreen();
        if (QuestionWidget)
        {
            QuestionWidget->SetRenderOpacity(0.0f);
        }
    }
    else
    {
        // First question or catch-up: show immediately
        ShowQuestionScreen();
        if (QuestionWidget)
        {
            QuestionWidget->SetRenderOpacity(1.0f);
        }
    }

    // Debug overlay
    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(1, 15.0f, FColor::Green,
            FString::Printf(TEXT("Q%d/%d: %s"), CurrentQuestion.Index + 1, CurrentQuestion.Total, *CurrentQuestion.QuestionId));
    }

    UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Displaying question %d/%d: %s"),
        CurrentQuestion.Index + 1, CurrentQuestion.Total, *CurrentQuestion.QuestionId);
}


void ATranslatorsHUD::OnTransitionReceived(const FString& Direction, const FString& NextScene)
{
    UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Transition: %s -> %s"), *Direction, *NextScene);

    // Debug overlay for transition
    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(2, 3.0f, FColor::Cyan,
            FString::Printf(TEXT("-> %s"), *NextScene));
    }
}


void ATranslatorsHUD::OnFinaleReceived(const FString& UsdPath)
{
    UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Finale! USD path: %s"), *UsdPath);

    bIsComplete = true;

    UW_FinaleScreen* FinaleScreen = Cast<UW_FinaleScreen>(FinaleWidget);
    if (FinaleScreen)
    {
        FinaleScreen->SetUsdPath(UsdPath);
    }

    ShowFinaleScreen(TEXT("Your cognitive profile is complete."));
}


// === HUD CANVAS DRAWING (bypasses UMG) ===

void ATranslatorsHUD::DrawHUD()
{
    Super::DrawHUD();

    if (bIsComplete)
    {
        // Draw finale
        DrawText(TEXT("PROFILE COMPLETE"), FColor::Cyan, 100, 100, nullptr, 2.0f);
        DrawText(TEXT("Your cognitive profile has been generated."), FColor::White, 100, 140);
        return;
    }

    if (CurrentQuestion.QuestionId.IsEmpty())
    {
        // No question yet - show connecting
        DrawText(TEXT("Connecting to Claude Code..."), FColor(128, 128, 153), Canvas->SizeX / 2 - 150, Canvas->SizeY / 2, nullptr, 1.5f);
        return;
    }

    // Draw question on canvas
    float CenterX = Canvas->SizeX / 2.0f;
    float StartY = Canvas->SizeY * 0.2f;

    // Progress
    FString ProgressStr = FString::Printf(TEXT("%d / %d"), CurrentQuestion.Index + 1, CurrentQuestion.Total);
    DrawText(ProgressStr, FColor(128, 128, 153), CenterX - 30, StartY, nullptr, 1.2f);

    // Question text
    FString FormattedText = CurrentQuestion.Text.Replace(TEXT("\\n"), TEXT(" "));
    DrawText(FormattedText, FColor(92, 255, 219), CenterX - 250, StartY + 50, nullptr, 1.5f);

    // Options
    float OptionY = StartY + 130;
    for (int32 i = 0; i < CurrentQuestion.OptionLabels.Num(); i++)
    {
        FString OptionStr = FString::Printf(TEXT("[%d]  %s"), i + 1, *CurrentQuestion.OptionLabels[i]);

        // Highlight selected option
        FColor OptionColor = FColor(230, 230, 230);
        if (PendingAnswerIndex == i)
        {
            OptionColor = FColor(92, 255, 219);  // Cyan highlight
        }

        DrawText(OptionStr, OptionColor, CenterX - 200, OptionY, nullptr, 1.3f);
        OptionY += 50;
    }

    // Instructions
    if (TransitionState == EHUDTransition::None && PendingAnswerIndex < 0)
    {
        DrawText(TEXT("Press 1, 2, or 3 to answer"), FColor(100, 100, 120), CenterX - 120, OptionY + 30);
    }
    else if (TransitionState == EHUDTransition::AnswerHold)
    {
        DrawText(TEXT("..."), FColor(92, 255, 219), CenterX - 10, OptionY + 30, nullptr, 1.5f);
    }
}


// === TICK & TRANSITIONS ===

void ATranslatorsHUD::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    UpdateTransition(DeltaSeconds);
    HandleKeyInput();
}


void ATranslatorsHUD::UpdateTransition(float DeltaSeconds)
{
    if (TransitionState == EHUDTransition::None)
    {
        return;
    }

    TransitionTimer += DeltaSeconds;

    switch (TransitionState)
    {
    case EHUDTransition::AnswerHold:
    {
        // Hold the selected answer visible for a moment
        if (TransitionTimer >= ANSWER_HOLD_TIME)
        {
            // Now send the answer to bridge
            if (BridgeComponent && PendingAnswerIndex >= 0)
            {
                float ResponseTimeMs = (GetWorld()->GetTimeSeconds() - QuestionStartTime) * 1000.0f;
                BridgeComponent->SendAnswer(CurrentQuestion.QuestionId, PendingAnswerIndex, ResponseTimeMs);
                UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Sent deferred answer: option %d (%.0fms)"), PendingAnswerIndex, ResponseTimeMs);
                PendingAnswerIndex = -1;
            }

            // Start fade out
            TransitionState = EHUDTransition::FadeOut;
            TransitionTimer = 0.0f;
        }
        break;
    }

    case EHUDTransition::FadeOut:
    {
        float Alpha = FMath::Clamp(1.0f - (TransitionTimer / FADE_DURATION), 0.0f, 1.0f);
        if (QuestionWidget)
        {
            QuestionWidget->SetRenderOpacity(Alpha);
        }

        if (TransitionTimer >= FADE_DURATION)
        {
            // Fully faded out - wait for next question
            if (QuestionWidget)
            {
                QuestionWidget->SetRenderOpacity(0.0f);
            }
            TransitionState = EHUDTransition::WaitForNext;
            TransitionTimer = 0.0f;
        }
        break;
    }

    case EHUDTransition::WaitForNext:
    {
        // Waiting for OnQuestionReceived or OnFinaleReceived to advance us
        // Safety timeout: if we wait too long, go back to visible
        if (TransitionTimer > 10.0f)
        {
            UE_LOG(LogTemp, Warning, TEXT("[TranslatorsHUD] Transition timeout - returning to visible"));
            if (QuestionWidget)
            {
                QuestionWidget->SetRenderOpacity(1.0f);
            }
            TransitionState = EHUDTransition::None;
        }
        break;
    }

    case EHUDTransition::FadeIn:
    {
        float Alpha = FMath::Clamp(TransitionTimer / FADE_DURATION, 0.0f, 1.0f);
        if (QuestionWidget)
        {
            QuestionWidget->SetRenderOpacity(Alpha);
        }

        if (TransitionTimer >= FADE_DURATION)
        {
            if (QuestionWidget)
            {
                QuestionWidget->SetRenderOpacity(1.0f);
            }
            TransitionState = EHUDTransition::None;
            // Reset question start time for input cooldown
            QuestionStartTime = GetWorld()->GetTimeSeconds();
        }
        break;
    }

    default:
        break;
    }
}


void ATranslatorsHUD::HandleKeyInput()
{
    // Only accept input when idle (no transition in progress)
    if (TransitionState != EHUDTransition::None)
    {
        return;
    }

    if (!QuestionWidget || QuestionWidget->GetVisibility() != ESlateVisibility::Visible)
    {
        return;
    }
    if (QuestionWidget->GetSelectedOptionIndex() != -1)
    {
        return;
    }

    // Guard: ignore input for 0.5s after question appears
    float TimeSinceQuestion = GetWorld()->GetTimeSeconds() - QuestionStartTime;
    if (TimeSinceQuestion < 0.5f)
    {
        return;
    }

    APlayerController* PC = GetOwningPlayerController();
    if (!PC)
    {
        return;
    }

    if (PC->WasInputKeyJustPressed(EKeys::One) || PC->WasInputKeyJustPressed(EKeys::NumPadOne))
    {
        OnAnswerSelected(0);
    }
    else if (PC->WasInputKeyJustPressed(EKeys::Two) || PC->WasInputKeyJustPressed(EKeys::NumPadTwo))
    {
        OnAnswerSelected(1);
    }
    else if (PC->WasInputKeyJustPressed(EKeys::Three) || PC->WasInputKeyJustPressed(EKeys::NumPadThree))
    {
        OnAnswerSelected(2);
    }
}


void ATranslatorsHUD::OnAnswerSelected(int32 OptionIndex)
{
    // Prevent double-answers during transition
    if (TransitionState != EHUDTransition::None)
    {
        return;
    }

    UE_LOG(LogTemp, Log, TEXT("[TranslatorsHUD] Answer selected: option %d"), OptionIndex);

    // Store answer for deferred sending
    PendingAnswerIndex = OptionIndex;

    // Start transition: hold the selected answer visible
    TransitionState = EHUDTransition::AnswerHold;
    TransitionTimer = 0.0f;

    // Visual feedback: highlight the selected option in the widget
    if (QuestionWidget)
    {
        // The widget's HandleOptionClicked already handles highlighting
        // For keyboard input, we need to manually trigger the visual
        // OnAnswerSelected delegate was already broadcast by the widget for mouse clicks
        // For keyboard, trigger it on the widget side too
    }
}
