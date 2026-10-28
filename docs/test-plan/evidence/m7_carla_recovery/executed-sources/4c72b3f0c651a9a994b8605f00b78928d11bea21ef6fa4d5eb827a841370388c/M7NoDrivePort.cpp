#include "Carla.h"
#include "M7NoDrivePort.h"
#include "M7NoDriveMovement.h"
#include "M7NoDriveModelConstants.h"
#include "Carla/Game/CarlaEngine.h"
#include "Carla/Game/CarlaEpisode.h"
#include "Carla/Actor/CarlaActor.h"
#include "Carla/Vehicle/CarlaWheeledVehicle.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "HAL/PlatformMisc.h"

#include <compiler/disable-ue4-macros.h>
#include <memory>
#pragma GCC visibility push(default)
#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"
#include "native_admission.hpp"
#pragma GCC visibility pop
#include <compiler/enable-ue4-macros.h>

namespace M7NoDrive {
namespace {
using namespace stratadrive::can;
using Json = TSharedPtr<FJsonObject>;
constexpr uint64 Step = 10000000;
constexpr uint64 Age = 30000000;
constexpr uint64 Skew = 10000000;
constexpr uint64 LogicalOrigin = 1000000000;
struct State {
  TWeakObjectPtr<ACarlaWheeledVehicle> Actor;
  TWeakObjectPtr<UM7NoDriveMovement> Movement;
  uint32 Session = 0;
  uint32 ActorId = 0;
  uint64 BaseFrame = 0, NextTicket = 0, Ticket = 0, Frame = 0, Begin = 0;
  uint64 PhysicsGeneration = 0;
  double SimBegin = 0;
  bool V1 = false, Native = false, Work = false;
  bool AwaitSettlement = false;
  double TotalMotorWork = 0;
  std::unique_ptr<stratadrive::m7_native::Admission> NativeGate;
  uint32 Application = 0;
  FM7WheelEffort Effort;
  bool Locked = false, Staged = false, Queued = false, InFlight = false, Latched = false;
  FString Reason;
  FString Run;
  TMap<FString, uint64> Denied;
  Json Receipt, Pending;
  // Diagnostic admission ranges; the selected server profile adds a separate model gate.
  std::unique_ptr<SteeringReceiver> Steering;
  std::unique_ptr<BrakeReceiver> Brake;
  std::unique_ptr<DriveReceiver> Drive;
};
State S;

FString Dec(uint64 V) { return FString::Printf(TEXT("%llu"), static_cast<unsigned long long>(V)); }
bool Text(const Json& J, const TCHAR* Key, FString& V) { return J->TryGetStringField(Key, V); }
bool Number(const Json& J, const TCHAR* Key, uint64& V)
{
  FString Value;
  if (!Text(J, Key, Value) || Value.IsEmpty() || Value.Len() > 20 ||
      (Value.Len() > 1 && Value[0] == '0')) return false;
  V = 0;
  for (TCHAR C : Value) {
    if (C < '0' || C > '9') return false;
    const uint64 Digit = C - '0';
    if (V > (MAX_uint64 - Digit) / 10) return false;
    V = V * 10 + Digit;
  }
  return true;
}
Json Object() { return MakeShared<FJsonObject>(); }
std::string Encode(const Json& J)
{
  FString Out;
  FJsonSerializer::Serialize(J.ToSharedRef(), TJsonWriterFactory<>::Create(&Out));
  return TCHAR_TO_UTF8(*Out);
}
Json Response(bool Ok, const FString& Reason)
{
  auto R = Object();
  R->SetBoolField(TEXT("ok"), Ok);
  R->SetStringField(TEXT("reason"), Reason);
  R->SetStringField(TEXT("schema"), TEXT("m7-nodrive-zero-probe-v1"));
  R->SetBoolField(TEXT("normal_driving_enabled"), false);
  R->SetBoolField(TEXT("interval_work_valid"), false);
  R->SetStringField(TEXT("effort_profile"), S.Native ? TEXT("virtual-ev-v1-native-functional") : (S.V1 ? TEXT("virtual-ev-v1-diagnostic") : TEXT("zero-only")));
  if (S.V1) {
    R->SetStringField(TEXT("model_id"), UTF8_TO_TCHAR(M7V1::Id));
    R->SetStringField(TEXT("model_sha256"), UTF8_TO_TCHAR(M7V1::Sha));
  }
  R->SetStringField(TEXT("frame"), Dec(FCarlaEngine::GetFrameCounter()));
  R->SetStringField(TEXT("session"), Dec(S.Session));
  R->SetStringField(TEXT("run"), S.Run);
  R->SetStringField(TEXT("actor"), Dec(S.ActorId));
  R->SetStringField(TEXT("clock_domain"), S.Native ? TEXT("m7-native-simulation-elapsed") : TEXT("m7-zero-probe-logical-frame"));
  R->SetBoolField(TEXT("locked"), S.Locked);
  R->SetBoolField(TEXT("latched"), S.Latched);
  R->SetBoolField(TEXT("staged"), S.Staged);
  R->SetBoolField(TEXT("in_flight"), S.InFlight || S.Queued);
  R->SetBoolField(TEXT("awaiting_ev_settlement"), S.AwaitSettlement);
  return R;
}
void Latch(const FString& Reason)
{
  S.Latched = true;
  S.Reason = Reason;
  S.Staged = S.Queued = S.InFlight = false;
  S.Pending.Reset();
  if (S.Movement.IsValid()) S.Movement->ClearInputs();
}
bool Settings(const UCarlaEpisode& Episode)
{
  const auto& E = Episode.GetSettings();
  return E.bSynchronousMode && E.FixedDeltaSeconds.IsSet() &&
    E.FixedDeltaSeconds.GetValue() == .01 && E.bSubstepping &&
    E.MaxSubstepDeltaTime > 0 && E.MaxSubstepDeltaTime * E.MaxSubsteps >= .01;
}
uint64 Now(const UCarlaEpisode& Episode) {
  return S.Native ? static_cast<uint64>(std::llround(Episode.GetElapsedGameTime()*1e9)) :
    LogicalOrigin + (FCarlaEngine::GetFrameCounter() - S.BaseFrame) * Step;
}
Json Physics()
{
  Json P;
  if (S.Movement.IsValid())
    FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S.Movement->DescribePhysics()), P);
  return P.IsValid() ? P : Object();
}
bool ReadPacket(const TSharedPtr<FJsonValue>& Value, stratadrive::m7_native::Packet& Out)
{
  if (!Value.IsValid()) return false;
  if (Value->Type == EJson::Null) { Out.reset(); return true; }
  FString Hex;
  if (!Value->TryGetString(Hex) || Hex.IsEmpty() || Hex.Len()%2 || Hex.Len()>1024) return false;
  stratadrive::remote::OwnerPacket P;
  P.size = Hex.Len()/2;
  auto Nibble = [](TCHAR C) { return C>='0' && C<='9' ? C-'0' : (C>='a' && C<='f' ? C-'a'+10 : -1); };
  for (unsigned I=0; I<P.size; ++I) {
    const int A=Nibble(Hex[2*I]), B=Nibble(Hex[2*I+1]);
    if (A<0 || B<0) return false;
    P.bytes[I]=static_cast<uint8>(A*16+B);
  }
  Out=P; return true;
}
template<std::size_t N>
bool ReadPackets(const Json& J, const TCHAR* Key, std::array<stratadrive::m7_native::Packet,N>& Out)
{
  const TArray<TSharedPtr<FJsonValue>>* Values=nullptr;
  if (!J->TryGetArrayField(Key, Values) || Values->Num()!=N) return false;
  for (unsigned I=0; I<N; ++I) if (!ReadPacket((*Values)[I],Out[I])) return false;
  return true;
}
bool ReadNative(const Json& J, stratadrive::m7_native::Input& Out)
{
  uint64 Service, Credit, Release, Observed, Enable;
  if (!Number(J,TEXT("observed_ns"),Observed) || !Number(J,TEXT("enable_ns"),Enable) ||
      !J->TryGetBoolField(TEXT("normal"),Out.normal) || !Number(J,TEXT("service_mask"),Service) ||
      !Number(J,TEXT("credit_mask"),Credit) || !Number(J,TEXT("release_mask"),Release) ||
      Service>255 || Credit>255 || Release>255 || !J->HasField(TEXT("permission"))) return false;
  Out.observed=Observed; Out.enable=Enable;
  Out.service_mask=Service; Out.credit_mask=Credit; Out.release_mask=Release;
  if (J->HasField(TEXT("protection_since_ns")) || J->HasField(TEXT("protection_selected_mask"))) {
    uint64 Since, Selected;
    if (!Number(J,TEXT("protection_since_ns"),Since) || !Number(J,TEXT("protection_selected_mask"),Selected) || Selected>255) return false;
    Out.protection_since=Since; Out.protection_selected_mask=Selected;
  }
  return ReadPackets(J,TEXT("actual"),Out.actual) && ReadPackets(J,TEXT("commands"),Out.commands) &&
    ReadPackets(J,TEXT("release"),Out.release) && ReadPackets(J,TEXT("credit"),Out.credit) &&
    ReadPacket(J->TryGetField(TEXT("permission")),Out.permission);
}
template <typename Frame>
bool ReadFrame(const Json& Request, const TCHAR* Role, Frame& Out, uint64 NowNs,
               uint64& Oldest)
{
  const Json* Item = nullptr;
  FString Payload;
  uint64 Id, Flags, Expiry;
  bool Fd;
  if (!Request->TryGetObjectField(Role, Item) ||
      !Number(*Item, TEXT("can_id"), Id) || Id > MAX_uint32 ||
      !Number(*Item, TEXT("fd_flags"), Flags) || Flags > 255 ||
      !(*Item)->TryGetBoolField(TEXT("is_fd"), Fd) ||
      !Text(*Item, TEXT("payload"), Payload) ||
      !Number(*Item, TEXT("oldest_ns"), Oldest) ||
      !Number(*Item, TEXT("exclusive_expiry_ns"), Expiry) ||
      Oldest > NowNs || NowNs + Step - Oldest > Age || Expiry <= NowNs + Step ||
      Payload.Len() != static_cast<int32>(Out.payload.size() * 2)) return false;
  Out.can_id = static_cast<uint32>(Id);
  Out.fd_flags = static_cast<uint8>(Flags);
  Out.is_fd = Fd;
  Out.payload_length = static_cast<uint8>(Out.payload.size());
  auto Nibble = [](TCHAR C) -> int {
    if (C >= '0' && C <= '9') return C - '0';
    if (C >= 'a' && C <= 'f') return C - 'a' + 10;
    return -1;
  };
  for (int I = 0; I != Payload.Len() / 2; ++I) {
    const int A = Nibble(Payload[I * 2]), B = Nibble(Payload[I * 2 + 1]);
    if (A < 0 || B < 0) return false;
    Out.payload[I] = static_cast<uint8>(A * 16 + B);
  }
  return true;
}
}

