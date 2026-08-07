import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

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
    this.isBuiltIn = false,
  });

  /// Node that requires [dependencyId] to function.
  final String dependentId;
  final String dependencyId;
  final String reason;
  final bool isBuiltIn;

  String get key => '$dependentId>$dependencyId';

  Map<String, Object> toJson() => {
        'dependent_id': dependentId,
        'dependency_id': dependencyId,
        'reason': reason,
      };

  static DependencyEdge? fromJson(Object? value) {
    if (value is! Map<String, dynamic>) return null;
    final dependentId = value['dependent_id'] as String?;
    final dependencyId = value['dependency_id'] as String?;
    final reason = value['reason'] as String?;
    if (dependentId == null || dependencyId == null || reason == null) return null;
    return DependencyEdge(
      dependentId: dependentId,
      dependencyId: dependencyId,
      reason: reason,
    );
  }
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

class DependencyGraphException implements Exception {
  const DependencyGraphException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Deterministic dependency registry used by the SirisOS Digital Twin.
///
/// Built-in edges represent relationships SirisOS knows from its own
/// architecture. User-defined edges are explicit topology declarations and
/// are persisted locally. Physical power/network dependencies are never
/// inferred from simultaneous failures.
class DependencyGraph {
  DependencyGraph._();

  static final DependencyGraph instance = DependencyGraph._();
  static const _storageKey = 'sirisos.digital_twin.custom_edges.v1';

  bool _loaded = false;
  final List<DependencyEdge> _customEdges = [];

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

  static const List<DependencyEdge> _builtInEdges = [
    DependencyEdge(
      dependentId: 'hyper_backup',
      dependencyId: 'synology',
      reason: 'Hyper Backup runs on Synology DSM and cannot operate when the NAS is unavailable.',
      isBuiltIn: true,
    ),
    DependencyEdge(
      dependentId: 'backup_analytics',
      dependencyId: 'hyper_backup',
      reason: 'Backup Protection Analytics requires observed Hyper Backup completion data.',
      isBuiltIn: true,
    ),
  ];

  List<DependencyNode> get nodes => _nodes;
  List<DependencyEdge> get builtInEdges => _builtInEdges;
  List<DependencyEdge> get customEdges => List.unmodifiable(_customEdges);
  List<DependencyEdge> get edges => List.unmodifiable([..._builtInEdges, ..._customEdges]);
  bool get isLoaded => _loaded;

  Future<void> load() async {
    if (_loaded) return;
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_storageKey);
    _customEdges.clear();
    if (raw != null && raw.isNotEmpty) {
      try {
        final decoded = jsonDecode(raw);
        if (decoded is List) {
          for (final item in decoded) {
            final edge = item is Map
                ? DependencyEdge.fromJson(Map<String, dynamic>.from(item))
                : null;
            if (edge != null && _isValidStoredEdge(edge)) {
              _customEdges.add(edge);
            }
          }
        }
      } catch (_) {
        // Invalid stored topology degrades to built-in defaults.
      }
    }
    _loaded = true;
  }

  Future<void> addCustomEdge({
    required String dependentId,
    required String dependencyId,
    String? reason,
  }) async {
    await load();
    if (dependentId == dependencyId) {
      throw const DependencyGraphException('A component cannot depend on itself.');
    }
    if (node(dependentId) == null || node(dependencyId) == null) {
      throw const DependencyGraphException('Both topology components must exist.');
    }
    final candidate = DependencyEdge(
      dependentId: dependentId,
      dependencyId: dependencyId,
      reason: reason?.trim().isNotEmpty == true
          ? reason!.trim()
          : '${node(dependentId)!.label} depends on ${node(dependencyId)!.label}.',
    );
    if (edges.any((edge) => edge.key == candidate.key)) return;
    if (_wouldCreateCycle(candidate)) {
      throw const DependencyGraphException('That dependency would create a topology cycle.');
    }
    _customEdges.add(candidate);
    await _persist();
  }

  Future<void> removeCustomEdge(String key) async {
    await load();
    _customEdges.removeWhere((edge) => edge.key == key);
    await _persist();
  }

  Future<void> resetCustomEdges() async {
    await load();
    _customEdges.clear();
    await _persist();
  }

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
      final nextEdges = edges.where((edge) => edge.dependencyId == current.id);
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

  bool _isValidStoredEdge(DependencyEdge edge) {
    if (edge.dependentId == edge.dependencyId) return false;
    if (node(edge.dependentId) == null || node(edge.dependencyId) == null) return false;
    if (_builtInEdges.any((item) => item.key == edge.key)) return false;
    if (_customEdges.any((item) => item.key == edge.key)) return false;
    return !_wouldCreateCycle(edge);
  }

  bool _wouldCreateCycle(DependencyEdge candidate) {
    final working = [..._builtInEdges, ..._customEdges, candidate];
    final visited = <String>{};
    final active = <String>{};

    bool visit(String id) {
      if (active.contains(id)) return true;
      if (!visited.add(id)) return false;
      active.add(id);
      for (final edge in working.where((item) => item.dependencyId == id)) {
        if (visit(edge.dependentId)) return true;
      }
      active.remove(id);
      return false;
    }

    return _nodes.any((item) => visit(item.id));
  }

  Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _storageKey,
      jsonEncode(_customEdges.map((edge) => edge.toJson()).toList(growable: false)),
    );
  }
}
