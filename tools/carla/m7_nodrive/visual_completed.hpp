#pragma once
// Called only by the authenticated owner in a paused simulation-time world.
namespace StrataM10VisualInspect {
inline Json CompletedActors(UCarlaEpisode& Episode, const Json& Request, uint32 Ego) {
  const TArray<TSharedPtr<FJsonValue>>* Ids=nullptr;
  if (!Request->TryGetArrayField(TEXT("actors"), Ids) || Ids->Num()!=3) return nullptr;
  uint32 Previous=0;
  bool IncludesEgo=false;
  Array Actors;
  const auto Begin=Clock();
  for (const auto& Value : *Ids) {
    double Number=0;
    if (!Value.IsValid() || !Value->TryGetNumber(Number) || !FMath::IsFinite(Number) ||
        Number<1 || Number>MAX_uint32 || Number!=double(uint32(Number)) || uint32(Number)<=Previous)
      return nullptr;
    Previous=uint32(Number);
    IncludesEgo |= Previous==Ego;
    auto Observed=Actor(Episode,Previous);
    if (!Observed->GetBoolField(TEXT("present"))) return nullptr;
    Actors.Add(MakeShared<FJsonValueObject>(Observed));
  }
  if (!IncludesEgo) return nullptr;
  auto Out=Object();
  Out->SetStringField(TEXT("begin_ns"),Decimal(Begin));
  Out->SetStringField(TEXT("end_ns"),Decimal(Clock()));
  Out->SetArrayField(TEXT("actors"),Actors);
  return Out;
}
}
