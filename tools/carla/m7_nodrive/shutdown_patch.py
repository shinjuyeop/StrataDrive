"""Narrow lifecycle fix for the pinned CARLA multigpu server (M7-1s).

Stop is an owner-thread operation: producers must be quiescent; it must not be
called by an I/O worker or concurrently with another lifecycle call. Restart
requires a new Router. No physics, wire, scheduling, or actuation changes.
"""


def apply(base, replace):
    out = {}
    path = "LibCarla/source/carla/multigpu/router.cpp"
    text = replace(base(path), """void Router::Stop() {
  ClearSessions();
  _listener->Stop();
  _listener.reset();
  _pool.Stop();
}""", """void Router::Stop() {
  // M7-1s: join every handler before mutating the shared acceptor/sessions.
  // Owner thread only, after external producers are quiescent. No restart.
  _pool.Stop();
  if (_listener) {
    _listener->Stop();
    _listener.reset();
  }
  ClearSessions();
  _promises.clear();
  // PrimaryCommands otherwise keeps this Router alive after the owner exits.
  _commander.set_router(nullptr);
}""")
    out[path] = text.encode()
    path = "LibCarla/source/carla/multigpu/listener.cpp"
    text = replace(base(path), """    _acceptor.cancel();
    _acceptor.close();
    _io_context.stop();
    _io_context.reset();""", """    // The owner has stopped and joined all io_context workers first.
    // Never restart an io_context during shutdown; cancellation is terminal.
    boost::system::error_code ec;
    _acceptor.cancel(ec);
    _acceptor.close(ec);""")
    text = replace(text, """      // Handle query and open a new session immediately.
      boost::asio::post(_io_context, [=]() { handle_query(ec); });
      OpenSession(timeout, on_opened, on_closed, on_response);""", """      // A cancelled/failed accept must not start another accept.
      if (ec) {
        if (ec != boost::asio::error::operation_aborted)
          log_error("Secondary server:", ec.message());
        return;
      }
      boost::asio::post(self->_io_context, [=]() { handle_query(ec); });
      self->OpenSession(timeout, on_opened, on_closed, on_response);""")
    out[path] = text.encode()
    path = "LibCarla/source/carla/multigpu/listener.h"
    text = replace(base(path), """      boost::asio::post(_io_context, [=]() {
        OpenSession(""", """      auto self = shared_from_this();
      boost::asio::post(_io_context, [=]() {
        self->OpenSession(""")
    text = replace(text, """            _timeout,
""", """            self->_timeout,
""")
    text = replace(text, "    void Stop();", """    // Owner only: stop/join io_context workers before calling. Terminal and
    // repeatable; no concurrent Listen/Stop or subsequent restart supported.
    void Stop();""")
    out[path] = text.encode()
    return out
