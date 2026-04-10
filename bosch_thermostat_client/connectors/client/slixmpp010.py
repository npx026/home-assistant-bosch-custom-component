from slixmpp import ClientXMPP


class BoschClientXMPP(ClientXMPP):

    def __init__(self, jid, password, ca_certs, use_ssl=True, force_starttls=True, disable_starttls=False, **kwargs):
        ClientXMPP.__init__(self, jid=jid, password=password, **kwargs)
        self.ca_certs = ca_certs
        self.use_ssl = use_ssl
        self.force_starttls = force_starttls
        self.disable_starttls = disable_starttls

    def connect(self):
        if self.force_starttls:
            return super().connect(enable_direct_tls=True, enable_starttls=True)
        return super().connect()