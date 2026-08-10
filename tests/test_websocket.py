import asyncio
from app.routers.ws import ConnectionManager

class MockWebSocket:
    def __init__(self, should_fail=False):
        self.accepted = False
        self.sent_messages = []
        self.should_fail = should_fail

    async def accept(self):
        self.accepted = True

    async def send_text(self, text: str):
        if self.should_fail:
            raise RuntimeError("Socket disconnected")
        self.sent_messages.append(text)

def test_connection_manager_lifecycle():
    async def _run():
        manager = ConnectionManager()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await manager.connect(ws1)
        await manager.connect(ws2)
        assert len(manager.active_connections) == 2

        # Broadcast message
        await manager.broadcast({"type": "test_event", "data": "hello"})
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1

        # Disconnect one
        await manager.disconnect(ws1)
        assert len(manager.active_connections) == 1
        assert ws2 in manager.active_connections

    asyncio.run(_run())

def test_connection_manager_prune_dead():
    async def _run():
        manager = ConnectionManager()
        good_ws = MockWebSocket(should_fail=False)
        broken_ws = MockWebSocket(should_fail=True)

        await manager.connect(good_ws)
        await manager.connect(broken_ws)
        assert len(manager.active_connections) == 2

        # Broadcast should automatically prune broken_ws
        await manager.broadcast({"type": "ping"})
        assert len(manager.active_connections) == 1
        assert good_ws in manager.active_connections

    asyncio.run(_run())
