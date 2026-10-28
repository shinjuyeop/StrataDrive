// Exercise the actual pinned CARLA RPC wrapper, including the worker join.
#include <carla/rpc/Server.h>
#include <rpc/client.h>
#include <atomic>
#include <chrono>
#include <iostream>
#include <thread>
#include <vector>
using namespace std::chrono_literals;
void require(bool value) { if (!value) throw std::runtime_error("assertion failed"); }
template<class F> auto wrap(boost::asio::io_context& io, std::atomic<bool>& stop, F f) {
#ifdef PATCHED
  return carla::rpc::detail::FunctionWrapper<F>::WrapSyncCall(io, stop, f);
#else
  (void)stop;
  return carla::rpc::detail::FunctionWrapper<F>::WrapSyncCall(io, f);
#endif
}
int main(int argc, char** argv) {
  const std::string mode = argc > 1 ? argv[1] : "";
  boost::asio::io_context io;
  std::atomic<bool> stop{false};
  std::atomic<unsigned> calls{0};
  const auto owner = std::this_thread::get_id();
  auto f = wrap(io, stop, [&] { require(std::this_thread::get_id()==owner); ++calls; return 42; });
  if (mode=="normal") {
    auto result=std::async(std::launch::async,[&]{return f(carla::rpc::Metadata::MakeSync());});
    while(result.wait_for(0ms)!=std::future_status::ready) {io.reset();io.poll();std::this_thread::yield();}
    require(result.get()==42 && calls==1);
  } else if(mode=="queued") {
    std::vector<std::future<bool>> workers;
    for(unsigned i=0;i<32;++i) workers.push_back(std::async(std::launch::async,[&]{
      try {f(carla::rpc::Metadata::MakeSync());return false;} catch(const std::runtime_error&){return true;}
    }));
    std::this_thread::sleep_for(20ms);
    require(calls==0);
    stop.store(true);
    for(auto& result:workers)require(result.get());
    io.reset();io.poll(); // queued mutation must never run, even if pumped later
    require(calls==0);
  } else if(mode=="ignored") {
    f(carla::rpc::Metadata::MakeAsync()); stop.store(true); io.poll();require(calls==0);
  } else if(mode=="late") {
    stop.store(true);bool rejected=false;
    try {f(carla::rpc::Metadata::MakeAsync());} catch(const std::runtime_error&){rejected=true;}
    io.poll();require(rejected && calls==0);
  } else if(mode=="network") {
    // Caller reserves an isolated port; no UE server is involved.
    require(argc==3);
    carla::rpc::Server server("127.0.0.1",static_cast<uint16_t>(std::stoul(argv[2])));
    server.BindSync("pending",[&]{++calls;return 42;});server.AsyncRun(2);
    rpc::client client("127.0.0.1",static_cast<uint16_t>(std::stoul(argv[2])));
    auto pending=client.async_call("pending",carla::rpc::Metadata::MakeSync());
    std::this_thread::sleep_for(100ms);require(pending.wait_for(0ms)!=std::future_status::ready);
    server.Stop();require(calls==0); // no SyncRunFor: reproduces cold-loading stop
    server.Stop();
  } else throw std::runtime_error("unknown case");
  std::cout<<mode<<" PASS callbacks="<<calls<<'\n';
}
