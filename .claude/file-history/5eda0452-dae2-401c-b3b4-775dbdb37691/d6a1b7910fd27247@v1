// W_QuestionDisplay.cpp
// Implementation of main question display widget
// Programmatic UI - no Blueprint required

#include "W_QuestionDisplay.h"
#include "W_OptionButton.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "Components/SizeBox.h"
#include "Blueprint/WidgetTree.h"
#include "Misc/Paths.h"

namespace
{
    FSlateFontInfo MakeFont(int32 Size)
    {
        return FSlateFontInfo(FPaths::EngineContentDir() / TEXT("Slate/Fonts/Roboto-Regular.ttf"), Size);
    }
}


UW_QuestionDisplay::UW_QuestionDisplay(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    // 8-bit color scheme
    BackgroundColor = FLinearColor(0.02f, 0.02f, 0.05f, 0.95f);
    QuestionTextColor = FLinearColor(0.36f, 1.0f, 0.86f, 1.0f);  // Cyan
    ProgressTextColor = FLinearColor(0.5f, 0.5f, 0.6f, 1.0f);
}


TSharedRef<SWidget> UW_QuestionDisplay::RebuildWidget()
{
    if (!QuestionText || !OptionsContainer)
    {
        BuildWidgetTree();
    }
    return Super::RebuildWidget();
}


void UW_QuestionDisplay::NativeConstruct()
{
    Super::NativeConstruct();

    // Apply colors
    if (BackgroundBorder)
    {
        BackgroundBorder->SetBrushColor(BackgroundColor);
    }
    if (QuestionText)
    {
        QuestionText->SetColorAndOpacity(FSlateColor(QuestionTextColor));
    }
    if (ProgressText)
    {
        ProgressText->SetColorAndOpacity(FSlateColor(ProgressTextColor));
    }

    UE_LOG(LogTemp, Log, TEXT("[W_QuestionDisplay] Constructed (Programmatic UI)"));
}


void UW_QuestionDisplay::BuildWidgetTree()
{
    // Create root canvas
    UCanvasPanel* RootCanvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("RootCanvas"));
    WidgetTree->RootWidget = RootCanvas;

    // Create background border - centered panel
    BackgroundBorder = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("BackgroundBorder"));
    BackgroundBorder->SetBrushColor(BackgroundColor);
    BackgroundBorder->SetPadding(FMargin(40.0f, 30.0f));

    UCanvasPanelSlot* BorderSlot = RootCanvas->AddChildToCanvas(BackgroundBorder);
    if (BorderSlot)
    {
        // Center the panel
        BorderSlot->SetAnchors(FAnchors(0.5f, 0.5f, 0.5f, 0.5f));
        BorderSlot->SetAlignment(FVector2D(0.5f, 0.5f));
        BorderSlot->SetAutoSize(true);
    }

    // Create main vertical layout
    UVerticalBox* MainLayout = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("MainLayout"));
    BackgroundBorder->AddChild(MainLayout);

    // Create size box to constrain width
    USizeBox* ContentSizeBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), TEXT("ContentSizeBox"));
    ContentSizeBox->SetWidthOverride(600.0f);
    UVerticalBoxSlot* SizeBoxSlot = MainLayout->AddChildToVerticalBox(ContentSizeBox);
    if (SizeBoxSlot)
    {
        SizeBoxSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // Inner vertical box for content
    UVerticalBox* ContentBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("ContentBox"));
    ContentSizeBox->AddChild(ContentBox);

    // Depth label (top - e.g. "SURFACE", "PATTERNS", etc.)
    DepthText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("DepthText"));
    DepthText->SetText(FText::FromString(TEXT("SURFACE")));
    DepthText->SetColorAndOpacity(FSlateColor(DepthLabelColor));
    DepthText->SetJustification(ETextJustify::Center);

    DepthText->SetFont(MakeFont(12));

    UVerticalBoxSlot* DepthSlot = ContentBox->AddChildToVerticalBox(DepthText);
    if (DepthSlot)
    {
        DepthSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 8.0f));
        DepthSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // Progress text
    ProgressText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("ProgressText"));
    ProgressText->SetText(FText::FromString(TEXT("1 / 8")));
    ProgressText->SetColorAndOpacity(FSlateColor(ProgressTextColor));
    ProgressText->SetJustification(ETextJustify::Center);

    ProgressText->SetFont(MakeFont(14));

    UVerticalBoxSlot* ProgressSlot = ContentBox->AddChildToVerticalBox(ProgressText);
    if (ProgressSlot)
    {
        ProgressSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 20.0f));
        ProgressSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // Question text (center)
    QuestionText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("QuestionText"));
    QuestionText->SetText(FText::FromString(TEXT("Loading question...")));
    QuestionText->SetColorAndOpacity(FSlateColor(QuestionTextColor));
    QuestionText->SetJustification(ETextJustify::Center);
    QuestionText->SetAutoWrapText(true);

    QuestionText->SetFont(MakeFont(24));

    UVerticalBoxSlot* QuestionSlot = ContentBox->AddChildToVerticalBox(QuestionText);
    if (QuestionSlot)
    {
        QuestionSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 30.0f));
        QuestionSlot->SetHorizontalAlignment(HAlign_Fill);
    }

    // Options container
    OptionsContainer = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("OptionsContainer"));
    UVerticalBoxSlot* OptionsSlot = ContentBox->AddChildToVerticalBox(OptionsContainer);
    if (OptionsSlot)
    {
        OptionsSlot->SetHorizontalAlignment(HAlign_Fill);
    }

    UE_LOG(LogTemp, Log, TEXT("[W_QuestionDisplay] Built programmatic widget tree"));
}


