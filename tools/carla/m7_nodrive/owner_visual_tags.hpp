#pragma once
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

// Opt-in for a dedicated NullRHI physics process. Semantic stencil labels are
// still assigned by TagActor; only the auxiliary rendering proxies are omitted.
// Collision-bearing original components and assets are never changed here.
inline bool StrataM10OmitVisualTags()
{
  static const bool Enabled = [] {
    const bool Requested = FParse::Param(FCommandLine::Get(), TEXT("StrataM10NoVisualTags"));
    if (Requested && (!FParse::Param(FCommandLine::Get(), TEXT("nullrhi")) ||
                      !FParse::Param(FCommandLine::Get(), TEXT("norenderthread")))) {
      UE_LOG(LogCarla, Fatal, TEXT("StrataM10NoVisualTags requires a NullRHI owner without a render thread"));
    }
    if (Requested) {
      UE_LOG(LogCarla, Log, TEXT("StrataM10NoVisualTags: retain semantic stencils; omit auxiliary visual tag components"));
    }
    return Requested;
  }();
  return Enabled;
}
