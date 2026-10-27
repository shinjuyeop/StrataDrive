using System.IO;
using UnrealBuildTool;

// Compile the unchanged project codecs/receivers with UE's own C++17 ABI.
public class M7Native : ModuleRules
{
  public M7Native(ReadOnlyTargetRules Target) : base(Target)
  {
    CppStandard = CppStandardVersion.Cpp17;
    bUseUnity = false;
    PCHUsage = PCHUsageMode.NoPCHs;
    PublicDependencyModuleNames.Add("Core");
    PrivateIncludePaths.Add(Path.Combine(ModuleDirectory, "Native"));
  }
}