void UW_QuestionDisplay::ShowQuestion(const FTranslatorsQuestion& Question)
{
    CurrentQuestion = Question;
    SelectedOptionIndex = -1;

    // Update depth label with tier-specific color
    if (DepthText)
    {
        DepthText->SetText(FText::FromString(Question.DepthLabel));

        // Color by tier
        FLinearColor TierColor;
        if (Question.DepthLabel == TEXT("SURFACE"))
        {
            TierColor = FLinearColor(0.5f, 0.8f, 0.5f, 1.0f);  // Sage green
        }
        else if (Question.DepthLabel == TEXT("PATTERNS"))
        {
            TierColor = FLinearColor(0.3f, 0.8f, 0.8f, 1.0f);  // Teal
        }
        else if (Question.DepthLabel == TEXT("FEELINGS"))
        {
            TierColor = FLinearColor(1.0f, 0.5f, 0.45f, 1.0f);  // Coral
        }
        else // CORE
        {
            TierColor = FLinearColor(1.0f, 0.85f, 0.3f, 1.0f);  // Gold
        }
        DepthText->SetColorAndOpacity(FSlateColor(TierColor));
    }

    // Update question text
    if (QuestionText)
    {
        FString FormattedText = Question.Text.Replace(TEXT("\\n"), TEXT("\n"));
        QuestionText->SetText(FText::FromString(FormattedText));
    }

    // Update progress
    UpdateProgress(Question.Index + 1, Question.Total);

    // Create option buttons
    CreateOptionButtons();

    UE_LOG(LogTemp, Log, TEXT("[W_QuestionDisplay] Showing question %d/%d: %s"),
        Question.Index + 1, Question.Total, *Question.QuestionId);
}


void UW_QuestionDisplay::UpdateProgress(int32 Current, int32 Total)
{
    if (ProgressText)
    {
        FString ProgressString = FString::Printf(TEXT("%d / %d"), Current, Total);
        ProgressText->SetText(FText::FromString(ProgressString));
    }
}


void UW_QuestionDisplay::ClearOptions()
{
    for (UW_OptionButton* Button : OptionButtons)
    {
        if (Button)
        {
            Button->OnOptionClicked.RemoveAll(this);
            Button->RemoveFromParent();
        }
    }
    OptionButtons.Empty();
    SelectedOptionIndex = -1;
}


void UW_QuestionDisplay::SetDisplayVisible(bool bVisible)
{
    SetVisibility(bVisible ? ESlateVisibility::Visible : ESlateVisibility::Hidden);
}


void UW_QuestionDisplay::CreateOptionButtons()
{
    ClearOptions();

    if (!OptionsContainer)
    {
        UE_LOG(LogTemp, Warning, TEXT("[W_QuestionDisplay] No OptionsContainer"));
        return;
    }

    TSubclassOf<UW_OptionButton> ButtonClass = OptionButtonClass;
    if (!ButtonClass)
    {
        ButtonClass = UW_OptionButton::StaticClass();
    }

    const int32 NumOptions = CurrentQuestion.OptionLabels.Num();
    for (int32 i = 0; i < NumOptions; i++)
    {
        UW_OptionButton* NewButton = CreateWidget<UW_OptionButton>(this, ButtonClass);
        if (NewButton)
        {
            FText Label = FText::FromString(CurrentQuestion.OptionLabels[i]);
            FString Dir = CurrentQuestion.OptionDirections.IsValidIndex(i)
                ? CurrentQuestion.OptionDirections[i]
                : TEXT("forward");

            NewButton->SetupOption(i, Label, Dir);
            NewButton->OnOptionClicked.AddDynamic(this, &UW_QuestionDisplay::HandleOptionClicked);

            UVerticalBoxSlot* ButtonSlot = OptionsContainer->AddChildToVerticalBox(NewButton);
            if (ButtonSlot)
            {
                ButtonSlot->SetPadding(FMargin(0.0f, 8.0f, 0.0f, 8.0f));
                ButtonSlot->SetHorizontalAlignment(HAlign_Fill);
            }

            OptionButtons.Add(NewButton);
        }
    }
}


void UW_QuestionDisplay::HandleOptionClicked(int32 OptionIndex)
{
    if (SelectedOptionIndex != -1)
    {
        return;
    }

    SelectedOptionIndex = OptionIndex;

    for (int32 i = 0; i < OptionButtons.Num(); i++)
    {
        if (OptionButtons[i])
        {
            OptionButtons[i]->SetHighlighted(i == OptionIndex);
        }
    }

    UE_LOG(LogTemp, Log, TEXT("[W_QuestionDisplay] Answer: option %d"), OptionIndex);
    OnAnswerSelected.Broadcast(OptionIndex);
}
