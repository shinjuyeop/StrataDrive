// Compile-only boundary: this target has no gateway/controller include paths.
#include "owner_messages.hpp"
#include "session_reset.hpp"
#include <type_traits>
static_assert(std::is_nothrow_copy_constructible_v<stratadrive::transport::ZoneRequest>);
static_assert(std::is_nothrow_copy_constructible_v<stratadrive::transport::LeafRequest>);
static_assert(std::is_nothrow_copy_constructible_v<stratadrive::simulation::SessionResetEvidence>);
