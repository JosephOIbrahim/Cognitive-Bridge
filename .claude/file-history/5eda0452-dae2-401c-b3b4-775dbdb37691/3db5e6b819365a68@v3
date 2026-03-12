// TranslatorsBridgeRuntime.cpp
// Runtime module implementation.

#include "TranslatorsBridgeRuntime.h"
#include "TranslatorsStyle.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY(LogTranslatorsBridge);

void FTranslatorsBridgeRuntimeModule::StartupModule()
{
    FTranslatorsStyle::Initialize();
    UE_LOG(LogTranslatorsBridge, Log, TEXT("TranslatorsBridge Runtime module loaded (v%s)"), BRIDGE_VERSION);
}

void FTranslatorsBridgeRuntimeModule::ShutdownModule()
{
    FTranslatorsStyle::Shutdown();
    UE_LOG(LogTranslatorsBridge, Log, TEXT("TranslatorsBridge Runtime module unloaded"));
}

IMPLEMENT_MODULE(FTranslatorsBridgeRuntimeModule, TranslatorsBridgeRuntime)
