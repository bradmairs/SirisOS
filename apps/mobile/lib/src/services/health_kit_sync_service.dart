import 'dart:convert';

import 'package:health/health.dart' as hk;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config/api_config.dart';
import 'auth_service.dart';

/// Reads Apple HealthKit data on-device and pushes it to the existing
/// POST /api/v1/health/ingest endpoint, in the same JSON shape Health Auto
/// Export used to send -- so the backend's parsing/storage didn't need to
/// change to support this as a native pusher.
class HealthKitSyncService {
  HealthKitSyncService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  final hk.Health _health = hk.Health();

  static const _lastSyncKey = 'health_kit_last_sync_millis';

  // Maps to the same metric_type strings the backend/UI already recognise
  // (see HealthIngestService, health_snapshot.dart's healthMetricDisplayName).
  // VO2 max is not yet exposed by the `health` plugin's HealthDataType, so
  // it is not synced by this path. HEART_RATE_VARIABILITY_SDNN feeds both
  // the Health screen and TrainingConflictService/ReadinessService, which
  // already recognised "heart_rate_variability" before any data for it
  // existed -- this is what actually starts populating it.
  static const Map<hk.HealthDataType, String> _metricTypes = {
    hk.HealthDataType.STEPS: 'step_count',
    hk.HealthDataType.RESTING_HEART_RATE: 'resting_heart_rate',
    hk.HealthDataType.HEART_RATE_VARIABILITY_SDNN: 'heart_rate_variability',
    hk.HealthDataType.SLEEP_ASLEEP: 'sleep_analysis',
    hk.HealthDataType.WEIGHT: 'body_mass',
    hk.HealthDataType.ACTIVE_ENERGY_BURNED: 'active_energy_burned',
    hk.HealthDataType.BLOOD_OXYGEN: 'blood_oxygen',
    hk.HealthDataType.RESPIRATORY_RATE: 'respiratory_rate',
    hk.HealthDataType.BODY_FAT_PERCENTAGE: 'body_fat_percentage',
    hk.HealthDataType.FLIGHTS_CLIMBED: 'flights_climbed',
  };

  List<hk.HealthDataType> get _requestedTypes => [
        ..._metricTypes.keys,
        hk.HealthDataType.WORKOUT,
      ];

  Future<DateTime?> lastSyncTime() async {
    final preferences = await SharedPreferences.getInstance();
    final millis = preferences.getInt(_lastSyncKey);
    return millis == null ? null : DateTime.fromMillisecondsSinceEpoch(millis);
  }

  /// Runs the HealthKit permission + data sync flow and pushes any new
  /// samples/workouts to SirisOS. Safe to call repeatedly (e.g. on app
  /// launch/resume and from a manual "Sync now" button) -- HealthKit's
  /// authorization sheet only appears once per type, and re-requesting after
  /// that is a fast no-op.
  Future<HealthSyncResult> sync() async {
    await _health.configure();

    final types = _requestedTypes;
    final authorized = await _health.requestAuthorization(
      types,
      permissions: List.filled(types.length, hk.HealthDataAccess.READ),
    );
    if (!authorized) {
      // HealthKit's own privacy model means this only reflects whether the
      // permission sheet completed, not whether every type was granted --
      // per-type denials just come back as empty queries below, which is
      // expected and not an error.
      throw const HealthKitSyncException('Apple Health access was not granted.');
    }

    final preferences = await SharedPreferences.getInstance();
    final lastSyncMillis = preferences.getInt(_lastSyncKey);
    final now = DateTime.now();
    final startTime = lastSyncMillis != null
        ? DateTime.fromMillisecondsSinceEpoch(lastSyncMillis)
        : now.subtract(const Duration(days: 30));

    final metricPoints = await _health.getHealthDataFromTypes(
      types: _metricTypes.keys.toList(growable: false),
      startTime: startTime,
      endTime: now,
    );
    final workoutPoints = await _health.getHealthDataFromTypes(
      types: const [hk.HealthDataType.WORKOUT],
      startTime: startTime,
      endTime: now,
    );

    if (metricPoints.isNotEmpty || workoutPoints.isNotEmpty) {
      final payload = _buildPayload(metricPoints, workoutPoints);
      final response = await _client
          .post(
            Uri.parse('${ApiConfig.baseUrl}/api/v1/health/ingest'),
            headers: {
              'Content-Type': 'application/json',
              ...AuthService.authorizationHeaders,
            },
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 30));

      if (response.statusCode != 202) {
        throw HealthKitSyncException('Health sync failed with status ${response.statusCode}.');
      }
    }

    await preferences.setInt(_lastSyncKey, now.millisecondsSinceEpoch);
    return HealthSyncResult(
      metricSamplesSent: metricPoints.length,
      workoutsSent: workoutPoints.length,
    );
  }

  Map<String, dynamic> _buildPayload(
    List<hk.HealthDataPoint> metricPoints,
    List<hk.HealthDataPoint> workoutPoints,
  ) {
    final samplesByMetric = <String, List<Map<String, dynamic>>>{};
    final unitByMetric = <String, String>{};

    for (final point in metricPoints) {
      final metricName = _metricTypes[point.type];
      final value = point.value;
      if (metricName == null || value is! hk.NumericHealthValue) continue;

      samplesByMetric.putIfAbsent(metricName, () => []).add({
        'date': _formatTimestamp(point.dateFrom),
        'qty': value.numericValue,
        'source': point.sourceName,
      });
      unitByMetric.putIfAbsent(metricName, () => point.unit.name);
    }

    final workouts = <Map<String, dynamic>>[];
    for (final point in workoutPoints) {
      final value = point.value;
      if (value is! hk.WorkoutHealthValue) continue;

      workouts.add({
        'id': point.uuid,
        'name': value.workoutActivityType.name,
        'start': _formatTimestamp(point.dateFrom),
        'end': _formatTimestamp(point.dateTo),
        'duration': point.dateTo.difference(point.dateFrom).inSeconds,
        if (value.totalDistance != null) 'distance': value.totalDistance,
        if (value.totalEnergyBurned != null) 'activeEnergyBurned': value.totalEnergyBurned,
        'source': point.sourceName,
      });
    }

    return {
      'data': {
        'metrics': samplesByMetric.entries
            .map((entry) => {
                  'name': entry.key,
                  'units': unitByMetric[entry.key],
                  'data': entry.value,
                })
            .toList(growable: false),
        'workouts': workouts,
      },
    };
  }

  // Matches the "YYYY-MM-DD HH:MM:SS +0000" shape the backend's
  // HealthIngestService already parses (the format Health Auto Export sent).
  String _formatTimestamp(DateTime dateTime) {
    final utc = dateTime.toUtc();
    String pad(int value, [int width = 2]) => value.toString().padLeft(width, '0');
    return '${pad(utc.year, 4)}-${pad(utc.month)}-${pad(utc.day)} '
        '${pad(utc.hour)}:${pad(utc.minute)}:${pad(utc.second)} +0000';
  }
}

class HealthSyncResult {
  const HealthSyncResult({required this.metricSamplesSent, required this.workoutsSent});

  final int metricSamplesSent;
  final int workoutsSent;

  bool get hadNewData => metricSamplesSent > 0 || workoutsSent > 0;
}

class HealthKitSyncException implements Exception {
  const HealthKitSyncException(this.message);

  final String message;

  @override
  String toString() => message;
}
