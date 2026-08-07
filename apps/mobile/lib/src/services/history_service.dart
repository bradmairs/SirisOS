import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/time_series_observation.dart';
import 'auth_service.dart';

class HistoryService {
  HistoryService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<List<TimeSeriesObservation>> fetchHistory({
    required String source,
    required String metric,
    int hours = 24,
    int limit = 720,
    Map<String, String>? dimensions,
  }) async {
    final query = <String, String>{
      'source': source,
      'metric': metric,
      'hours': '$hours',
      'limit': '$limit',
      if (dimensions != null && dimensions.isNotEmpty)
        'dimensions': jsonEncode(dimensions),
    };
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/history')
        .replace(queryParameters: query);
    final response = await _client
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 6));
    if (response.statusCode == 401) {
      throw const HistoryServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw HistoryServiceException(
        'History request failed with status ${response.statusCode}.',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const HistoryServiceException('Invalid history response.');
    }
    final raw = decoded['observations'];
    if (raw is! List) return const <TimeSeriesObservation>[];
    return raw
        .whereType<Map<String, dynamic>>()
        .map(TimeSeriesObservation.fromJson)
        .toList(growable: false);
  }
}

class HistoryServiceException implements Exception {
  const HistoryServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}
