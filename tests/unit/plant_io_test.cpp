#include "../../simulation/runtime/plant_io.hpp"
#include <gtest/gtest.h>
#include <filesystem>

namespace {
using namespace stratadrive::simulation;
class PlantIOTest : public ::testing::Test {
protected:
    std::string path;
    int blocker=-1;
    void SetUp() override {
        char name[]="/tmp/stratadrive-plant-XXXXXX";
        const int fd=mkstemp(name);ASSERT_GE(fd,0);close(fd);unlink(name);path=name;
    }
    void TearDown() override {if(blocker>=0)close(blocker);std::filesystem::remove(path);}
    void lock(std::size_t offset,std::size_t length) {
        blocker=open(path.c_str(),O_RDWR|O_CLOEXEC);ASSERT_GE(blocker,0);
        struct flock value{};value.l_type=F_WRLCK;value.l_whence=SEEK_SET;
        value.l_start=static_cast<off_t>(offset);value.l_len=static_cast<off_t>(length);
        ASSERT_EQ(fcntl(blocker,F_OFD_SETLK,&value),0);
    }
};
TEST_F(PlantIOTest, BusySensorDoesNotDelayBrakeOutputOrRelease) {
    PlantIO plant(path,true),front(path),central(path);
    lock(offsetof(PlantState,sensors),sizeof(OwnerSensors));
    EXPECT_FALSE(front.read_sensors());
    OwnerActuation output;output.epoch=3;output.source_ns=101;
    ASSERT_TRUE(front.write_output(1,output));
    ASSERT_TRUE(central.write_release(3));
    ASSERT_TRUE(plant.read_output(1));EXPECT_EQ(plant.read_output(1)->source_ns,101U);
    EXPECT_EQ(plant.read_release(),3U);EXPECT_EQ(front.busy,1U);EXPECT_EQ(front.errors,0U);
}
TEST_F(PlantIOTest, BusyRearOutputDoesNotBlockFrontOrSensorPublication) {
    PlantIO plant(path,true),front(path),rear(path);
    lock(offsetof(PlantState,outputs)+2*sizeof(OwnerActuation),sizeof(OwnerActuation));
    OwnerActuation output;output.epoch=4;output.source_ns=200;
    EXPECT_FALSE(rear.write_output(2,output));
    EXPECT_FALSE(plant.read_output(2));
    EXPECT_TRUE(front.write_output(1,output));
    OwnerSensors sensors;sensors.source_ns=201;EXPECT_TRUE(plant.write_sensors(sensors));
    ASSERT_TRUE(front.read_sensors());EXPECT_EQ(front.read_sensors()->source_ns,201U);
}
TEST_F(PlantIOTest, RetryingBusyFieldPreservesOriginalIdentityAndOtherWriters) {
    PlantIO plant(path,true),front(path),rear(path);
    OwnerActuation old;old.epoch=2;old.source_ns=100;ASSERT_TRUE(front.write_output(1,old));
    lock(offsetof(PlantState,outputs)+sizeof(OwnerActuation),sizeof(OwnerActuation));
    OwnerActuation next;next.epoch=3;next.source_ns=200;
    next.brake=stratadrive::brake::Actuation{stratadrive::brake::ActuationMode::Target,500000,199};
    EXPECT_FALSE(front.write_output(1,next));
    ASSERT_TRUE(rear.write_output(2,old));
    close(blocker);blocker=-1;
    ASSERT_TRUE(plant.read_output(1));EXPECT_EQ(plant.read_output(1)->source_ns,100U);
    ASSERT_TRUE(front.write_output(1,next));
    const auto result=plant.read_output(1);ASSERT_TRUE(result);ASSERT_TRUE(result->brake);
    EXPECT_EQ(result->epoch,3U);EXPECT_EQ(result->source_ns,200U);EXPECT_EQ(result->brake->issued_time_ns,199U);
    EXPECT_EQ(plant.read_output(2)->source_ns,100U);
}
TEST_F(PlantIOTest, InvalidSlotAndTruncatedTransferFailWithoutKeepingLock) {
    PlantIO plant(path,true),front(path);
    EXPECT_THROW(front.read_output(5),std::out_of_range);
    EXPECT_EQ(truncate(path.c_str(),offsetof(PlantState,outputs)),0);
    EXPECT_THROW(front.read_output(1),std::runtime_error);EXPECT_EQ(front.errors,1U);
    OwnerActuation output;output.source_ns=100;
    EXPECT_TRUE(plant.write_output(1,output));
    ASSERT_TRUE(front.read_output(1));EXPECT_EQ(front.read_output(1)->source_ns,100U);
}
}
