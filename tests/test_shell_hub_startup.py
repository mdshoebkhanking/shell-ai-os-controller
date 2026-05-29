import shell_hub


def test_pick_available_port_probes_actual_loopback_host(monkeypatch):
    binds = []

    class FakeSocket:
        def __init__(self, family, sock_type):
            self.family = family
            self.sock_type = sock_type

        def bind(self, address):
            binds.append(address)

        def close(self):
            return None

    monkeypatch.setattr(shell_hub, "_candidate_ports", lambda: [5000])
    monkeypatch.setattr(shell_hub.socket, "socket", lambda family, sock_type: FakeSocket(family, sock_type))

    assert shell_hub._pick_available_port("localhost") == 5000
    assert binds == [("127.0.0.1", 5000)]
