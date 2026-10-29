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
#include <time.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include "wall_signal.hpp"

#include <compiler/disable-ue4-macros.h>
#include <memory>
#pragma GCC visibility push(default)
#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"
#include "native_admission.hpp"
#include "wall_bridge.hpp"
#include "held_steer_sleep.hpp"
#include "solver_journal.hpp"
#pragma GCC visibility pop
#include <compiler/enable-ue4-macros.h>

namespace M7NoDrive {
namespace {
using namespace stratadrive::can;
using Json = TSharedPtr<FJsonObject>;
uint64 StepNs() {return FParse::Param(FCommandLine::Get(), TEXT("StrataM7Wall5ms")) ? 5000000 : 10000000;}
constexpr uint64 Age = 30000000;
constexpr uint64 Skew = 10000000;
constexpr uint64 LogicalOrigin = 1000000000;
struct WallIngressEntry {
  uint64 At=0,Observed=0,Enable=0;
  stratadrive::m7_native::SharedPacket Actual[3]{},Permission{};
  bool Accepted=false;
};
struct State {
  TWeakObjectPtr<ACarlaWheeledVehicle> Actor;
  TWeakObjectPtr<UM7NoDriveMovement> Movement;
  uint32 Session = 0;
  uint32 ActorId = 0;
  uint64 BaseFrame = 0, NextTicket = 0, Ticket = 0, Frame = 0, Begin = 0;
  uint64 PhysicsGeneration = 0;
  double SimBegin = 0;
  bool V1 = false, Native = false, Work = false;
  std::unique_ptr<stratadrive::m7_native::SolverJournal<1024>> Journal;
  bool AwaitSettlement = false;
  double TotalMotorWork = 0;
  std::unique_ptr<stratadrive::m7_native::Admission> NativeGate;
  uint32 Application = 0;
  bool Wall = false;
  const stratadrive::m7_native::WallSignal* Signal = nullptr;
  uint64 WallProof = 0, WallExpiry = 0, AppliedWall = 0;
  bool WallProtection = false, Pumping = false;
  stratadrive::m7_native::WallBridge* Bridge = nullptr;
  stratadrive::m7_native::SharedReader<stratadrive::m7_native::SharedProof> ProofReader;
  stratadrive::m7_native::SharedWriter<stratadrive::m7_native::SharedReceipt> ReceiptWriter;
  stratadrive::m7_native::SharedProof AppliedProof;
  uint64 NextDue = 0, WallFrames = 0, WallLimit = 0, GapUntil = 0, WallNormal=0, WallProtected=0;
  uint64 RpcBegin=0,MaxRpc=0,LastPump=0,MaxPumpGap=0;
  double WheelBegin = 0;
  FString WallWait;
  TArray<Json> WallReceipts, WallSettlements;
  std::unique_ptr<WallIngressEntry[]> WallIngress;
  uint64 IngressCount=0;
  stratadrive::m7_native::Input IngressProof;
  void CloseSignal() {if(Signal){munmap(const_cast<stratadrive::m7_native::WallSignal*>(Signal),Bridge?sizeof(*Bridge):sizeof(*Signal));Signal=nullptr;Bridge=nullptr;}}
  ~State() {CloseSignal();}
  FM7WheelEffort Effort, LastEffort;
  bool ProtectionEffort = false, LastProtection = false, KeptSteerSleep = false;
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

uint64 WallNow() {timespec T{};return clock_gettime(CLOCK_MONOTONIC,&T)==0?uint64(T.tv_sec)*1000000000+uint64(T.tv_nsec):0;}
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
  R->SetStringField(TEXT("model_step_ns"),Dec(StepNs()));
  R->SetStringField(TEXT("reason"), Reason);
  R->SetStringField(TEXT("schema"), TEXT("m7-nodrive-zero-probe-v1"));
  R->SetBoolField(TEXT("normal_driving_enabled"), false);
  R->SetBoolField(TEXT("interval_work_valid"), false);
  R->SetStringField(TEXT("effort_profile"), S.Wall ? TEXT("virtual-ev-v1-native-wall-experimental") : (S.Native ? TEXT("virtual-ev-v1-native-functional") : (S.V1 ? TEXT("virtual-ev-v1-diagnostic") : TEXT("zero-only"))));
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
  R->SetStringField(TEXT("latched_reason"),S.Reason);
  R->SetBoolField(TEXT("staged"), S.Staged);
  R->SetBoolField(TEXT("in_flight"), S.InFlight || S.Queued);
  R->SetBoolField(TEXT("awaiting_ev_settlement"), S.AwaitSettlement);
  if(S.Wall){R->SetStringField(TEXT("wall_frames"),Dec(S.WallFrames));R->SetStringField(TEXT("wall_wait"),S.WallWait);
    R->SetStringField(TEXT("native_clock_domain"),TEXT("host_CLOCK_MONOTONIC; separate_CARLA_model_time"));
    R->SetStringField(TEXT("max_rpc_window_ns"),Dec(S.MaxRpc));R->SetStringField(TEXT("max_pump_gap_ns"),Dec(S.MaxPumpGap));
    R->SetStringField(TEXT("wall_ingress_count"),Dec(S.IngressCount));
    R->SetStringField(TEXT("wall_normal_intervals"),Dec(S.WallNormal));R->SetStringField(TEXT("wall_protected_intervals"),Dec(S.WallProtected));
    R->SetBoolField(TEXT("wall_terminal"),S.Signal && stratadrive::m7_native::wall_fault(S.Signal));}
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
    E.FixedDeltaSeconds.GetValue() == double(StepNs())/1e9 && E.bSubstepping &&
    E.MaxSubstepDeltaTime > 0 && E.MaxSubstepDeltaTime * E.MaxSubsteps >= double(StepNs())/1e9;
}
uint64 Now(const UCarlaEpisode& Episode) {
  return S.Native ? static_cast<uint64>(std::llround(Episode.GetElapsedGameTime()*1e9)) :
    LogicalOrigin + (FCarlaEngine::GetFrameCounter() - S.BaseFrame) * StepNs();
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
      Oldest > NowNs || NowNs + StepNs() - Oldest > Age || Expiry <= NowNs + StepNs() ||
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
  if (StepNs()==5000000 && (!NativeFlag || !FParse::Param(FCommandLine::Get(), TEXT("StrataM7WallNative")) || FParse::Param(FCommandLine::Get(), TEXT("StrataM7SensorFrame5"))))
    return Encode(Response(false,TEXT("wall5_requires_nonvideo_wall_native")));
  Json J;
  if (Input.size() > 16384 || Input.find('\0') != std::string::npos || !FJsonSerializer::Deserialize(
        TJsonReaderFactory<>::Create(UTF8_TO_TCHAR(Input.c_str())), J) || !J.IsValid())
    return Encode(Response(false, TEXT("malformed")));
  FString Op;
  if (!Text(J, TEXT("op"), Op)) return Encode(Response(false, TEXT("operation")));
  if (Op == TEXT("wall_status")) return Encode(Response(true,TEXT("status_only")));
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
    S.Wall = NativeFlag && FParse::Param(FCommandLine::Get(),TEXT("StrataM7WallNative"));
    S.CloseSignal();S.WallProof=S.WallExpiry=S.AppliedWall=0;S.WallProtection=false;
    S.WallFrames=S.WallLimit=S.GapUntil=S.NextDue=S.WallNormal=S.WallProtected=0;S.WallReceipts.Empty(950);S.WallSettlements.Empty(950);
    S.ProofReader={};S.ReceiptWriter={};S.WallWait.Empty();S.WallIngress.reset(S.Wall?new WallIngressEntry[4096]{}:nullptr);S.IngressCount=0;S.IngressProof={};
    S.Work = NativeFlag && FParse::Param(FCommandLine::Get(), TEXT("StrataM7SolverWork"));
    const bool Compact = FParse::Param(FCommandLine::Get(), TEXT("StrataM7CompactWork"));
    if(S.Wall && (!S.Work || !Compact))return Encode(Response(false,TEXT("wall_requires_compact_solver_work")));
    if (Compact && !S.Work) return Encode(Response(false, TEXT("compact_requires_native_work")));
    S.Journal.reset(Compact ? new stratadrive::m7_native::SolverJournal<1024> : nullptr);
    S.AwaitSettlement = false; S.TotalMotorWork = 0;
    S.Application = static_cast<uint32>(Application);
    S.NativeGate.reset(NativeFlag ? new stratadrive::m7_native::Admission(S.Application, Now(Episode)) : nullptr);
    S.Effort = FM7WheelEffort(); S.LastEffort = FM7WheelEffort();
    S.ProtectionEffort = S.LastProtection = S.KeptSteerSleep = false;
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
    R->SetBoolField(TEXT("protected_hold_history_valid"), S.LastProtection);
    R->SetBoolField(TEXT("compact_solver_work"), bool(S.Journal));
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
  if (Op == TEXT("wall_start")) {
    uint64 Initial,Limit;FString Path;
    if(!S.Wall || S.Signal || S.Receipt.IsValid() || !Number(J,TEXT("limit"),Limit) || Limit<1 || Limit>950 || !Number(J,TEXT("initial"),Initial) ||
       !Text(J,TEXT("signal_path"),Path) || Initial>WallNow() || WallNow()-Initial>40000000)
      return Encode(Response(false,TEXT("wall_start_context")));
    const int Fd=open(TCHAR_TO_UTF8(*Path),O_RDWR|O_NOFOLLOW);
    struct stat Info{};
    if(Fd<0)return Encode(Response(false,TEXT("wall_signal_open")));
    if(fstat(Fd,&Info) || !S_ISREG(Info.st_mode) || Info.st_uid!=getuid() || Info.st_size!=sizeof(stratadrive::m7_native::WallBridge)) {
      close(Fd);return Encode(Response(false,TEXT("wall_signal_file")));
    }
    void* M=mmap(nullptr,sizeof(stratadrive::m7_native::WallBridge),PROT_READ|PROT_WRITE,MAP_SHARED,Fd,0);close(Fd);
    if(M==MAP_FAILED)return Encode(Response(false,TEXT("wall_signal_map")));
    S.Bridge=static_cast<stratadrive::m7_native::WallBridge*>(M);S.Signal=&S.Bridge->signal;
    if(!stratadrive::m7_native::bridge_identity(*S.Bridge,S.Application,Initial,S.ActorId,Now(Episode),
       S.Session,S.PhysicsGeneration,TCHAR_TO_UTF8(*S.Run),StepNs())) {
      S.CloseSignal();return Encode(Response(false,TEXT("wall_signal_identity")));
    }
    S.WallLimit=Limit;S.NextDue=Initial+StepNs();
    S.MaxRpc=S.LastPump=S.MaxPumpGap=0;
    S.NativeGate.reset(new stratadrive::m7_native::Admission(S.Application,Initial,stratadrive::m7_native::ClockPolicy::HostMonotonic,StepNs()));
    auto R=Response(true,TEXT("same_host_monotonic_new_init"));R->SetStringField(TEXT("wall_now_ns"),Dec(WallNow()));return Encode(R);
  }
  if(Op==TEXT("wall_gap")) {
    if(!S.Bridge || S.GapUntil)return Encode(Response(false,TEXT("wall_gap_context")));
    S.GapUntil=WallNow()+100000000;return Encode(Response(true,TEXT("withheld_physics_100ms_no_restamp")));
  }
  if(Op==TEXT("wall_ingress")) {
    uint64 Index;
    if(!S.Bridge || !Number(J,TEXT("index"),Index) || Index>=uint64(S.IngressCount))return Encode(Response(false,TEXT("wall_ingress_index")));
    const auto& Saved=S.WallIngress[Index];
    auto Entry=Object();Entry->SetStringField(TEXT("at_ns"),Dec(Saved.At));Entry->SetStringField(TEXT("observed_ns"),Dec(Saved.Observed));
    Entry->SetStringField(TEXT("enable_ns"),Dec(Saved.Enable));Entry->SetBoolField(TEXT("accepted"),Saved.Accepted);
    const auto Hex=[](const stratadrive::m7_native::SharedPacket& P)->TSharedPtr<FJsonValue> {
      if(!P.size)return MakeShared<FJsonValueNull>();
      const TCHAR* Digits=TEXT("0123456789abcdef");FString Out;Out.Reserve(int(P.size)*2);
      for(uint64 I=0;I<P.size;++I){Out.AppendChar(Digits[P.bytes[I]>>4]);Out.AppendChar(Digits[P.bytes[I]&15]);}
      return MakeShared<FJsonValueString>(Out);
    };
    TArray<TSharedPtr<FJsonValue>> Actual;for(const auto& P:Saved.Actual)Actual.Add(Hex(P));
    Entry->SetArrayField(TEXT("actual"),Actual);Entry->SetField(TEXT("permission"),Hex(Saved.Permission));
    auto R=Response(true,TEXT("original_CAN_ingress"));R->SetObjectField(TEXT("ingress"),Entry);return Encode(R);
  }
  if(Op==TEXT("wall_trace")) {
    uint64 Index;
    if(!S.Bridge || !Number(J,TEXT("index"),Index) || Index>=uint64(S.WallReceipts.Num()))return Encode(Response(false,TEXT("wall_trace_index")));
    auto R=Response(true,TEXT("immutable_wall_receipt"));R->SetObjectField(TEXT("receipt"),S.WallReceipts[Index]);
    if(Index<uint64(S.WallSettlements.Num()))R->SetObjectField(TEXT("settlement"),S.WallSettlements[Index]);return Encode(R);
  }
  if (Op == TEXT("receipt")) {
    auto R = Response(true, TEXT("query_only"));
    if (S.Receipt.IsValid()) R->SetObjectField(TEXT("receipt"), S.Receipt);
    return Encode(R);
  }
  if (Op == TEXT("solver_trace")) {
    uint64 Ticket;
    if (!S.Journal || !Number(J, TEXT("ticket"), Ticket)) return Encode(Response(false, TEXT("trace_ticket")));
    const auto* Entry = S.Journal->find(Ticket);
    if (!Entry) return Encode(Response(false, TEXT("trace_missing")));
    Json Trace;
    FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(UM7NoDriveMovement::SolverTraceSteps(Entry->trace)), Trace);
    auto R = Response(true, TEXT("immutable_raw_solver_trace"));
    R->SetObjectField(TEXT("trace"), Trace);
    R->SetStringField(TEXT("ticket"), Dec(Entry->ticket));
    R->SetStringField(TEXT("trace_frame"), Dec(Entry->frame));
    R->SetStringField(TEXT("physics_generation"), Dec(S.PhysicsGeneration));
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
    S.Actor.Reset(); S.Movement.Reset(); S.Locked = false;S.CloseSignal();
    auto R = Response(true, TEXT("closed_actor_destroyed"));
    R->SetBoolField(TEXT("registry_actor_present"), Episode.FindCarlaActor(S.ActorId) != nullptr);
    return Encode(R);
  }
  if (S.Latched) return Encode(Response(false, S.Reason));
  if (!Settings(Episode) || !S.Actor.IsValid() || !S.Movement.IsValid() ||
      !S.Movement->InputsAreZero() || S.Movement->PhysicsGeneration() != S.PhysicsGeneration) {
    Latch(TEXT("plant_changed")); return Encode(Response(false, S.Reason));
  }
  if(S.Bridge && !S.Pumping && (Op==TEXT("settle_work") || Op==TEXT("stage_native") || Op==TEXT("advance")))
    return Encode(Response(false,TEXT("wall_single_tick_owner")));
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
    const uint64 AdmissionNow=S.Wall?WallNow():Begin;
    if(S.Wall && (!S.Signal || (stratadrive::m7_native::wall_fault(S.Signal) && !Native.protection_since)))
      return Encode(Response(false,TEXT("wall_normal_closed")));
    if(S.Pumping) {
      std::string Why;
      if(!S.NativeGate->eligible(Native,AdmissionNow,Actual,&Why,4000000)){S.WallWait=UTF8_TO_TCHAR(Why.c_str());return Encode(Response(false,S.WallWait));}
    }
    if (!S.NativeGate->accept(Native, AdmissionNow, Actual)) {
      Latch(UTF8_TO_TCHAR(S.NativeGate->error().c_str())); return Encode(Response(false, S.Reason));
    }
    FM7WheelEffort Effort;
    if (!Actual.empty && !S.Movement->PrepareV1(Actual.angle, Actual.torque, Actual.pressure, Effort)) {
      Latch(TEXT("native_model_range_or_geometry")); return Encode(Response(false, S.Reason));
    }
    S.WallProof=Native.observed;S.WallExpiry=Actual.empty?AdmissionNow+StepNs()+4000001:std::min<uint64>(Actual.exclusive_expiry,Actual.oldest_actuator+Age+1);
    S.WallProtection=Actual.protection;
    S.Frame = Frame; S.Begin = Begin; S.SimBegin = Episode.GetElapsedGameTime();
    S.Ticket = ++S.NextTicket; S.Effort = Effort;
    S.ProtectionEffort = Actual.protection && Actual.torque == 0 && Actual.pressure >= 1000000;
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
      if (Sources[I] < O[I] || Sources[I] > Begin || Begin + StepNs() - Sources[I] > Age)
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

void RpcWindow(bool Begin) {
  if(!S.Bridge)return;
  const uint64 Now=WallNow();
  if(Begin)S.RpcBegin=Now;
  else if(S.RpcBegin && Now>=S.RpcBegin)S.MaxRpc=FMath::Max(S.MaxRpc,Now-S.RpcBegin);
}
bool PumpWall(UCarlaEpisode& Episode) {
  using namespace stratadrive::m7_native;
  if(S.Bridge){const uint64 Now=WallNow();if(S.LastPump)S.MaxPumpGap=FMath::Max(S.MaxPumpGap,Now-S.LastPump);S.LastPump=Now;}
  if(!S.Bridge || S.Latched || !S.Locked || S.InFlight || S.Staged || S.Queued)return false;
  SharedProof Shared;if(!S.ProofReader.read(S.Bridge->proof,Shared))return false;
  const uint64 Now=WallNow();
  if(S.AwaitSettlement) {
    if(Shared.energy_end!=static_cast<uint64>(std::llround(Episode.GetElapsedGameTime()*1e9)))return false;
    if(!FMath::IsFinite(Shared.total_mechanical) || !FMath::IsFinite(Shared.balance) ||
       FMath::Abs(Shared.total_mechanical-S.TotalMotorWork)>256*2.220446049250313e-16*(1+FMath::Abs(Shared.total_mechanical)+double(S.Ticket)) ||
       FMath::Abs(Shared.balance)>.00072) {Latch(TEXT("shared_ev_settlement_rejected"));return false;}
    auto Ack=Object();Ack->SetStringField(TEXT("end_ns"),Dec(Shared.energy_end));Ack->SetStringField(TEXT("observed_ns"),Dec(Shared.observed));
    Ack->SetNumberField(TEXT("total_mechanical_j"),Shared.total_mechanical);Ack->SetNumberField(TEXT("balance_j"),Shared.balance);
    Ack->SetNumberField(TEXT("soc"),Shared.soc);Ack->SetNumberField(TEXT("chemical_j"),Shared.chemical);Ack->SetNumberField(TEXT("motor_loss_j"),Shared.motor_loss);
    Ack->SetNumberField(TEXT("auxiliary_j"),Shared.auxiliary);Ack->SetNumberField(TEXT("ohmic_j"),Shared.ohmic);
    Ack->SetNumberField(TEXT("capacitor_delta_j"),Shared.capacitor);Ack->SetNumberField(TEXT("circuit_loss_j"),Shared.circuit);
    S.WallSettlements.Add(Ack);S.AwaitSettlement=false;
  }
  if(__atomic_load_n(&S.Bridge->stop,__ATOMIC_ACQUIRE) || S.WallFrames>=S.WallLimit)return false;
  Input Native;Output Actual;std::string Why;
  if(!restore(Shared,Native)){Latch(TEXT("shared_proof_format"));return false;}
  const auto PacketJson=[](const Packet& P)->TSharedPtr<FJsonValue> {
    if(!P)return MakeShared<FJsonValueNull>();
    FString Hex;Hex.Reserve(int(P->size)*2);
    const TCHAR* Digits=TEXT("0123456789abcdef");
    for(std::size_t I=0;I<P->size;++I){Hex.AppendChar(Digits[P->bytes[I]>>4]);Hex.AppendChar(Digits[P->bytes[I]&15]);}
    return MakeShared<FJsonValueString>(Hex);
  };
  const auto Packets=[&](const auto& Values){TArray<TSharedPtr<FJsonValue>> Out;for(const auto& P:Values)Out.Add(PacketJson(P));return Out;};
  if(S.NativeGate->started()) {
    // Ingress is not conditional on a physics release, authority preview or
    // GapUntil. Counter/timeout validation must observe real delivered traffic.
    bool Changed=false;
    for(unsigned I=0;I<3;++I)Changed=Changed || !same(Native.actual[I],S.IngressProof.actual[I]);
    Changed=Changed || bool(Native.permission)!=bool(S.IngressProof.permission) ||
      (Native.permission && !same(Native.permission,S.IngressProof.permission));
    if(Changed) {
      if(S.IngressCount>=4096){Latch(TEXT("wall_ingress_full"));return false;}
      const uint64 Received=WallNow();
      const bool Accepted=S.NativeGate->ingest(Native,Received);
      // Preallocated POD journal: no JSON/hex work on the receive deadline.
      auto& Entry=S.WallIngress[S.IngressCount++];Entry.At=Received;Entry.Observed=Native.observed;
      Entry.Enable=Native.enable;Entry.Accepted=Accepted;
      for(unsigned I=0;I<3;++I)Entry.Actual[I]=Shared.actual[I];
      Entry.Permission=Shared.permission;S.IngressProof=Native;
      if(!Accepted){Latch(UTF8_TO_TCHAR(S.NativeGate->error().c_str()));return false;}
    }
  }
  if(Now<S.NextDue || Now<S.GapUntil)return false;
  if((wall_fault(S.Signal) || __atomic_load_n(&S.Bridge->server_trip,__ATOMIC_ACQUIRE)) && !Native.protection_since){S.WallWait=TEXT("wall_normal_closed");return false;}
  // Eligibility does not consume a receiver or turn a rejected candidate into
  // a permission. The selected proof is checked again by the original gate.
  if(!S.NativeGate->eligible(Native,Now,Actual,&Why,4000000)){S.WallWait=UTF8_TO_TCHAR(Why.c_str());return false;}
  auto Proof=Object();Proof->SetStringField(TEXT("observed_ns"),Dec(Native.observed));Proof->SetStringField(TEXT("enable_ns"),Dec(Native.enable));
  Proof->SetBoolField(TEXT("normal"),Native.normal);Proof->SetStringField(TEXT("protection_since_ns"),Dec(Native.protection_since));
  Proof->SetStringField(TEXT("protection_selected_mask"),Dec(Native.protection_selected_mask));
  Proof->SetStringField(TEXT("service_mask"),Dec(Native.service_mask));Proof->SetStringField(TEXT("credit_mask"),Dec(Native.credit_mask));
  Proof->SetStringField(TEXT("release_mask"),Dec(Native.release_mask));
  Proof->SetArrayField(TEXT("actual"),Packets(Native.actual));Proof->SetArrayField(TEXT("commands"),Packets(Native.commands));
  Proof->SetArrayField(TEXT("release"),Packets(Native.release));Proof->SetArrayField(TEXT("credit"),Packets(Native.credit));
  Proof->SetField(TEXT("permission"),PacketJson(Native.permission));
  auto RequestJson=Object();RequestJson->SetStringField(TEXT("op"),TEXT("stage_native"));RequestJson->SetStringField(TEXT("frame"),Dec(FCarlaEngine::GetFrameCounter()+1));
  RequestJson->SetStringField(TEXT("session"),Dec(S.Session));RequestJson->SetStringField(TEXT("run"),S.Run);
  RequestJson->SetStringField(TEXT("owner_key"),FPlatformMisc::GetEnvironmentVariable(TEXT("STRATADRIVE_M7_OWNER_KEY")));
  RequestJson->SetObjectField(TEXT("native"),Proof);
  bool Tick=false;S.Pumping=true;Request(Episode,Encode(RequestJson),Tick);S.Pumping=false;
  if(!S.Staged)return false;
  S.AppliedProof=Shared;S.Queued=true;S.WallWait.Empty();return true;
}

bool BeforeTick(UCarlaEpisode& Episode, uint64 Frame, float DeltaSeconds)
{
  if (!S.Locked) return true;
  if (S.Latched || !S.Staged || !S.Queued || S.InFlight || S.Frame != Frame ||
      !Settings(Episode) || FMath::Abs(DeltaSeconds - float(double(StepNs())/1e9)) > 1e-8f ||
      !S.Movement.IsValid() || !S.Movement->InputsAreZero() ||
      S.Movement->PhysicsGeneration() != S.PhysicsGeneration ||
      FMath::Abs(Episode.GetElapsedGameTime() - S.SimBegin) > 1e-9) {
    Latch(TEXT("prephysics_guard")); return false;
  }
  if(S.Wall) {
    const uint64 Now=WallNow();
    if(!S.Signal || !Now || Now<S.WallProof || Now-S.WallProof>4000000 ||
       Now+StepNs()>=S.WallExpiry || ((stratadrive::m7_native::wall_fault(S.Signal) ||
       __atomic_load_n(&S.Bridge->server_trip,__ATOMIC_ACQUIRE)) && !S.WallProtection)) {
      S.Staged=S.Queued=false;S.Pending.Reset();S.Reason=TEXT("wall_prephysics_contained");return false;
    }
    S.AppliedWall=Now;
    const auto P=Physics();const auto& Wheels=P->GetArrayField(TEXT("wheels"));
    S.WheelBegin=(Wheels[2]->AsObject()->GetNumberField(TEXT("solver_omega_rad_s"))+Wheels[3]->AsObject()->GetNumberField(TEXT("solver_omega_rad_s")))/2;
  }
  if (S.Journal && (S.Journal->full() || S.Journal->failed())) { Latch(TEXT("solver_journal_full")); return false; }
  if (!S.Movement->NumericalProfileMatches() || (S.V1 && !S.Movement->ValidateV1()) || !S.Movement->ApplyEffort(S.Effort)) {
    Latch(TEXT("effort_apply")); return false;
  }
  S.Staged = S.Queued = false;
  S.KeptSteerSleep = S.Native && S.Work &&
    FParse::Param(FCommandLine::Get(), TEXT("StrataM7HeldSteerSleep")) &&
    stratadrive::m7_native::held_protection(S.LastProtection, S.ProtectionEffort,
      S.LastEffort.Steer, S.Effort.Steer, S.LastEffort.Drive, S.Effort.Drive,
      S.LastEffort.Brake, S.Effort.Brake);
  if (S.Work && !S.Movement->BeginSolverWork(S.KeptSteerSleep)) { Latch(TEXT("solver_observer_unavailable")); return false; }
  S.InFlight = true;
  return true;
}

void AfterTick(UCarlaEpisode& Episode, uint64 Frame, float DeltaSeconds)
{
  if (!S.Locked) return;
  if (!S.InFlight || Frame != S.Frame || !S.Movement.IsValid() ||
      !S.Movement->EffortMatches(S.Effort) || !S.Movement->NumericalProfileMatches() ||
      S.Movement->PhysicsGeneration() != S.PhysicsGeneration ||
      FMath::Abs(DeltaSeconds - float(double(StepNs())/1e9)) > 1e-8f ||
      FMath::Abs(Episode.GetElapsedGameTime() - S.SimBegin - double(StepNs())/1e9) > 1e-6) {
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
  R->SetStringField(TEXT("logical_end_ns"), Dec(S.Begin + StepNs()));
  R->SetStringField(TEXT("model_step_ns"),Dec(StepNs()));
  R->SetNumberField(TEXT("simulation_begin_seconds"), S.SimBegin);
  R->SetNumberField(TEXT("simulation_end_seconds"), Episode.GetElapsedGameTime());
  R->SetObjectField(TEXT("original_actual"), S.Pending);
  if(S.Wall) {
    R->SetStringField(TEXT("native_clock_domain"),TEXT("host_CLOCK_MONOTONIC; separate_CARLA_model_time"));
    R->SetStringField(TEXT("wall_applied_ns"),Dec(S.AppliedWall));
    R->SetStringField(TEXT("wall_ingress_count"),Dec(S.IngressCount));
    R->SetBoolField(TEXT("wall_fault_after_physics"),stratadrive::m7_native::wall_fault(S.Signal));
  }
  if (S.Native) R->SetStringField(TEXT("application"), Dec(S.Application));
  // Bracket this NEW post-physics acquisition on the same host monotonic
  // clock as the runner. Cached receipt queries retain both original values.
  // Wall mode uses this original acquisition coordinate. Model/solver time
  // remains separate; querying a cached receipt never changes either clock.
  timespec SampleBegin{}, SampleEnd{};
  const bool BeginOk = clock_gettime(CLOCK_MONOTONIC, &SampleBegin) == 0;
  R->SetObjectField(TEXT("physics"), Physics());
  const bool EndOk = clock_gettime(CLOCK_MONOTONIC, &SampleEnd) == 0;
  if (!BeginOk || !EndOk) { Latch(TEXT("acquisition_clock")); return; }
  R->SetStringField(TEXT("physics_acquisition_clock"), TEXT("host_CLOCK_MONOTONIC; diagnostic_not_CAN_mapping"));
  R->SetStringField(TEXT("physics_acquisition_begin_ns"), Dec(uint64(SampleBegin.tv_sec)*1000000000+uint64(SampleBegin.tv_nsec)));
  R->SetStringField(TEXT("physics_acquisition_end_ns"), Dec(uint64(SampleEnd.tv_sec)*1000000000+uint64(SampleEnd.tv_nsec)));
  bool Zero = true;
  for (unsigned W = 0; W != 4; ++W)
    Zero = Zero && S.Effort.Drive[W] == 0 && S.Effort.Brake[W] == 0 && S.Effort.Steer[W] == 0;
  R->SetBoolField(TEXT("applied_zero_effort"), Zero);
  R->SetBoolField(TEXT("protected_held_steer_sleep"), S.KeptSteerSleep);
  R->SetStringField(TEXT("effort_profile"), S.Wall ? TEXT("virtual-ev-v1-native-wall-experimental") : (S.Native ? TEXT("virtual-ev-v1-native-functional") : (S.V1 ? TEXT("virtual-ev-v1-diagnostic") : TEXT("zero-only"))));
  if (S.V1) {
    R->SetStringField(TEXT("model_id"), UTF8_TO_TCHAR(M7V1::Id));
    R->SetStringField(TEXT("model_sha256"), UTF8_TO_TCHAR(M7V1::Sha));
  }
  bool WorkValid = false;
  if (S.Work) {
    Json Work;
    M7SolverTrace Saved{};
    FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S.Movement->FinishSolverWork(WorkValid, S.Journal ? &Saved : nullptr)), Work);
    if (WorkValid && S.Journal && !S.Journal->append(Frame, S.Ticket, Saved)) { Latch(TEXT("solver_journal_rejected")); return; }
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
  if(S.Bridge && WorkValid) {
    using namespace stratadrive::m7_native;
    SharedReceipt Completed;Completed.frame=Frame;Completed.begin=S.Begin;Completed.end=Now(Episode);
    Completed.applied=S.AppliedWall;Completed.acquired_begin=uint64(SampleBegin.tv_sec)*1000000000+uint64(SampleBegin.tv_nsec);
    Completed.acquired_end=uint64(SampleEnd.tv_sec)*1000000000+uint64(SampleEnd.tv_nsec);
    const auto Admitted=S.Pending->GetObjectField(TEXT("admitted_actual"));
    uint64 Oldest=0;Number(Admitted,TEXT("oldest_actuator_ns"),Oldest);Completed.oldest=Oldest?Oldest:S.AppliedWall;
    Completed.coil_source=S.AppliedProof.coil_source;Completed.coils=S.AppliedProof.coils;Completed.wheel_begin=S.WheelBegin;
    Completed.torque=Admitted->GetNumberField(TEXT("torque_nm"));Completed.dt=double(float(double(StepNs())/1e9)*(1.f/320.f));
    const auto Work=R->GetObjectField(TEXT("solver_work"));Completed.sleeping=uint64(Work->GetNumberField(TEXT("sleeping")));
    const auto& Means=Work->GetArrayField(TEXT("rear_mean_rad_s"));
    if((Completed.sleeping && Means.Num()!=0) || (!Completed.sleeping && Means.Num()!=320)){Latch(TEXT("shared_work_count"));return;}
    for(int I=0;I<Means.Num();++I)Completed.means[I]=Means[I]->AsNumber();
    const auto& Wheels=R->GetObjectField(TEXT("physics"))->GetArrayField(TEXT("wheels"));
    for(unsigned I=0;I<4;++I)Completed.omega[I]=Wheels[I]->AsObject()->GetNumberField(TEXT("solver_omega_rad_s"));
    R->SetStringField(TEXT("coil_source_ns"),Dec(Completed.coil_source));R->SetStringField(TEXT("coil_bits"),Dec(Completed.coils));
    const bool Expired=Completed.acquired_end>=S.WallExpiry;
    R->SetBoolField(TEXT("wall_authority_expired_during_physics"),Expired);
    if(Expired)__atomic_store_n(&S.Bridge->server_trip,1ULL,__ATOMIC_RELEASE);
    S.WallReceipts.Add(R);++S.WallFrames;
    S.WallNormal+=Admitted->GetBoolField(TEXT("normal"))?1:0;S.WallProtected+=Admitted->GetBoolField(TEXT("protection"))?1:0;S.NextDue=StepNs()==5000000?S.Signal->initial+(S.WallFrames+1)*StepNs():S.AppliedWall+StepNs();
    S.ReceiptWriter.publish(S.Bridge->receipt,Completed);
  }
  if (S.Work && !WorkValid) { Latch(TEXT("solver_work_incomplete")); return; }
  S.LastProtection = S.ProtectionEffort; S.LastEffort = S.Effort;
  S.Pending.Reset();
  S.InFlight = false;
}

void Shutdown()
{
  check(IsInGameThread());
  if (S.Locked) Latch(TEXT("engine_exit"));
}

void EndEpisode()
{
  if (S.Locked) Latch(TEXT("episode_ended"));
  S.Actor.Reset(); S.Movement.Reset();
  // Keep the gate closed across unexpected episode changes; no automatic INIT.
}
}
