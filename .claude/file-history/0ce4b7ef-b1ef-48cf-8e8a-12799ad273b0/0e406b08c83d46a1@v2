// TranslatorsGameMode.h
// Game mode for The Translators Card
// Part of The Translators Card - Claude Code → UE5.7 Bridge

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "TranslatorsGameMode.generated.h"

/**
 * ATranslatorsGameMode - Default game mode for Translators
 *
 * Sets up:
 * - TranslatorsHUD as default HUD class
 * - Default pawn (none needed for questionnaire)
 * - Auto-spawns BridgeActor with BridgeComponent (no manual placement needed)
 */
UCLASS()
class TRANSLATORSCARD_API ATranslatorsGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    ATranslatorsGameMode();

    virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;

private:
    /** The auto-spawned bridge actor */
    UPROPERTY()
    AActor* BridgeActor;
};
