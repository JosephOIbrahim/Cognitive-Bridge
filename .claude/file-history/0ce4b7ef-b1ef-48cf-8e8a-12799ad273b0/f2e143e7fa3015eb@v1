// TranslatorsGameMode.cpp
// Implementation of game mode

#include "TranslatorsGameMode.h"
#include "TranslatorsHUD.h"
#include "GameFramework/PlayerController.h"


ATranslatorsGameMode::ATranslatorsGameMode()
{
    // Set default HUD class
    HUDClass = ATranslatorsHUD::StaticClass();

    // No pawn needed for questionnaire game
    DefaultPawnClass = nullptr;

    // Use default player controller
    PlayerControllerClass = APlayerController::StaticClass();

    UE_LOG(LogTemp, Log, TEXT("[TranslatorsGameMode] Constructed with TranslatorsHUD"));
}
