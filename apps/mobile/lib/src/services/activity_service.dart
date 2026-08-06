import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/activity_event.dart';
import 'auth_service.dart';

class ActivityService {
  ActivityService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<List<ActivityEvent>> fetchEvents({int limit = 20, String severity = 'all'}) async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/activity?limit=$limit&severity=$severity'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 10));
    _ensureSuccess(response);
    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw const ActivityServiceException('Activity response was not a list.');
    }
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(ActivityEvent.fromJson)
        .toList(growable: false);
  }

  Future<int> fetchUnreadCount() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/activity/notifications'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 10));
    _ensureSuccess(response);
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) return 0;
    return decoded['unread_count'] as int? ?? 0;
  }

  Future<void> markAllRead() async {
    final response = await _client
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/activity/notifications/read-all'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 10));
    _ensureSuccess(response);
  }

  void _ensureSuccess(http.Response response) {
    if (response.statusCode == 401) {
      throw const ActivityServiceException('Your session has expired.');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ActivityServiceException('Activity request failed with status ${response.statusCode}.');
    }
  }
}

class ActivityServiceException implements Exception {
  const ActivityServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
