class LostItemHandler:
    def __init__(self, node, ns: str):
        self._node = node
        self._ns   = ns

    def is_active(self) -> bool:
        return False

    def handle(self, payload: dict):
        cls  = payload.get('class', '?')
        conf = payload.get('confidence', 0)
        self._node.get_logger().info(f'[{self._ns}] 유실물 감지: {cls} (conf={conf})')
