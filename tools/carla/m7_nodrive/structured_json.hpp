#pragma once
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

// Internal JSON objects own their values just like the legacy parsed objects.
// This check runs before native START, never on the measured control path.
namespace M10StructuredJson {
using Json = TSharedPtr<FJsonObject>;
inline bool FiniteValue(const TSharedPtr<FJsonValue>& Value);
inline bool FiniteObject(const Json& Object) {
  if(!Object.IsValid())return false;
  for(const auto& Item:Object->Values)if(!FiniteValue(Item.Value))return false;
  return true;
}
inline bool FiniteValue(const TSharedPtr<FJsonValue>& Value) {
  if(!Value.IsValid())return false;
  if(Value->Type==EJson::Number)return FMath::IsFinite(Value->AsNumber());
  if(Value->Type==EJson::Object)return FiniteObject(Value->AsObject());
  if(Value->Type==EJson::Array) {
    for(const auto& Item:Value->AsArray())if(!FiniteValue(Item))return false;
    return true;
  }
  return Value->Type==EJson::String || Value->Type==EJson::Boolean || Value->Type==EJson::Null;
}
inline Json LegacyParsed(const Json& Original) {
  FString Text;Json Parsed;
  FJsonSerializer::Serialize(Original.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));
  FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Parsed);
  return Parsed;
}
inline Json Compatible(const Json& Original) {
  // Nonfinite physics used to pass through the actual JSON parser. Preserve
  // that rejection/representation instead of admitting new direct NaN/Inf values.
  return FiniteObject(Original) ? Original : LegacyParsed(Original);
}
inline bool Equal(const TSharedPtr<FJsonValue>& A, const TSharedPtr<FJsonValue>& B);
inline bool EqualObject(const Json& A, const Json& B) {
  if(!A.IsValid() || !B.IsValid())return A.IsValid()==B.IsValid();
  if(A->Values.Num()!=B->Values.Num())return false;
  for(const auto& Item:A->Values) {
    const auto* Other=B->Values.Find(Item.Key);
    if(!Other || !Equal(Item.Value,*Other))return false;
  }
  return true;
}
inline bool Equal(const TSharedPtr<FJsonValue>& A, const TSharedPtr<FJsonValue>& B) {
  if(!A.IsValid() || !B.IsValid())return A.IsValid()==B.IsValid();
  if(A->Type!=B->Type)return false;
  switch(A->Type) {
    case EJson::Null:return true;
    case EJson::String:return A->AsString()==B->AsString();
    case EJson::Boolean:return A->AsBool()==B->AsBool();
    case EJson::Number: {
      const double X=A->AsNumber(),Y=B->AsNumber();
      return FMemory::Memcmp(&X,&Y,sizeof(double))==0;
    }
    case EJson::Object:return EqualObject(A->AsObject(),B->AsObject());
    case EJson::Array: {
      const auto& X=A->AsArray();const auto& Y=B->AsArray();
      if(X.Num()!=Y.Num())return false;
      for(int32 I=0;I<X.Num();++I)if(!Equal(X[I],Y[I]))return false;
      return true;
    }
    default:return false;
  }
}
inline bool RoundTrip(const Json& Original, Json* Parsed=nullptr) {
  FString Text;Json Copy;
  if(!FJsonSerializer::Serialize(Original.ToSharedRef(),TJsonWriterFactory<>::Create(&Text)) ||
     !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Copy))return false;
  if(Parsed)*Parsed=Copy;
  return EqualObject(Original,Copy);
}
inline Json SelfCheck(const Json& Physics) {
  auto Fixture=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> Numbers;
  // Include signed zero, subnormals, normal boundaries and largest finite values.
  const uint64 Edges[]={0ULL,0x8000000000000000ULL,1ULL,0x8000000000000001ULL,
    0x0010000000000000ULL,0x8010000000000000ULL,0x3ff0000000000000ULL,
    0x3ff0000000000001ULL,0x7fefffffffffffffULL,0xffefffffffffffffULL};
  for(uint64 Bits:Edges) {double Value;FMemory::Memcpy(&Value,&Bits,sizeof(Value));Numbers.Add(MakeShared<FJsonValueNumber>(Value));}
  uint64 Bits=0x5a17d03a965e42b1ULL;
  while(Numbers.Num()<4096) {
    Bits^=Bits<<13;Bits^=Bits>>7;Bits^=Bits<<17;
    if((Bits&0x7ff0000000000000ULL)==0x7ff0000000000000ULL)continue;
    double Value;FMemory::Memcpy(&Value,&Bits,sizeof(Value));Numbers.Add(MakeShared<FJsonValueNumber>(Value));
  }
  Fixture->SetArrayField(TEXT("numbers"),Numbers);
  Fixture->SetStringField(TEXT("uint64"),TEXT("18446744073709551615"));
  Fixture->SetStringField(TEXT("escaped"),TEXT("quote\" slash\\ newline\n 한글"));
  auto Nested=MakeShared<FJsonObject>();Nested->SetBoolField(TEXT("false"),false);
  Nested->SetField(TEXT("null"),MakeShared<FJsonValueNull>());
  Fixture->SetObjectField(TEXT("nested"),Nested);
  Json Copy;const bool Numeric=RoundTrip(Fixture,&Copy);
  bool RejectNumber=false,RejectType=false,RejectMissing=false,RejectOrder=false;
  if(Numeric) {
    Copy->SetStringField(TEXT("uint64"),TEXT("18446744073709551614"));RejectNumber=!EqualObject(Fixture,Copy);
    RoundTrip(Fixture,&Copy);Copy->SetNumberField(TEXT("uint64"),0);RejectType=!EqualObject(Fixture,Copy);
    RoundTrip(Fixture,&Copy);Copy->RemoveField(TEXT("nested"));RejectMissing=!EqualObject(Fixture,Copy);
    RoundTrip(Fixture,&Copy);auto Array=Copy->GetArrayField(TEXT("numbers"));Array.Swap(6,7);
    Copy->SetArrayField(TEXT("numbers"),Array);RejectOrder=!EqualObject(Fixture,Copy);
  }
  const bool State=Physics.IsValid() && RoundTrip(Physics);
  bool Nonfinite=true;unsigned NonfiniteCases=0;
  for(uint64 Special:{0x7ff0000000000000ULL,0xfff0000000000000ULL,0x7ff8000000000001ULL}) {
    double Value;FMemory::Memcpy(&Value,&Special,sizeof(Value));
    auto Invalid=MakeShared<FJsonObject>();auto Child=MakeShared<FJsonObject>();
    Child->SetNumberField(TEXT("special"),Value);
    Invalid->SetArrayField(TEXT("nested"),{MakeShared<FJsonValueObject>(Child)});
    const auto Legacy=LegacyParsed(Invalid),Direct=Compatible(Invalid);
    Nonfinite=Nonfinite && !FiniteObject(Invalid) && !Legacy.IsValid() && !Direct.IsValid();
    ++NonfiniteCases;
  }
  const bool FiniteDirect=FiniteObject(Fixture) && Compatible(Fixture)==Fixture;
  auto Result=MakeShared<FJsonObject>();
  Result->SetBoolField(TEXT("ok"),Numeric && State && RejectNumber && RejectType && RejectMissing && RejectOrder && Nonfinite && FiniteDirect);
  Result->SetNumberField(TEXT("nonfinite_cases"),NonfiniteCases);
  Result->SetBoolField(TEXT("nonfinite_legacy_fallback"),Nonfinite);
  Result->SetBoolField(TEXT("finite_direct_identity"),FiniteDirect);
  Result->SetNumberField(TEXT("finite_double_patterns"),Numbers.Num());
  Result->SetBoolField(TEXT("exact_number_bits"),Numeric);
  Result->SetBoolField(TEXT("actual_physics_equal"),State);
  Result->SetBoolField(TEXT("mutation_checks"),RejectNumber && RejectType && RejectMissing && RejectOrder);
  Result->SetStringField(TEXT("scope"),TEXT("pre_native_START; no control service; bitwise JSON roundtrip and actual physics snapshot"));
  return Result;
}
}
