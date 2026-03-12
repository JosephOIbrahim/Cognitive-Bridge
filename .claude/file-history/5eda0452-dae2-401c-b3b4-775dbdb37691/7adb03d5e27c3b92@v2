// W_ConnectingScreen.cpp
// Implementation of connecting screen widget
// Programmatic UI - no Blueprint required

#include "W_ConnectingScreen.h"
#include "TranslatorsBridgeRuntime.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "Blueprint/WidgetTree.h"
#include "Misc/Paths.h"


UW_ConnectingScreen::UW_ConnectingScreen(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    // 8-bit color scheme
    BackgroundColor = FLinearColor(0.02f, 0.02f, 0.05f, 0.98f);
    TextColor = FLinearColor(0.5f, 0.5f, 0.6f, 1.0f);
}


TSharedRef<SWidget> UW_ConnectingScreen::RebuildWidget()
{
    if (!StatusText)
    {
        BuildWidgetTree();
    }
    return Super::RebuildWidget();
}


void UW_ConnectingScreen::NativeConstruct()
{
    Super::NativeConstruct();

    // Apply colors
    if (BackgroundBorder)
    {
        BackgroundBorder->SetBrushColor(BackgroundColor);
    }
    if (StatusText)
    {
        StatusText->SetColorAndOpacity(FSlateColor(TextColor));
    }

    UE_LOG(LogTranslatorsBridge, Log, TEXT("[W_ConnectingScreen] Constructed (Programmatic UI)"));
}


void UW_ConnectingScreen::SetStatusText(const FString& Status)
{
    if (StatusText)
    {
        StatusText->SetText(FText::FromString(Status));
    }
}


void UW_ConnectingScreen::BuildWidgetTree()
{
    // Border root (fills viewport, centers content)
    BackgroundBorder = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("BackgroundBorder"));
    BackgroundBorder->SetBrushColor(BackgroundColor);
    BackgroundBorder->SetHorizontalAlignment(HAlign_Center);
    BackgroundBorder->SetVerticalAlignment(VAlign_Center);
    WidgetTree->RootWidget = BackgroundBorder;

    // Centered text
    StatusText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("StatusText"));
    StatusText->SetText(FText::FromString(TEXT("Connecting to Claude Code...")));
    StatusText->SetColorAndOpacity(FSlateColor(TextColor));
    StatusText->SetJustification(ETextJustify::Center);
    StatusText->SetFont(FSlateFontInfo(FPaths::EngineContentDir() / TEXT("Slate/Fonts/Roboto-Regular.ttf"), 24));
    BackgroundBorder->AddChild(StatusText);

    UE_LOG(LogTranslatorsBridge, Log, TEXT("[W_ConnectingScreen] Built programmatic widget tree (Border root)"));
}
