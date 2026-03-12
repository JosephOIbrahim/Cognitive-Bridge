// W_OptionButton.cpp
// Implementation of clickable answer option button
// Programmatic UI - no Blueprint required

#include "W_OptionButton.h"
#include "TranslatorsBridgeRuntime.h"
#include "Components/Button.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "Components/SizeBox.h"
#include "Blueprint/WidgetTree.h"
#include "Misc/Paths.h"


UW_OptionButton::UW_OptionButton(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    // Default 8-bit color scheme
    NormalColor = FLinearColor(0.1f, 0.1f, 0.15f, 1.0f);      // Dark blue-gray
    HoveredColor = FLinearColor(0.2f, 0.4f, 0.5f, 1.0f);      // Teal
    PressedColor = FLinearColor(0.36f, 1.0f, 0.86f, 1.0f);    // Cyan (matches PALETTE.glowCyan)
    TextColor = FLinearColor(0.9f, 0.9f, 0.9f, 1.0f);         // Off-white
}


TSharedRef<SWidget> UW_OptionButton::RebuildWidget()
{
    if (!OptionButton || !OptionLabel)
    {
        BuildWidgetTree();
    }
    return Super::RebuildWidget();
}


void UW_OptionButton::NativeConstruct()
{
    Super::NativeConstruct();

    // Bind button events if button exists
    if (OptionButton)
    {
        OptionButton->OnClicked.AddDynamic(this, &UW_OptionButton::HandleButtonClicked);
        OptionButton->OnHovered.AddDynamic(this, &UW_OptionButton::HandleButtonHovered);
        OptionButton->OnUnhovered.AddDynamic(this, &UW_OptionButton::HandleButtonUnhovered);
    }

    // Set initial visual state
    UpdateVisualState(NormalColor);

    // Set label text if available
    if (OptionLabel && !LabelText.IsEmpty())
    {
        OptionLabel->SetText(LabelText);
        OptionLabel->SetColorAndOpacity(FSlateColor(TextColor));
    }

    UE_LOG(LogTranslatorsBridge, Log, TEXT("[W_OptionButton] Constructed (Programmatic UI)"));
}


void UW_OptionButton::NativeDestruct()
{
    // Unbind events
    if (OptionButton)
    {
        OptionButton->OnClicked.RemoveAll(this);
        OptionButton->OnHovered.RemoveAll(this);
        OptionButton->OnUnhovered.RemoveAll(this);
    }

    Super::NativeDestruct();
}


void UW_OptionButton::SetupOption(int32 Index, const FText& Label, const FString& Dir)
{
    OptionIndex = Index;
    LabelText = Label;
    Direction = Dir;

    // Update label if widget exists
    if (OptionLabel)
    {
        OptionLabel->SetText(LabelText);
    }

    UE_LOG(LogTranslatorsBridge, Log, TEXT("[W_OptionButton] Setup option %d: %s (dir: %s)"),
        Index, *Label.ToString(), *Dir);
}


void UW_OptionButton::SetHighlighted(bool bHighlighted)
{
    if (bHighlighted)
    {
        UpdateVisualState(HoveredColor);
    }
    else
    {
        UpdateVisualState(NormalColor);
    }
}


void UW_OptionButton::SimulateClick()
{
    HandleButtonClicked();
}


void UW_OptionButton::HandleButtonClicked()
{
    UE_LOG(LogTranslatorsBridge, Log, TEXT("[W_OptionButton] Option %d clicked"), OptionIndex);

    // Visual feedback
    UpdateVisualState(PressedColor);

    // Broadcast the click event
    OnOptionClicked.Broadcast(OptionIndex);

    // Return to normal after brief delay (handled by caller typically)
}


void UW_OptionButton::HandleButtonHovered()
{
    UpdateVisualState(HoveredColor);

    // Optional: Play hover sound
    // UGameplayStatics::PlaySound2D(this, HoverSound);
}


void UW_OptionButton::HandleButtonUnhovered()
{
    UpdateVisualState(NormalColor);
}


void UW_OptionButton::UpdateVisualState(const FLinearColor& BackgroundColor)
{
    if (ButtonBorder)
    {
        ButtonBorder->SetBrushColor(BackgroundColor);
    }
    else if (OptionButton)
    {
        // Fallback: tint the button itself
        FButtonStyle Style = OptionButton->GetStyle();
        Style.Normal.TintColor = FSlateColor(BackgroundColor);
        Style.Hovered.TintColor = FSlateColor(HoveredColor);
        Style.Pressed.TintColor = FSlateColor(PressedColor);
        OptionButton->SetStyle(Style);
    }
}


void UW_OptionButton::BuildWidgetTree()
{
    // Create border as root (for background color)
    ButtonBorder = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("ButtonBorder"));
    ButtonBorder->SetBrushColor(NormalColor);
    ButtonBorder->SetPadding(FMargin(20.0f, 12.0f));
    WidgetTree->RootWidget = ButtonBorder;

    // Create size box to ensure consistent button size
    USizeBox* ButtonSizeBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), TEXT("ButtonSizeBox"));
    ButtonSizeBox->SetMinDesiredWidth(400.0f);
    ButtonSizeBox->SetMinDesiredHeight(50.0f);
    ButtonBorder->AddChild(ButtonSizeBox);

    // Create the actual button (invisible, just for interaction)
    OptionButton = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("OptionButton"));

    // Make button transparent - border handles visuals
    FButtonStyle TransparentStyle;
    TransparentStyle.Normal.TintColor = FSlateColor(FLinearColor::Transparent);
    TransparentStyle.Hovered.TintColor = FSlateColor(FLinearColor::Transparent);
    TransparentStyle.Pressed.TintColor = FSlateColor(FLinearColor::Transparent);
    OptionButton->SetStyle(TransparentStyle);

    ButtonSizeBox->AddChild(OptionButton);

    // Create label text
    OptionLabel = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("OptionLabel"));
    OptionLabel->SetText(LabelText.IsEmpty() ? NSLOCTEXT("TranslatorsBridge", "OptionButton.Default", "Option") : LabelText);
    OptionLabel->SetColorAndOpacity(FSlateColor(TextColor));
    OptionLabel->SetJustification(ETextJustify::Center);
    OptionLabel->SetAutoWrapText(true);

    OptionLabel->SetFont(FSlateFontInfo(FPaths::EngineContentDir() / TEXT("Slate/Fonts/Roboto-Regular.ttf"), 18));

    OptionButton->AddChild(OptionLabel);

    UE_LOG(LogTranslatorsBridge, Log, TEXT("[W_OptionButton] Built programmatic widget tree"));
}
