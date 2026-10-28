"""Cancel queued sync RPC waits before joining RPC workers at owner shutdown.

Stop/SyncRunFor are serialized on the game-thread owner; no restart supported.
Never run queued game/physics callbacks merely to unblock shutdown.
"""


def apply(base, replace):
    path = "LibCarla/source/carla/rpc/Server.h"
    text = replace(base(path), "#include <future>",
                   "#include <future>\n#include <atomic>\n#include <chrono>\n#include <stdexcept>")
    text = replace(text, "    void Stop() {\n      _server.stop();", """    void Stop() {
      // M7: game-thread owner has stopped dispatching callbacks. RPC workers
      // may still wait on that owner; cancel waits BEFORE joining the workers.
      _stopping.store(true, std::memory_order_release);
      _server.stop();""")
    text = replace(text, "    ::rpc::server _server;", """    // Declared before _server: survives worker destruction and queued tasks.
    std::atomic<bool> _stopping{false};
    ::rpc::server _server;""")
    text = replace(text, "    static auto WrapSyncCall(boost::asio::io_context &io, FuncT &&functor) {\n      return [&io, functor=std::forward<FuncT>(functor)](Metadata metadata, Args... args) -> R {",
                   """    static auto WrapSyncCall(boost::asio::io_context &io, std::atomic<bool> &stopping, FuncT &&functor) {
      return [&io, &stopping, functor=std::forward<FuncT>(functor)](Metadata metadata, Args... args) -> R {
        if (stopping.load(std::memory_order_acquire))
          throw std::runtime_error("CARLA RPC server stopping");""")
    text = replace(text, "        auto task = std::packaged_task<R()>([functor=std::move(functor), args...]() {\n          return functor(args...);",
                   """        auto task = std::packaged_task<R()>([&stopping, functor=std::move(functor), args...]() {
          if (stopping.load(std::memory_order_acquire))
            throw std::runtime_error("CARLA RPC server stopping");
          return functor(args...);""")
    text = replace(text, "          return result.get();", """          while (result.wait_for(std::chrono::milliseconds(1)) != std::future_status::ready) {
            if (stopping.load(std::memory_order_acquire))
              throw std::runtime_error("CARLA RPC server stopping");
          }
          return result.get();""")
    text = replace(text, "Wrapper::WrapSyncCall(_sync_io_context, std::forward<FunctorT>(functor))",
                   "Wrapper::WrapSyncCall(_sync_io_context, _stopping, std::forward<FunctorT>(functor))")
    return {path: text.encode()}
