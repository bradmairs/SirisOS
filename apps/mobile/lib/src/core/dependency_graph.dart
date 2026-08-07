class DependencyNode {
  const DependencyNode({
    required this.id,
    required this.label,
    required this.kind,
    this.description,
  });

  final String id;
  final String label;
  final String kind;
  final String? description;
}

class DependencyEdge {
  const DependencyEdge({
    required this.dependentId,
    required this.dependencyId,
    required this.reason,
  });

  /// Node that requires [dependencyId] to function.
  final String dependentId;
  final String dependencyId;
  final String reason;
}

class DependencyImpact {
  const DependencyImpact({
    required this.node,
    required this.path,
    required this.reason,
  });

  final DependencyNode node;
  final List<String> path;
  final String reason;
}

/// Deterministic dependency registry used by the SirisOS Digital Twin.
///
/// Only explicit, known relationships belong here. Physical power/network
/// dependencies must not be guessed from simultaneous failures.
class DependencyGraph {
  DependencyGraph._();

  static final DependencyGraph instance = DependencyGraph._();

  static const List<DependencyNode> _nodes = [
    DependencyNode(id: 'ups', label: 'UPS', kind: 'power'),
    DependencyNode(id: 'docker', label: 'Docker', kind: 'compute'),
    DependencyNode(id: 'synology', label: 'Synology', kind: 'storage'),
    DependencyNode(id: 'hyper_backup', label: 'Hyper Backup', kind: 'backup'),
    DependencyNode(id: 'backup_analytics', label: 'Backup Protection Analytics', kind: 'analytics'),
    DependencyNode(id: 'home_assistant', label: 'Home Assistant', kind: 'automation'),
    DependencyNode(id: 'unifi', label: 'UniFi', kind: 'network'),
    DependencyNode(id: 'prometheus', label: 'Prometheus', kind: 'observability'),
    DependencyNode(id: 'grafana', label: 'Grafana', kind: 'observability'),
  ];

  static const List<DependencyEdge> _edges = [
    DependencyEdge(
      dependentId: 'hyper_backup',
      dependencyId: 'synology',
      reason: 'Hyper Backup runs on Synology DSM and cannot operate when the NAS is unavailable.',
    ),
    DependencyEdge(
      dependentId: 'backup_analytics',
      dependencyId: 'hyper_backup',
      reason: 'Backup Protection Analytics requires observed Hyper Backup completion data.',
    ),
  ];

  List<DependencyNode> get nodes => _nodes;
  List<DependencyEdge> get edges => _edges;

  DependencyNode? node(String id) {
    for (final item in _nodes) {
      if (item.id == id) return item;
    }
    return null;
  }

  List<DependencyImpact> downstreamImpacts(String dependencyId) {
    final impacts = <DependencyImpact>[];
    final visited = <String>{dependencyId};
    final queue = <({String id, List<String> path})>[
      (id: dependencyId, path: [dependencyId]),
    ];

    while (queue.isNotEmpty) {
      final current = queue.removeAt(0);
      final nextEdges = _edges.where((edge) => edge.dependencyId == current.id);
      for (final edge in nextEdges) {
        if (!visited.add(edge.dependentId)) continue;
        final path = [...current.path, edge.dependentId];
        final dependent = node(edge.dependentId);
        if (dependent != null) {
          impacts.add(
            DependencyImpact(node: dependent, path: path, reason: edge.reason),
          );
        }
        queue.add((id: edge.dependentId, path: path));
      }
    }

    return impacts;
  }

  List<DependencyImpact> downstreamForMany(Iterable<String> dependencyIds) {
    final byNode = <String, DependencyImpact>{};
    for (final id in dependencyIds) {
      for (final impact in downstreamImpacts(id)) {
        final existing = byNode[impact.node.id];
        if (existing == null || impact.path.length < existing.path.length) {
          byNode[impact.node.id] = impact;
        }
      }
    }
    final result = byNode.values.toList(growable: false)
      ..sort((a, b) => a.node.label.compareTo(b.node.label));
    return result;
  }
}
