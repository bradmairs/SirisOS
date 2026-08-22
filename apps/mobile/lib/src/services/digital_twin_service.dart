import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../core/dependency_graph.dart';
import 'auth_service.dart';

/// HTTP layer for the Digital Twin's server-side canonical topology
/// (`apps/backend/app/api/digital_twin.py`). `DependencyGraph` (core) still
/// owns the node catalog, cycle/self/duplicate validation and downstream
/// impact traversal -- this only persists/reads custom edges, replacing the
/// local `SharedPreferences` store the topology previously lived in so the
/// same topology is visible from any session against this backend, not just
/// the device that declared it.
class DigitalTwinService {
  Future<List<DependencyEdge>> fetchCustomEdges() async {
    final response = await http
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/digital-twin/topology'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw DigitalTwinServiceException(
        'Unable to load Digital Twin topology (${response.statusCode}).',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const DigitalTwinServiceException('Digital Twin topology response was not an object.');
    }
    final customEdges = decoded['custom_edges'];
    if (customEdges is! List) return const [];
    return customEdges.map(DependencyEdge.fromJson).whereType<DependencyEdge>().toList(growable: false);
  }

  Future<DependencyEdge> addEdge({
    required String dependentId,
    required String dependencyId,
    String? reason,
  }) async {
    final response = await http
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/digital-twin/edges'),
          headers: {
            ...AuthService.authorizationHeaders,
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'dependent_id': dependentId,
            'dependency_id': dependencyId,
            'reason': reason,
          }),
        )
        .timeout(const Duration(seconds: 12));
    final decoded = jsonDecode(response.body.isEmpty ? '{}' : response.body);
    if (response.statusCode != 200) {
      throw DigitalTwinServiceException(
        decoded is Map<String, dynamic>
            ? decoded['detail'] as String? ?? 'Unable to add dependency.'
            : 'Unable to add dependency.',
      );
    }
    final edge = decoded is Map<String, dynamic> ? DependencyEdge.fromJson(decoded) : null;
    if (edge == null) {
      throw const DigitalTwinServiceException('Digital Twin edge response was malformed.');
    }
    return edge;
  }

  Future<void> removeEdge(String key) async {
    final response = await http
        .delete(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/digital-twin/edges/${Uri.encodeComponent(key)}'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw DigitalTwinServiceException(
        'Unable to remove dependency (${response.statusCode}).',
      );
    }
  }

  Future<void> resetEdges() async {
    final response = await http
        .delete(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/digital-twin/edges'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw DigitalTwinServiceException(
        'Unable to reset topology (${response.statusCode}).',
      );
    }
  }
}

class DigitalTwinServiceException implements Exception {
  const DigitalTwinServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
