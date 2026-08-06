import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../core/siris_event_bus.dart';
import '../models/run_record.dart';
import 'auth_service.dart';

class RunningService {
  Future<List<RunRecord>> fetchRuns() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/running'),
      headers: AuthService.authorizationHeaders,
    ).timeout(const Duration(seconds: 8));
    if (response.statusCode != 200) throw Exception('Could not load runs.');
    final decoded = jsonDecode(response.body) as List<dynamic>;
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(RunRecord.fromJson)
        .toList(growable: false);
  }

  Future<void> createRun({
    required DateTime date,
    required String type,
    required double distanceKm,
    required int paceSecondsPerKm,
    required int averageHeartRate,
  }) async {
    final response = await http.post(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/running'),
      headers: {
        ...AuthService.authorizationHeaders,
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'run_date': date.toIso8601String().split('T').first,
        'run_type': type,
        'distance_km': distanceKm,
        'average_pace_seconds_per_km': paceSecondsPerKm,
        'average_heart_rate': averageHeartRate,
      }),
    ).timeout(const Duration(seconds: 8));
    if (response.statusCode != 201) throw Exception('Could not save run.');

    SirisEventBus.instance.publish(
      ModuleDataChanged(moduleId: 'running', reason: 'run_logged'),
    );
    SirisEventBus.instance.publish(
      NotificationStateChanged(source: 'running'),
    );
  }
}
