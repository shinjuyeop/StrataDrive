// Exercise the real pinned LibCarla networking classes, without UE or physics.
#include "carla/multigpu/listener.h"
#include "carla/multigpu/router.h"
#include <boost/asio/connect.hpp>
#include <atomic>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <thread>

using tcp = boost::asio::ip::tcp;
using carla::multigpu::Listener;
using carla::multigpu::Router;

static void require(bool condition, const char *message) {
  if (!condition) throw std::runtime_error(message);
}

int main(int argc, char **argv) {
  const std::string mode = argc > 1 ? argv[1] : "";
  const int repeats = argc > 2 ? std::stoi(argv[2]) : 1;
  try {
    if (mode == "cancel") {
      boost::asio::io_context io;
      auto listener = std::make_shared<Listener>(io, tcp::endpoint(tcp::v4(), 0));
      listener->Listen([](Listener::Session) {}, [](Listener::Session) {},
                       [](Listener::Session, carla::Buffer) {});
      require(io.poll_one() == 1, "accept was not registered");
      // No run/poll call is active here. Drain cancellation only after Stop.
      io.stop();
      listener->Stop();
      io.restart();
      unsigned completions = 0;
      while (completions < 32 && io.poll_one()) ++completions;
      std::cout << "cancel completions=" << completions << std::endl;
      require(completions == 1, "cancelled accept rearmed on a closed descriptor");
      io.stop();
      listener->Stop();
    } else if (mode == "empty" || mode == "double") {
      auto router = mode == "empty" ? std::make_shared<Router>() : std::make_shared<Router>(0);
      router->Stop();
      router->Stop();
      router.reset();
    } else if (mode == "stress" || mode == "connected" || mode == "lifetime") {
      unsigned released = 0, connections = 0;
      for (int i = 0; i < repeats; ++i) {
        // Reserve a loopback port; Router stores its input endpoint, so port=0
        // cannot be queried after construction. Refuse a bind collision.
        boost::asio::io_context io;
        tcp::acceptor reserve(io, tcp::endpoint(tcp::v4(), 0));
        const auto port = reserve.local_endpoint().port();
        reserve.close();
        auto router = std::make_shared<Router>(port);
        std::weak_ptr<Router> weak = router;
        std::atomic<bool> connected{false};
        router->SetNewConnectionCallback([&] { connected.store(true); });
        router->SetCallbacks();
        router->AsyncRun(4);
        tcp::socket peer(io);
        if (mode == "connected") {
          peer.connect(tcp::endpoint(boost::asio::ip::address_v4::loopback(), port));
          const auto until = std::chrono::steady_clock::now() + std::chrono::seconds(2);
          while (!connected.load() && std::chrono::steady_clock::now() < until)
            std::this_thread::yield();
          require(connected.load(), "real secondary connection not accepted");
          ++connections;
        } else {
          std::this_thread::sleep_for(std::chrono::microseconds(i % 50));
        }
        router->Stop();
        if (mode != "stress") router->Stop();
        router.reset();
        if (weak.expired()) ++released;
        boost::system::error_code ec;
        peer.close(ec);
        tcp::acceptor rebound(io, tcp::endpoint(tcp::v4(), port));
        if ((i+1) % 100 == 0) std::cout << "completed=" << i+1 << std::endl;
      }
      std::cout << "iterations=" << repeats << " released=" << released
                << " connected=" << connections << std::endl;
      require(released == static_cast<unsigned>(repeats), "Router self-cycle leaked at Stop");
    } else {
      throw std::runtime_error("unknown case");
    }
    std::cout << "PASS " << mode << std::endl;
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "FAIL " << mode << ": " << error.what() << std::endl;
    return 1;
  }
}