bool IsLocked() { return S.Locked; }
bool RejectLegacyRpc(const char* Name)
{
  if (!S.Locked) return false;
  check(IsInGameThread());
  ++S.Denied.FindOrAdd(UTF8_TO_TCHAR(Name));
  return true;
}

std::string Request(UCarlaEpisode& Episode, const std::string& Input, bool& Tick)
{
  check(IsInGameThread());
  Tick = false;
  const bool ZeroFlag = FParse::Param(FCommandLine::Get(), TEXT("StrataM7ZeroProbe"));
  const bool V1Flag = FParse::Param(FCommandLine::Get(), TEXT("StrataM7V1Probe"));
  const bool NativeFlag = FParse::Param(FCommandLine::Get(), TEXT("StrataM7NativeProbe"));
  unsigned VehicleSubsteps = 0;
  for (unsigned Candidate : {20u, 40u, 80u, 160u, 320u, 640u}) {
    const FString Flag = FString::Printf(TEXT("StrataM7V1Substeps%u"), Candidate);
    if (FParse::Param(FCommandLine::Get(), *Flag)) {
      if (VehicleSubsteps) return Encode(Response(false, TEXT("ambiguous_numerical_profile")));
      VehicleSubsteps = Candidate;
    }
  }
  if (VehicleSubsteps && !V1Flag && !NativeFlag) return Encode(Response(false, TEXT("numerical_profile_requires_v1")));
  if (unsigned(ZeroFlag) + unsigned(V1Flag) + unsigned(NativeFlag) > 1) return Encode(Response(false, TEXT("ambiguous_profile")));
  if (!ZeroFlag && !V1Flag && !NativeFlag)
    return Encode(Response(false, TEXT("disabled")));
  if (NativeFlag && VehicleSubsteps != 320) return Encode(Response(false, TEXT("native_requires_vehicle320")));
  Json J;
  if (Input.size() > 16384 || Input.find('\0') != std::string::npos || !FJsonSerializer::Deserialize(
        TJsonReaderFactory<>::Create(UTF8_TO_TCHAR(Input.c_str())), J) || !J.IsValid())
    return Encode(Response(false, TEXT("malformed")));
  FString Op;
  if (!Text(J, TEXT("op"), Op)) return Encode(Response(false, TEXT("operation")));
  if (Op == TEXT("describe")) {
    auto R = Response(true, TEXT("diagnostic_only"));
    R->SetStringField(TEXT("clock_domain"), NativeFlag ? TEXT("m7-native-simulation-elapsed; NOT wall") : TEXT("m7-zero-probe-logical-frame; NOT native wall"));
    R->SetStringField(TEXT("provenance"), NativeFlag ? TEXT("trusted local eight-role native owner; original CAN/P05 and owner-wire") : TEXT("synthetic CAN/P05 fixture only; NOT native eight-role authority"));
    R->SetObjectField(TEXT("physics"), Physics());
    auto Denied = Object();
    for (const auto& Item : S.Denied) Denied->SetStringField(Item.Key, Dec(Item.Value));
    R->SetObjectField(TEXT("denied_legacy_rpc"), Denied);
    if (S.Locked) R->SetStringField(TEXT("logical_begin_ns"), Dec(Now(Episode)));
    return Encode(R);
  }
  const FString Key = FPlatformMisc::GetEnvironmentVariable(TEXT("STRATADRIVE_M7_OWNER_KEY"));
  FString Presented;
  if (Key.Len() < 32 || !Text(J, TEXT("owner_key"), Presented) || Presented != Key)
    return Encode(Response(false, TEXT("owner")));
  if (Op == TEXT("bind")) {
    uint64 Id, Application = 0;
    if (NativeFlag && (!Number(J, TEXT("application"), Application) || !Application || Application > MAX_uint32))
      return Encode(Response(false, TEXT("native_application")));
    if (S.Locked) return Encode(Response(false, TEXT("already_bound")));
    FString Model;
    if ((V1Flag || NativeFlag) && (!Text(J, TEXT("model_sha256"), Model) || Model != UTF8_TO_TCHAR(M7V1::Sha)))
      return Encode(Response(false, TEXT("model_identity")));
    if (!Settings(Episode) || !Number(J, TEXT("actor"), Id) || Id > MAX_uint32 ||
        S.Session == MAX_uint32) return Encode(Response(false, TEXT("init")));
    auto* CarlaActor = Episode.FindCarlaActor(static_cast<uint32>(Id));
    auto* Actor = CarlaActor ? Cast<ACarlaWheeledVehicle>(CarlaActor->GetActor()) : nullptr;
    auto* Movement = Actor ? Cast<UM7NoDriveMovement>(Actor->GetVehicleMovementComponent()) : nullptr;
    if (!Movement) return Encode(Response(false, TEXT("unsupported_actor")));
    S.Actor = Actor;
    S.ActorId = static_cast<uint32>(Id);
    S.Movement = Movement;
    S.V1 = V1Flag || NativeFlag;
    S.Native = NativeFlag;
    S.Work = NativeFlag && FParse::Param(FCommandLine::Get(), TEXT("StrataM7SolverWork"));
    S.AwaitSettlement = false; S.TotalMotorWork = 0;
    S.Application = static_cast<uint32>(Application);
    S.NativeGate.reset(NativeFlag ? new stratadrive::m7_native::Admission(S.Application, Now(Episode)) : nullptr);
    S.Effort = FM7WheelEffort();
    S.Locked = true; // Failure during conversion remains contained until close.
    S.Latched = S.Staged = S.Queued = S.InFlight = false;
    S.Receipt.Reset(); S.Pending.Reset();
    S.Denied.Reset();
    if (S.Run.IsEmpty()) S.Run = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphens);
    ++S.Session;
    S.BaseFrame = FCarlaEngine::GetFrameCounter();
    S.Steering.reset(new SteeringReceiver({SteeringFrameKind::Actual, -.3, .3}));
    S.Brake.reset(new BrakeReceiver({BrakeFrameKind::Actual, 0, 1500000}));
    S.Drive.reset(new DriveReceiver({DriveFrameKind::Actual, {-200, 300}, 100, 200}));
    if (!S.Steering->start_session(S.Session, LogicalOrigin) ||
        !S.Brake->start_session(S.Session, LogicalOrigin) ||
        !S.Drive->start_session(S.Session, LogicalOrigin) || !Movement->EnableZeroProbe(VehicleSubsteps)) {
      Latch(TEXT("nodrive_init")); return Encode(Response(false, S.Reason));
    }
    S.PhysicsGeneration = Movement->PhysicsGeneration();
    if (S.V1 && !Movement->ValidateV1()) {
      Latch(TEXT("model_geometry")); return Encode(Response(false, S.Reason));
    }
    auto R = Response(true, S.V1 ? TEXT("bound_virtual_v1_diagnostic") : TEXT("bound_zero_only"));
    R->SetObjectField(TEXT("physics"), Physics());
    R->SetStringField(TEXT("logical_begin_ns"), Dec(Now(Episode)));
    R->SetNumberField(TEXT("simulation_seconds"), Episode.GetElapsedGameTime());
    R->SetStringField(TEXT("application"), Dec(S.Application));
    return Encode(R);
  }
  uint64 Session;
  FString Run;
  if (!S.Locked || !Number(J, TEXT("session"), Session) || Session != S.Session ||
      !Text(J, TEXT("run"), Run) || Run != S.Run)
    return Encode(Response(false, TEXT("session")));
  if (Op == TEXT("receipt")) {
    auto R = Response(true, TEXT("query_only"));
    if (S.Receipt.IsValid()) R->SetObjectField(TEXT("receipt"), S.Receipt);
    return Encode(R);
  }
  if (Op == TEXT("geometry")) {
    if (!S.Movement.IsValid() || !S.Movement->HasNoDrive() ||
        S.Movement->PhysicsGeneration() != S.PhysicsGeneration)
      return Encode(Response(false, TEXT("geometry_generation")));
    Json Geometry;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(
          S.Movement->DescribeGeometry()), Geometry) || !Geometry.IsValid())
      return Encode(Response(false, TEXT("geometry_unavailable")));
    auto R = Response(true, TEXT("read_only_rest_geometry"));
    R->SetNumberField(TEXT("simulation_seconds"), Episode.GetElapsedGameTime());
    R->SetObjectField(TEXT("geometry"), Geometry);
    return Encode(R);
  }
  if (Op == TEXT("pause")) {
    Latch(TEXT("paused_requires_close_and_new_init"));
    return Encode(Response(true, S.Reason));
  }
  if (Op == TEXT("reset")) {
    Latch(TEXT("reset_requires_close_and_new_init"));
    if (!S.Movement.IsValid()) return Encode(Response(false, TEXT("actor_missing")));
    S.Movement->ResetZeroProbe();
    auto R = Response(S.Movement->HasNoDrive(), S.Reason);
    R->SetObjectField(TEXT("physics"), Physics());
    return Encode(R);
  }
  if (Op == TEXT("close")) {
    Latch(TEXT("closed"));
    auto* Actor = Episode.FindCarlaActor(S.ActorId);
    if (Actor) {
      Actor->SetActorState(carla::rpc::ActorState::PendingKill);
      if (!Episode.DestroyActor(S.ActorId)) return Encode(Response(false, TEXT("destroy_failed")));
    }
    S.Actor.Reset(); S.Movement.Reset(); S.Locked = false;
    auto R = Response(true, TEXT("closed_actor_destroyed"));
    R->SetBoolField(TEXT("registry_actor_present"), Episode.FindCarlaActor(S.ActorId) != nullptr);
    return Encode(R);
  }
  if (S.Latched) return Encode(Response(false, S.Reason));
  if (!Settings(Episode) || !S.Actor.IsValid() || !S.Movement.IsValid() ||
      !S.Movement->InputsAreZero() || S.Movement->PhysicsGeneration() != S.PhysicsGeneration) {
    Latch(TEXT("plant_changed")); return Encode(Response(false, S.Reason));
  }
  if (Op == TEXT("settle_work")) {
    uint64 Ticket, Frame, End;
    double Total = 0, Balance = 0;
    FString Basis;
    if (!S.Work || !S.AwaitSettlement || !S.Receipt.IsValid() ||
        !Number(J,TEXT("ticket"),Ticket) || Ticket != S.Ticket ||
        !Number(J,TEXT("frame"),Frame) || Frame != S.Frame ||
        !Number(J,TEXT("end_ns"),End) || End != Now(Episode) ||
        !Text(J,TEXT("basis"),Basis) || Basis != TEXT("OBSERVED_SOLVER_WORK_SINGLE_EV") ||
        !J->TryGetNumberField(TEXT("total_mechanical_j"),Total) || !FMath::IsFinite(Total) ||
        !J->TryGetNumberField(TEXT("balance_j"),Balance) || !FMath::IsFinite(Balance) ||
        FMath::Abs(Total-S.TotalMotorWork) > 256*2.220446049250313e-16*(1+FMath::Abs(Total)+double(S.Ticket)) ||
        FMath::Abs(Balance) > .00072) {
      Latch(TEXT("ev_settlement_rejected")); return Encode(Response(false,S.Reason));
    }
    S.AwaitSettlement = false;
    auto R = Response(true,TEXT("ev_settlement_accepted"));
    R->SetStringField(TEXT("ticket"),Dec(S.Ticket));
    R->SetNumberField(TEXT("total_mechanical_j"),S.TotalMotorWork);
    return Encode(R);
  }
  if (Op == TEXT("stage_native")) {
    uint64 Frame;
    if (!S.Native || !S.NativeGate) return Encode(Response(false, TEXT("native_profile_required")));
    if (S.AwaitSettlement) { Latch(TEXT("ev_settlement_required")); return Encode(Response(false,S.Reason)); }
    if (S.Staged || S.Queued || S.InFlight) return Encode(Response(false, TEXT("pending")));
    const Json* Proof = nullptr;
    stratadrive::m7_native::Input Native;
    stratadrive::m7_native::Output Actual;
    if (!Number(J, TEXT("frame"), Frame) || Frame != FCarlaEngine::GetFrameCounter()+1 ||
        S.NextTicket == MAX_uint64 || !J->TryGetObjectField(TEXT("native"), Proof) ||
        !ReadNative(*Proof, Native)) {
      Latch(TEXT("native_envelope")); return Encode(Response(false, S.Reason));
    }
    const uint64 Begin = Now(Episode);
    if (!S.NativeGate->accept(Native, Begin, Actual)) {
      Latch(UTF8_TO_TCHAR(S.NativeGate->error().c_str())); return Encode(Response(false, S.Reason));
    }
    FM7WheelEffort Effort;
    if (!Actual.empty && !S.Movement->PrepareV1(Actual.angle, Actual.torque, Actual.pressure, Effort)) {
      Latch(TEXT("native_model_range_or_geometry")); return Encode(Response(false, S.Reason));
    }
    S.Frame = Frame; S.Begin = Begin; S.SimBegin = Episode.GetElapsedGameTime();
    S.Ticket = ++S.NextTicket; S.Effort = Effort;
    S.Pending = Object(); S.Pending->SetObjectField(TEXT("native"), *Proof);
    auto Applied = Object();
    Applied->SetBoolField(TEXT("empty_init"), Actual.empty);
    Applied->SetBoolField(TEXT("normal"), Actual.normal);
    Applied->SetBoolField(TEXT("protection"), Actual.protection);
    Applied->SetNumberField(TEXT("angle_rad"), Actual.angle);
    Applied->SetNumberField(TEXT("torque_nm"), Actual.torque);
    Applied->SetNumberField(TEXT("pressure_pa"), Actual.pressure);
    Applied->SetStringField(TEXT("oldest_actuator_ns"), Dec(Actual.oldest_actuator));
    Applied->SetStringField(TEXT("oldest_dependency_ns"), Dec(Actual.oldest_dependency));
    Applied->SetStringField(TEXT("exclusive_expiry_ns"), Dec(Actual.exclusive_expiry));
    S.Pending->SetObjectField(TEXT("admitted_actual"), Applied);
    S.Staged = true;
    auto R = Response(true, TEXT("staged_native_not_applied"));
    R->SetStringField(TEXT("ticket"), Dec(S.Ticket)); return Encode(R);
  }
  if (Op == TEXT("stage")) {
    if (S.Native) { Latch(TEXT("native_actual_only")); return Encode(Response(false, S.Reason)); }
    uint64 Frame;
    if (S.Staged || S.Queued || S.InFlight) return Encode(Response(false, TEXT("pending")));
    if (S.NextTicket == MAX_uint64) {
      Latch(TEXT("ticket_exhausted")); return Encode(Response(false, S.Reason));
    }
    if (!Number(J, TEXT("frame"), Frame) || Frame != FCarlaEngine::GetFrameCounter() + 1)
      return Encode(Response(false, TEXT("frame")));
    SteeringFrame Steering; BrakeFrame Brake; DriveFrame Drive;
    uint64 O[3];
    const uint64 Begin = Now(Episode);
    if (!ReadFrame(J, TEXT("steering"), Steering, Begin, O[0]) ||
        !ReadFrame(J, TEXT("brake"), Brake, Begin, O[1]) ||
        !ReadFrame(J, TEXT("drive"), Drive, Begin, O[2]) ||
        FMath::Max3(O[0], O[1], O[2]) - FMath::Min3(O[0], O[1], O[2]) > Skew)
      return Encode(Response(false, TEXT("envelope_or_coverage")));
    // Validate a candidate atomically; a rejected bundle cannot poison RX cursors.
    auto SR = *S.Steering; auto BR = *S.Brake; auto DR = *S.Drive;
    const auto A = SR.receive(Steering, Begin);
    const auto B = BR.receive(Brake, Begin);
    const auto C = DR.receive(Drive, Begin);
    const auto Accepted = ActuatorReceiveDecision::Accepted;
    auto SM = SR.current_sample(Begin); auto BM = BR.current_sample(Begin); auto DM = DR.current_sample(Begin);
    if (A.decision != Accepted || B.decision != Accepted || C.decision != Accepted ||
        !SM || !BM || !DM) return Encode(Response(false, TEXT("actual_receiver")));
    const uint64 Sources[3] = {SM->source_time_ns, BM->source_time_ns, DM->source_time_ns};
    for (unsigned I = 0; I != 3; ++I)
      if (Sources[I] < O[I] || Sources[I] > Begin || Begin + Step - Sources[I] > Age)
        return Encode(Response(false, TEXT("source_coverage")));
    if (FMath::Max3(Sources[0], Sources[1], Sources[2]) -
        FMath::Min3(Sources[0], Sources[1], Sources[2]) > Skew)
      return Encode(Response(false, TEXT("source_skew")));
    FM7WheelEffort Effort;
    if (!S.V1 && (*SM->angle_rad != 0 || *BM->pressure_pa != 0 || *DM->torque_nm != 0))
      return Encode(Response(false, TEXT("calibration_unavailable_zero_only")));
    if (S.V1 && !S.Movement->PrepareV1(*SM->angle_rad, *DM->torque_nm, *BM->pressure_pa, Effort))
      return Encode(Response(false, TEXT("model_range_or_geometry")));
    // The immutable configs match; update only validated receiver state via copy construction.
    S.Steering.reset(new SteeringReceiver(SR));
    S.Brake.reset(new BrakeReceiver(BR));
    S.Drive.reset(new DriveReceiver(DR));
    S.Frame = Frame; S.Begin = Begin; S.SimBegin = Episode.GetElapsedGameTime();
    S.Ticket = ++S.NextTicket;
    S.Effort = Effort;
    S.Pending = Object();
    for (const TCHAR* Role : {TEXT("steering"), TEXT("brake"), TEXT("drive")})
      S.Pending->SetObjectField(Role, J->GetObjectField(Role));
    S.Staged = true;
    auto R = Response(true, TEXT("staged_not_applied"));
    R->SetStringField(TEXT("ticket"), Dec(S.Ticket));
    return Encode(R);
  }
  if (Op == TEXT("advance")) {
    uint64 Ticket;
    if (!S.Staged || S.Queued || S.InFlight || !Number(J, TEXT("ticket"), Ticket) || Ticket != S.Ticket)
      return Encode(Response(false, TEXT("ticket")));
    S.Queued = true;
    Tick = true;
    return Encode(Response(true, TEXT("queued_not_receipt")));
  }
  return Encode(Response(false, TEXT("operation")));
}

