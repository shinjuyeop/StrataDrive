#include "diagnostic_channel.hpp"
#include <algorithm>
#include <stdexcept>

namespace stratadrive::someip::diagnostic {
Channel::Channel(Role r,std::uint64_t stream,std::uint32_t registry,Services services)
    :role_(r),stream_(stream),registry_(registry),services_(services) {
    if((r!=Role::Publisher && r!=Role::Replica) || !stream || registry<1 || registry>3 || !valid(services))
        throw std::invalid_argument("diagnostic channel configuration");
}
void Channel::configure(const std::shared_ptr<vsomeip::application>& app) {
    if(app_ || !app) throw std::invalid_argument("diagnostic channel attachment");
    app_=app;
    app_->register_availability_handler(peer(role_,services_),1,[this](auto,auto,bool yes){available_=yes;},1,0);
    app_->register_message_handler(local(role_,services_),1,vsomeip::ANY_METHOD,[this](const auto& message) {
        const auto p=message->get_payload();
        if(!p || !p->get_length() || p->get_length()>diagnostics::wire::kMaxPacket) {++rejected_;return;}
        diagnostics::wire::Bytes bytes(p->get_data(),p->get_data()+p->get_length());
        try {
            const auto decoded=diagnostics::wire::decode(bytes);
            if(!binding(role_,message->get_service(),message->get_instance(),message->get_method(),
                        static_cast<unsigned>(message->get_message_type()),message->get_interface_version(),message->is_reliable(),decoded,stream_,registry_,services_)) {++rejected_;return;}
        } catch(const std::exception&) {++rejected_;return;}
        std::lock_guard<std::mutex> lock(mutex_);
        if(received_.size()==kCapacity) {++dropped_;return;}
        received_.push_back(std::move(bytes));++count_;highwater_=std::max(highwater_.load(),received_.size());
    });
}
void Channel::registered() {
    if(!app_) throw std::logic_error("diagnostic channel not attached");
    app_->offer_service(local(role_,services_),1,1,0);app_->request_service(peer(role_,services_),1,1,0);
}
bool Channel::send(const diagnostics::wire::Bytes& bytes) {
    try {
        const auto decoded=diagnostics::wire::decode(bytes);const auto receiver=role_==Role::Publisher?Role::Replica:Role::Publisher;
        if(!app_ || !binding(receiver,peer(role_,services_),1,role_==Role::Publisher?kData:kAck,1,1,true,decoded,stream_,registry_,services_) || !available()) return false;
    } catch(const std::exception&) {return false;}
    auto message=vsomeip::runtime::get()->create_request(true);
    message->set_service(peer(role_,services_));message->set_instance(1);message->set_interface_version(1);
    message->set_method(role_==Role::Publisher?kData:kAck);message->set_message_type(vsomeip::message_type_e::MT_REQUEST_NO_RETURN);
    auto payload=vsomeip::runtime::get()->create_payload();payload->set_data(bytes);message->set_payload(payload);
    app_->send(message);++sent_;return true;
}
std::optional<diagnostics::wire::Bytes> Channel::pop() {
    std::lock_guard<std::mutex> lock(mutex_);if(received_.empty())return std::nullopt;
    auto bytes=std::move(received_.front());received_.pop_front();return bytes;
}
Channel::Stats Channel::stats() const noexcept {return {count_.load(),rejected_.load(),sent_.load(),dropped_.load(),highwater_.load()};}
} // namespace stratadrive::someip::diagnostic
