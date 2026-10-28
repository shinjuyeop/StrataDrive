"""Pinned, opt-in M7 camera scheduling by original CARLA frame counter."""

def apply(base, replace):
    root = 'Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Sensor/'
    header = root+'Sensor.h'
    source = root+'Sensor.cpp'
    h = replace(base(header), '  FDataStream Stream;', '  bool M7Frame5 = false;\n\n  FDataStream Stream;')
    s = replace(base(source), '#include "Carla.h"',
                '#include "Carla.h"\n#include "Misc/CommandLine.h"\n#include "Misc/Parse.h"')
    s = replace(s, '  SensorDescription = Description;', '''  SensorDescription = Description;
  // M7 explicit camera profile only. Native float tick intervals can delay the
  // first 50 ms camera release to frame six. Schedule acquisition, not delivery
  // timestamps or cached images, on the existing authoritative 10 ms frames.
  const auto* Role = Description.Variations.Find(TEXT("role_name"));
  const auto* Period = Description.Variations.Find(TEXT("sensor_tick"));
  M7Frame5 = FParse::Param(FCommandLine::Get(), TEXT("StrataM7SensorFrame5")) &&
      FParse::Param(FCommandLine::Get(), TEXT("StrataM7NativeProbe")) &&
      (Description.Id == TEXT("sensor.camera.rgb") || Description.Id == TEXT("sensor.camera.semantic_segmentation")) &&
      Role && Role->Value == TEXT("m7_frame5") && Period &&
      UActorBlueprintFunctionLibrary::ActorAttributeToFloat(*Period, 0.0f) == .05f;''')
    s = replace(s, '        0.0f));\n  }\n}', '        0.0f));\n  }\n  if (M7Frame5) SetActorTickInterval(0.0f);\n}')
    s = replace(s, '  ReadyToTick = true;', '''  if (M7Frame5 && FCarlaEngine::GetFrameCounter() % 5 != 0) return;
  ReadyToTick = true;''')
    return {header:h.encode(), source:s.encode()}
