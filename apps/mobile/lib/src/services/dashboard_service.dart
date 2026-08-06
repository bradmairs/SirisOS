import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../core/siris_event_bus.dart';
import '../models/dashboard_summary.dart';
import '../models/health_snapshot.dart';
import 'auth_service.dart';
import 'gym_service.dart';
import 'health_service.dart';
import 'homelab_service.dart';
import 'running_service.dart';

class DashboardService {
  DashboardService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  final HomelabService _homelabService = HomelabService();
  final RunningService _runningService = RunningService();
  final GymService _gymService = GymService();
  final HealthService _healthService = HealthService();

  Future<DashboardSummary> fetchDashboard() async {
    final dashboardFuture = _fetchDashboardSummary();
    final recommendationsFuture = _fetchRecommendations();
    final trendsFuture = _fetchTrends();
    final healthFuture = _fetchHealthSnapshot();

    final dashboard = await dashboardFuture;
    final recommendations = await recommendationsFuture;
    final trends = await trendsFuture;
    final health = await healthFuture;

    final result = dashboard.copyWith(
      homelab: dashboard.homelab.copyWith(trend: trends.memory),
      running: dashboard.running.copyWith(trend: trends.running),
      gym: dashboard.gym.copyWith(trend: trends.gym),
      system: dashboard.system.copyWith(trend: trends.cpu),
      health: health,
      briefingItems: recommendations.isEmpty
          ? dashboard.briefingItems
          : <String>[...recommendations, ...dashboard.briefingItems],
    );

    SirisEventBus.instance.publish(
      MissionControlRefreshed(source: 'dashboard_service'),
    );
    return result;
  }

  Future<DashboardSummary> _fetchDashboardSummary() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/dashboard');
    final response = await _client
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 8));

    if (response.statusCode == 401) {
      throw const DashboardServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw DashboardServiceException(
        'Dashboard request failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const DashboardServiceException(
        'Dashboard response was not a JSON object.',
      );
    }

    return DashboardSummary.fromJson(decoded);
  }

  Future<HealthSnapshot?> _fetchHealthSnapshot() async {
    try {
      return await _healthService.fetchSnapshot();
    } catch (_) {
      return null;
    }
  }

  Future<_DashboardTrends> _fetchTrends() async {
    var cpu = const <double>[];
    var memory = const <double>[];
    var running = const <double>[];
    var gym = const <double>[];

    try {
      final history = await _homelabService.fetchHostHistory();
      final recent = history.length > 24
          ? history.sublist(history.length - 24)
          : history;
      cpu = recent
          .map((item) => item.cpuPercent)
          .whereType<double>()
          .toList(growable: false);
      memory = recent
          .map((item) => item.memoryPercent)
          .whereType<double>()
          .toList(growable: false);
    } catch (_) {}

    try {
      final runs = await _runningService.fetchRuns();
      running = runs.reversed
          .take(12)
          .map((item) => item.fitnessScore)
          .toList(growable: false);
    } catch (_) {}

    try {
      final workouts = await _gymService.fetchWorkouts();
      gym = workouts.reversed
          .take(12)
          .map((item) => item.totalVolumeKg)
          .toList(growable: false);
    } catch (_) {}

    return _DashboardTrends(
      cpu: cpu,
      memory: memory,
      running: running,
      gym: gym,
    );
  }

  Future<List<String>> _fetchRecommendations() async {
    try {
      final uri = Uri.parse(
        '${ApiConfig.baseUrl}/api/v1/intelligence/recommendations',
      );
      final response = await _client
          .get(uri, headers: AuthService.authorizationHeaders)
          .timeout(const Duration(seconds: 8));
      if (response.statusCode != 200) return const [];

      final decoded = jsonDecode(response.body);
      if (decoded is! List) return const [];

      return decoded
          .whereType<Map<String, dynamic>>()
          .take(3)
          .map((item) {
            final title = item['title'] as String? ?? 'Recommendation';
            final message = item['message'] as String? ?? '';
            return message.isEmpty ? title : '$title — $message';
          })
          .toList(growable: false);
    } catch (_) {
      return const [];
    }
  }
}

class _DashboardTrends {
  const _DashboardTrends({
    required this.cpu,
    required this.memory,
    required this.running,
    required this.gym,
  });

  final List<double> cpu;
  final List<double> memory;
  final List<double> running;
  final List<double> gym;
}

class DashboardServiceException implements Exception {
  const DashboardServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}
