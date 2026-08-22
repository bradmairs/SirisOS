import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';

enum IncidentLifecycleStatus { open, acknowledged, resolved }

extension IncidentLifecycleStatusValue on IncidentLifecycleStatus {
  String get apiValue => name;

  static IncidentLifecycleStatus fromApiValue(String value) =>
      IncidentLifecycleStatus.values.firstWhere(
        (item) => item.apiValue == value,
        orElse: () => IncidentLifecycleStatus.open,
      );
}

class IncidentLifecycleRecord {
  const IncidentLifecycleRecord({
    required this.id,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
    this.assignedTo,
    this.notes,
    this.acknowledgedAt,
    this.resolvedAt,
  });

  final String id;
  final IncidentLifecycleStatus status;
  final String? assignedTo;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? acknowledgedAt;
  final DateTime? resolvedAt;

  factory IncidentLifecycleRecord.fromJson(Map<String, dynamic> json) =>
      IncidentLifecycleRecord(
        id: json['id'] as String,
        status: IncidentLifecycleStatusValue.fromApiValue(json['status'] as String),
        assignedTo: json['assigned_to'] as String?,
        notes: json['notes'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
        acknowledgedAt: json['acknowledged_at'] == null
            ? null
            : DateTime.parse(json['acknowledged_at'] as String),
        resolvedAt: json['resolved_at'] == null ? null : DateTime.parse(json['resolved_at'] as String),
      );
}

/// The Incident Engine's correlation/grouping (apps/mobile's IncidentEngine)
/// stays entirely client-side and stateless -- recomputed fresh from current
/// policy/integration state on every build. This service only tracks the
/// human-facing lifecycle (acknowledge/assign/resolve) for whatever incident
/// id the client is currently showing, keyed by that already-stable id
/// (e.g. "incident.power"). Records for incidents no longer currently active
/// stay listed -- they're the "history" half of ADR 099's roadmap sibling,
/// "Persist incident lifecycle/history".
class IncidentLifecycleService {
  Future<List<IncidentLifecycleRecord>> list() async {
    final response = await http
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/incidents'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw IncidentLifecycleServiceException(
        'Unable to load incident lifecycle records (${response.statusCode}).',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw const IncidentLifecycleServiceException('Incident lifecycle response was not a list.');
    }
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(IncidentLifecycleRecord.fromJson)
        .toList(growable: false);
  }

  Future<IncidentLifecycleRecord> update(
    String incidentId, {
    required IncidentLifecycleStatus status,
    String? assignedTo,
    String? notes,
  }) async {
    final response = await http
        .patch(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/incidents/${Uri.encodeComponent(incidentId)}'),
          headers: {
            ...AuthService.authorizationHeaders,
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'status': status.apiValue,
            'assigned_to': assignedTo,
            'notes': notes,
          }),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw IncidentLifecycleServiceException(
        'Unable to update incident (${response.statusCode}).',
      );
    }
    return IncidentLifecycleRecord.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }
}

class IncidentLifecycleServiceException implements Exception {
  const IncidentLifecycleServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