bool BeforeTick(UCarlaEpisode& Episode, uint64 Frame, float DeltaSeconds)
{
  if (!S.Locked) return true;
  if (S.Latched || !S.Staged || !S.Queued || S.InFlight || S.Frame != Frame ||
      !Settings(Episode) || FMath::Abs(DeltaSeconds - .01f) > 1e-8f ||
      !S.Movement.IsValid() || !S.Movement->InputsAreZero() ||
      S.Movement->PhysicsGeneration() != S.PhysicsGeneration ||
      FMath::Abs(Episode.GetElapsedGameTime() - S.SimBegin) > 1e-9) {
    Latch(TEXT("prephysics_guard")); return false;
  }
  if (!S.Movement->NumericalProfileMatches() || (S.V1 && !S.Movement->ValidateV1()) || !S.Movement->ApplyEffort(S.Effort)) {
    Latch(TEXT("effort_apply")); return false;
  }
  S.Staged = S.Queued = false;
  if (S.Work && !S.Movement->BeginSolverWork()) { Latch(TEXT("solver_observer_unavailable")); return false; }
  S.InFlight = true;
  return true;
}

void AfterTick(UCarlaEpisode& Episode, uint64 Frame, float DeltaSeconds)
{
  if (!S.Locked) return;
  if (!S.InFlight || Frame != S.Frame || !S.Movement.IsValid() ||
      !S.Movement->EffortMatches(S.Effort) || !S.Movement->NumericalProfileMatches() ||
      S.Movement->PhysicsGeneration() != S.PhysicsGeneration ||
      FMath::Abs(DeltaSeconds - .01f) > 1e-8f ||
      FMath::Abs(Episode.GetElapsedGameTime() - S.SimBegin - .01) > 1e-6) {
    Latch(TEXT("postphysics_ambiguous")); return;
  }
  auto R = Object();
  R->SetStringField(TEXT("session"), Dec(S.Session));
  R->SetStringField(TEXT("run"), S.Run);
  R->SetStringField(TEXT("actor"), Dec(S.ActorId));
  R->SetStringField(TEXT("physics_generation"), Dec(S.PhysicsGeneration));
  R->SetStringField(TEXT("clock_domain"), S.Native ? TEXT("m7-native-simulation-elapsed") : TEXT("m7-zero-probe-logical-frame"));
  R->SetStringField(TEXT("source_identity"), S.Native ? TEXT("native-eight-role-CAN-P05-Actual; authenticated-local-owner") : TEXT("synthetic-steering/brake/drive-CAN-P05-fixture; NOT native authority"));
  R->SetStringField(TEXT("ticket"), Dec(S.Ticket));
  R->SetStringField(TEXT("frame"), Dec(Frame));
  R->SetStringField(TEXT("logical_begin_ns"), Dec(S.Begin));
  R->SetStringField(TEXT("logical_end_ns"), Dec(S.Begin + Step));
  R->SetNumberField(TEXT("simulation_begin_seconds"), S.SimBegin);
  R->SetNumberField(TEXT("simulation_end_seconds"), Episode.GetElapsedGameTime());
  R->SetObjectField(TEXT("original_actual"), S.Pending);
  if (S.Native) R->SetStringField(TEXT("application"), Dec(S.Application));
  R->SetObjectField(TEXT("physics"), Physics());
  bool Zero = true;
  for (unsigned W = 0; W != 4; ++W)
    Zero = Zero && S.Effort.Drive[W] == 0 && S.Effort.Brake[W] == 0 && S.Effort.Steer[W] == 0;
  R->SetBoolField(TEXT("applied_zero_effort"), Zero);
  R->SetStringField(TEXT("effort_profile"), S.Native ? TEXT("virtual-ev-v1-native-functional") : (S.V1 ? TEXT("virtual-ev-v1-diagnostic") : TEXT("zero-only")));
  if (S.V1) {
    R->SetStringField(TEXT("model_id"), UTF8_TO_TCHAR(M7V1::Id));
    R->SetStringField(TEXT("model_sha256"), UTF8_TO_TCHAR(M7V1::Sha));
  }
  bool WorkValid = false;
  if (S.Work) {
    Json Work;
    FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S.Movement->FinishSolverWork(WorkValid)), Work);
    R->SetObjectField(TEXT("solver_work"), Work);
    if (WorkValid) {
      for (const auto& J : Work->GetArrayField(TEXT("motor_work_j"))) S.TotalMotorWork += J->AsNumber();
      S.AwaitSettlement = true;
      R->SetStringField(TEXT("work_end_ns"),Dec(Now(Episode)));
    }
  }
  R->SetBoolField(TEXT("interval_work_valid"), WorkValid);
  R->SetBoolField(TEXT("solver_substep_work_observed"), WorkValid);
  S.Movement->ClearInputs();
  if (!S.Movement->InputsAreZero()) { Latch(TEXT("clear_failed")); return; }
  R->SetBoolField(TEXT("inputs_cleared_after_physics"), true);
  S.Receipt = R;
  if (S.Work && !WorkValid) { Latch(TEXT("solver_work_incomplete")); return; }
  S.Pending.Reset();
  S.InFlight = false;
}

void EndEpisode()
{
  if (S.Locked) Latch(TEXT("episode_ended"));
  S.Actor.Reset(); S.Movement.Reset();
  // Keep the gate closed across unexpected episode changes; no automatic INIT.
}
}
