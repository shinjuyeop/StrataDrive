#include "../../interfaces/someip/diagnostic_binding.hpp"
#include "diagnostics_fixture.hpp"
#include <gtest/gtest.h>

namespace {
using namespace stratadrive;
using namespace someip::diagnostic;
using namespace diagnostics_fixture;
TEST(DiagnosticBinding, ExactDedicatedServiceAndDirectionAreRequiredForBothRoles) {
    for(unsigned registry=1;registry<=4;++registry) {
        const diagnostics::wire::Message d=diagnostics::wire::Data{7001,1,registry,session()};
        const diagnostics::wire::Message a=diagnostics::wire::Ack{7001,1,registry,1};
        EXPECT_TRUE(binding(Role::Replica,kReplica,1,kData,1,1,true,d,7001,registry));
        EXPECT_TRUE(binding(Role::Publisher,kPublisher,1,kAck,1,1,true,a,7001,registry));
        EXPECT_FALSE(binding(Role::Publisher,kPublisher,1,kData,1,1,true,d,7001,registry));
        EXPECT_FALSE(binding(Role::Replica,kReplica,1,kAck,1,1,true,a,7001,registry));
    }
}
TEST(DiagnosticBinding, ControlBindingsUnreliableAndForeignContextsNeverEnterIngress) {
    const diagnostics::wire::Message d=diagnostics::wire::Data{7001,1,3,session()};
    for(unsigned variant=0;variant<10;++variant) {
        std::uint16_t service=kReplica,instance=1,method=kData; unsigned type=1,version=1,registry=3; bool reliable=true; std::uint64_t stream=7001;
        switch(variant) {
        case 0:service=0x5344;break; case 1:service=kPublisher;break; case 2:instance=2;break;
        case 3:method=kAck;break; case 4:method=0x40;break; case 5:type=0;break;
        case 6:version=2;break; case 7:reliable=false;break; case 8:stream=7002;break; case 9:registry=2;break;
        }
        EXPECT_FALSE(binding(Role::Replica,service,instance,method,type,version,reliable,d,stream,registry))<<variant;
    }
    EXPECT_FALSE(binding(Role::Replica,kReplica,1,kData,1,1,true,d,0,3));
    EXPECT_FALSE(binding(Role::Replica,kReplica,1,kData,1,1,true,d,7001,4));
    EXPECT_FALSE(binding(static_cast<Role>(255),kReplica,1,kData,1,1,true,d,7001,3));
}
TEST(DiagnosticBinding, ConfiguredNativeLanesRequireTheirOwnServiceStreamAndDirection) {
    const diagnostics::wire::Message data=diagnostics::wire::Data{8200,1,3,session()};
    const diagnostics::wire::Message ack=diagnostics::wire::Ack{8200,1,3,1};
    const Services services{0x5e10,0x5e11};
    EXPECT_TRUE(binding(Role::Replica,0x5e11,1,kData,1,1,true,data,8200,3,services));
    EXPECT_TRUE(binding(Role::Publisher,0x5e10,1,kAck,1,1,true,ack,8200,3,services));
    EXPECT_FALSE(binding(Role::Replica,kReplica,1,kData,1,1,true,data,8200,3,services));
    EXPECT_FALSE(binding(Role::Replica,0x5e11,1,kData,1,1,true,data,8201,3,services));
    EXPECT_FALSE(binding(Role::Replica,0x5e11,1,kData,1,1,true,data,8200,3,{0x5e12,0x5e13}));
    EXPECT_FALSE(binding(Role::Replica,0x5e11,1,kData,1,1,true,data,8200,3,{0x5344,0x5e11}));
    EXPECT_FALSE(binding(Role::Replica,0x5e11,1,kData,1,1,true,data,8200,3,{0x5e11,0x5e11}));
    EXPECT_FALSE(binding(Role::Replica,0x5e11,1,kData,1,1,true,data,8200,3,{0xffff,0x5e11}));
}
} // namespace
