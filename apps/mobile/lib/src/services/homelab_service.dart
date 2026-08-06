import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../core/siris_event_bus.dart';
import '../models/docker_summary.dart';
import '../models/homelab_alerts.dart';
import '../models/homelab_audit_event.dart';
import '../models/host_metrics.dart';
import 'auth_service.dart';

class HomelabService {
  HomelabService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<DockerSummary> fetchDockerSummary() async {
    final decoded = await _getJson('/api/v1/homelab/docker');
    return DockerSummary.fromJson(decoded);
  }

  Future<HostMetrics> fetchHostMetrics() async {
    final decoded = await _getJson('/api/v1/homelab/host');
    return HostMetrics.fromJson(decoded);
  }

  Future<HomelabAlertSummary> fetchAlerts() async {
    final decoded = await _getJson('/api/v1/homelab/alerts');
    return HomelabAlertSummary.fromJson(decoded);
  }

  Future<List<HomelabAuditEvent>> fetchAuditHistory({int limit = 100}) async {
    final response = await _get('/api/v1/homelab/audit?limit=$limit');
    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw const HomelabServiceException('Audit response was not a JSON list.');
    }
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(HomelabAuditEvent.fromJson)
        .toList(growable: false);
  }

  Future<List<HostMetricHistorySample>> fetchHostHistory() async {
    final decoded = await _getJson('/api/v1/homelab/host/history');
    final samples = decoded['samples'];
    if (samples is! List) return const [];
    return samples
        .whereType<Map<String, dynamic>>()
        .map(HostMetricHistorySample.fromJson)
        .toList(growable: false);
  }

  Future<String> fetchContainerLogs(String containerId, {int tail = 300}) async {
    final decoded = await _getJson(
      '/api/v1/homelab/docker/$containerId/logs?tail=$tail',
    );
    return decoded['logs'] as String? ?? '';
  }

  Future<String> performContainerAction(
    String containerId,
    String action,
  ) async {
    final response = await _client
        .post(
          Uri.parse(
            '${ApiConfig.baseUrl}/api/v1/homelab/docker/$containerId/$action',
          ),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 401) {
      throw const HomelabServiceException('Your session has expired.');
    }
    final decoded = jsonDecode(response.body);
    if (response.statusCode != 200) {
      final detail = decoded is Map<String, dynamic> ? decoded['detail'] : null;
      throw HomelabServiceException(
        detail as String? ?? 'Container action failed.',
      );
    }
    if (decoded is! Map<String, dynamic>) {
      throw const HomelabServiceException(
        'Invalid container action response.',
      );
    }

    final status = decoded['status'] as String? ?? 'unknown';
    SirisEventBus.instance.publish(
      ModuleDataChanged(
        moduleId: 'homelab',
        reason: 'container_${action}_completed',
      ),
    );
    SirisEventBus.instance.publish(
      NotificationStateChanged(source: 'homelab_service'),
    );
    return status;
  }

  Future<Map<String, dynamic>> _getJson(String path) async {
    final response = await _get(path);
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const HomelabServiceException(
        'Homelab response was not a JSON object.',
      );
    }
    return decoded;
  }

  Future<http.Response> _get(String path) async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}$path'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 10));
    if (response.statusCode == 401) {
      throw const HomelabServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw HomelabServiceException(
        'Homelab request failed with status ${response.statusCode}.',
      );
    }
    return response;
  }
}

class HomelabServiceException implements Exception {
  const HomelabServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
