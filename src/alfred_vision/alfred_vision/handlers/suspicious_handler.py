class SuspiciousHandler:
    def __init__(self, node, ns: str, **_kwargs):
        self._node = node
        self._ns   = ns

    def is_active(self) -> bool:
        return False

    def handle(self, payload: dict):
        cls = payload.get('class', '?')
        loc = payload.get('location', {})
        x   = loc.get('x')
        y   = loc.get('y')
        self._node.get_logger().info(
            f'[{self._ns}] 위험물 감지: {cls} @ ({x}, {y})')
