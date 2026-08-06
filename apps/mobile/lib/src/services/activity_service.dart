import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/activity_event.dart';
import 'auth_service.dart';

class ActivityService {
  ActivityService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<List<ActivityEvent>> fetchEvents({int limit = 20}) async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/activity?limit=$limit'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 10));

    if (response.statusCode == 401) {
      throw const ActivityServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw ActivityServiceException(
        'Activity request failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw const ActivityServiceException('Activity response was not a list.');
    }
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(ActivityEvent.fromJson)
        .toList(growable: false);
  }
}

class ActivityServiceException implements Exception {
  const ActivityServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
