from typing import Dict, List, Tuple, Optional
import collections

class GraphCycleError(ValueError): pass
class GraphIntegrityError(ValueError): pass

def topological_sort(vertices: List[str], edges: List[Tuple[str, str]]) -> List[str]:
    """Time Complexity: O(V+E). Safe Kahn's Algorithm for DAGs."""
    vertex_set = set(vertices)
    for u, v in edges:
        if u not in vertex_set or v not in vertex_set:
            raise GraphIntegrityError(f"Edge ({u} -> {v}) references undefined vertex.")

    in_degree = {v: 0 for v in vertices}
    graph = collections.defaultdict(list)

    for u, v in edges:
        graph[u].append(v)
        in_degree[v] += 1

    queue = collections.deque([v for v in vertices if in_degree[v] == 0])
    sorted_order = []

    while queue:
        u = queue.popleft()
        sorted_order.append(u)
        for neighbor in graph[u]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_order) != len(vertices):
        raise GraphCycleError("Hallucinated cyclic dependency detected.")
    return sorted_order

class TrieNode:
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.is_end_of_command: bool = False
        self.command_action: Optional[str] = None

class FastPathRouter:
    """O(L) Routing to bypass LLM inference."""
    def __init__(self):
        self.root = TrieNode()
        self._initialize_defaults()

    def _initialize_defaults(self):
        self.insert("stop", "ACTION_HALT_ALL")
        self.insert("stop jarvis", "ACTION_HALT_ALL")
        self.insert("status", "ACTION_GET_METRICS")

    def insert(self, word: str, action: str):
        node = self.root
        for char in word.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_command = True
        node.command_action = action

    def search(self, word: str) -> Optional[str]:
        node = self.root
        for char in word.lower():
            if char not in node.children:
                return None
            node = node.children[char]
        return node.command_action if node.is_end_of_command else None

router = FastPathRouter()