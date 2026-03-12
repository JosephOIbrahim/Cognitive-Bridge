// TranslatorsBridgeRuntime.cpp
// Runtime module implementation.

#include "TranslatorsBridgeRuntime.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY(LogTranslatorsBridge);

void FTranslatorsBridgeRuntimeModule::StartupModule()
{
    UE_LOG(LogTranslatorsBridge, Log, TEXT("TranslatorsBridge Runtime module loaded (v%s)"), BRIDGE_VERSION);
}

void FTranslatorsBridgeRuntimeModule::ShutdownModule()
{
    UE_LOG(LogTranslatorsBridge, Log, TEXT("TranslatorsBridge Runtime module unloaded"));
}

IMPLEMENT_MODULE(FTranslatorsBridgeRuntimeModule, TranslatorsBridgeRuntime)
