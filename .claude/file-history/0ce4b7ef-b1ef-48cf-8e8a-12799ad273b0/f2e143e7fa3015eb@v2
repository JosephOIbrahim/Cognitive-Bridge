// TranslatorsGameMode.cpp
// Implementation of game mode

#include "TranslatorsGameMode.h"
#include "TranslatorsHUD.h"
#include "../BridgeComponent.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"


ATranslatorsGameMode::ATranslatorsGameMode()
{
    // Set default HUD class
    HUDClass = ATranslatorsHUD::StaticClass();

    // No pawn needed for questionnaire game
    DefaultPawnClass = nullptr;

    // Use default player controller
    PlayerControllerClass = APlayerController::StaticClass();

    BridgeActor = nullptr;

    UE_LOG(LogTemp, Log, TEXT("[TranslatorsGameMode] Constructed with TranslatorsHUD"));
}


void ATranslatorsGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
    Super::InitGame(MapName, Options, ErrorMessage);

    // Auto-spawn BridgeActor so HUD can find BridgeComponent without manual placement
    UWorld* World = GetWorld();
    if (World)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.Name = FName(TEXT("TranslatorsBridgeActor"));
        SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

        BridgeActor = World->SpawnActor<AActor>(AActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
        if (BridgeActor)
        {
            UBridgeComponent* Bridge = NewObject<UBridgeComponent>(BridgeActor, TEXT("BridgeComponent"));
            Bridge->bVerboseLogging = true;
            Bridge->RegisterComponent();
            BridgeActor->AddInstanceComponent(Bridge);

            UE_LOG(LogTemp, Log, TEXT("[TranslatorsGameMode] Auto-spawned BridgeActor with BridgeComponent"));
        }
    }
}
