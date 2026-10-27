#pragma once

#include "CoreMinimal.h"
#include <string>

class UCarlaEpisode;

// All state is owned by the server game thread. Legacy RPC guards use IsLocked.
namespace M7NoDrive {
  bool IsLocked();
  bool RejectLegacyRpc(const char* Name);
  std::string Request(UCarlaEpisode& Episode, const std::string& Json, bool& Tick);
  bool BeforeTick(UCarlaEpisode& Episode, uint64 Frame, float DeltaSeconds);
  void AfterTick(UCarlaEpisode& Episode, uint64 Frame, float DeltaSeconds);
  void EndEpisode();
}
