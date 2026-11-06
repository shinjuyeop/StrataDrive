#include "diagnostic_transport.hpp"
#include <algorithm>
#include <stdexcept>

namespace stratadrive::someip::diagnostic {
Transport::Transport(Role r,std::uint64_t stream,std::uint32_t registry,const std::string& name)
    :role_(r),stream_(stream),registry_(registry),app_(vsomeip::runtime::get()->create_application(name)) {
    if((r!=Role::Publisher && r!=Role::Replica) || !stream || registry<1 || registry>4 || name.empty() || !app_) throw std::invalid_argument("diagnostic SDK configuration");
}
Transport::~Transport() { stop(); }
void Transport::start() {
    if(dispatch_.joinable() || !app_->init()) throw std::runtime_error("diagnostic SDK init");
    app_->register_state_handler([this](auto state) {
        if(state==vsomeip::state_type_e::ST_REGISTERED) { app_->offer_service(local(role_),1,1,0); app_->request_service(peer(role_),1,1,0); }
    });
    app_->register_availability_handler(peer(role_),1,[this](auto,auto,bool yes){available_=yes;},1,0);
    app_->register_message_handler(local(role_),1,vsomeip::ANY_METHOD,[this](const auto& message) {
        const auto p=message->get_payload();
        if(!p || !p->get_length() || p->get_length()>diagnostics::wire::kMaxPacket) { ++rejected_; return; }
        diagnostics::wire::Bytes bytes(p->get_data(),p->get_data()+p->get_length());
        try {
            const auto decoded=diagnostics::wire::decode(bytes);
            if(!binding(role_,message->get_service(),message->get_instance(),message->get_method(),
                        static_cast<unsigned>(message->get_message_type()),message->get_interface_version(),message->is_reliable(),decoded,stream_,registry_)) { ++rejected_; return; }
        } catch(const std::exception&) { ++rejected_; return; }
        std::lock_guard<std::mutex> lock(mutex_);
        if(received_.size()==kCapacity) { ++dropped_; return; }
        received_.push_back(std::move(bytes)); ++count_; highwater_=std::max(highwater_.load(),received_.size());
    });
    dispatch_=std::thread([this]{app_->start();});
}
bool Transport::send(const diagnostics::wire::Bytes& bytes) {
    try {
        const auto decoded=diagnostics::wire::decode(bytes);
        const auto receiver=role_==Role::Publisher?Role::Replica:Role::Publisher;
        if(!binding(receiver,peer(role_),1,role_==Role::Publisher?kData:kAck,1,1,true,decoded,stream_,registry_) || !available()) return false;
    } catch(const std::exception&) { return false; }
    auto message=vsomeip::runtime::get()->create_request(true);
    message->set_service(peer(role_)); message->set_instance(1); message->set_interface_version(1);
    message->set_method(role_==Role::Publisher?kData:kAck); message->set_message_type(vsomeip::message_type_e::MT_REQUEST_NO_RETURN);
    auto payload=vsomeip::runtime::get()->create_payload(); payload->set_data(bytes); message->set_payload(payload);
    app_->send(message); ++sent_; return true;
}
std::optional<diagnostics::wire::Bytes> Transport::pop() {
    std::lock_guard<std::mutex> lock(mutex_); if(received_.empty()) return std::nullopt;
    auto bytes=std::move(received_.front()); received_.pop_front(); return bytes;
}
Transport::Stats Transport::stats() const noexcept { return {count_.load(),rejected_.load(),sent_.load(),dropped_.load(),highwater_.load()}; }
void Transport::stop() {
    if(!dispatch_.joinable()) return;
    app_->stop_offer_service(local(role_),1,1,0); app_->release_service(peer(role_),1); app_->clear_all_handler(); app_->stop(); dispatch_.join(); available_=false;
}
} // namespace stratadrive::someip::diagnostic
