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

  static const _optionalTimeout = Duration(seconds: 4);
  static const _dashboardRetryDelays = <Duration>[
    Duration(seconds: 1),
    Duration(seconds: 2),
    Duration(seconds: 4),
  ];

  final http.Client _client;
  final HomelabService _homelabService = HomelabService();
  final RunningService _runningService = RunningService();
  final GymService _gymService = GymService();
  final HealthService _healthService = HealthService();

  Future<DashboardSummary> fetchDashboard() async {
    // Start all work together, but treat non-core enrichment as optional. The
    // dashboard should never remain blocked because Health, trends, or the
    // recommendation service is slow or unavailable.
    //
    // The core dashboard request retries transient failures because the web
    // client can become interactive a moment before the API is ready after a
    // stack restart. Authentication failures still fail immediately.
    final dashboardFuture = _fetchDashboardSummaryWithRetry();
    final recommendationsFuture = _fetchRecommendations().timeout(
      _optionalTimeout,
      onTimeout: () => const <String>[],
    );
    final trendsFuture = _fetchTrends().timeout(
      _optionalTimeout,
      onTimeout: () => const _DashboardTrends.empty(),
    );
    final healthFuture = _fetchHealthSnapshot().timeout(
      _optionalTimeout,
      onTimeout: () => null,
    );

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

  Future<DashboardSummary> _fetchDashboardSummaryWithRetry() async {
    Object? lastError;
    StackTrace? lastStackTrace;

    for (var attempt = 0; attempt <= _dashboardRetryDelays.length; attempt += 1) {
      try {
        return await _fetchDashboardSummary();
      } on DashboardServiceException catch (error, stackTrace) {
        if (error.isAuthenticationFailure) rethrow;
        lastError = error;
        lastStackTrace = stackTrace;
      } catch (error, stackTrace) {
        lastError = error;
        lastStackTrace = stackTrace;
      }

      if (attempt < _dashboardRetryDelays.length) {
        await Future<void>.delayed(_dashboardRetryDelays[attempt]);
      }
    }

    Error.throwWithStackTrace(lastError!, lastStackTrace!);
  }

  Future<DashboardSummary> _fetchDashboardSummary() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/dashboard');
    final response = await _client
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 8));

    if (response.statusCode == 401) {
      throw const DashboardServiceException(
        'Your session has expired.',
        statusCode: 401,
      );
    }
    if (response.statusCode != 200) {
      throw DashboardServiceException(
        'Dashboard request failed with status ${response.statusCode}.',
        statusCode: response.statusCode,
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
    final hostFuture = _fetchHostTrends();
    final runningFuture = _fetchRunningTrend();
    final gymFuture = _fetchGymTrend();

    final host = await hostFuture;
    final running = await runningFuture;
    final gym = await gymFuture;

    return _DashboardTrends(
      cpu: host.cpu,
      memory: host.memory,
      running: running,
      gym: gym,
    );
  }

  Future<_HostTrends> _fetchHostTrends() async {
    try {
      final history = await _homelabService.fetchHostHistory();
      final recent = history.length > 24
          ? history.sublist(history.length - 24)
          : history;
      return _HostTrends(
        cpu: recent
            .map((item) => item.cpuPercent)
            .whereType<double>()
            .toList(growable: false),
        memory: recent
            .map((item) => item.memoryPercent)
            .whereType<double>()
            .toList(growable: false),
      );
    } catch (_) {
      return const _HostTrends();
    }
  }

  Future<List<double>> _fetchRunningTrend() async {
    try {
      final runs = await _runningService.fetchRuns();
      return runs.reversed
          .take(12)
          .map((item) => item.fitnessScore)
          .toList(growable: false);
    } catch (_) {
      return const <double>[];
    }
  }

  Future<List<double>> _fetchGymTrend() async {
    try {
      final workouts = await _gymService.fetchWorkouts();
      return workouts.reversed
          .take(12)
          .map((item) => item.totalVolumeKg)
          .toList(growable: false);
    } catch (_) {
      return const <double>[];
    }
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

class _HostTrends {
  const _HostTrends({
    this.cpu = const <double>[],
    this.memory = const <double>[],
  });

  final List<double> cpu;
  final List<double> memory;
}

class _DashboardTrends {
  const _DashboardTrends({
    required this.cpu,
    required this.memory,
    required this.running,
    required this.gym,
  });

  const _DashboardTrends.empty()
      : cpu = const <double>[],
        memory = const <double>[],
        running = const <double>[],
        gym = const <double>[];

  final List<double> cpu;
  final List<double> memory;
  final List<double> running;
  final List<double> gym;
}

class DashboardServiceException implements Exception {
  const DashboardServiceException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  bool get isAuthenticationFailure => statusCode == 401;

  @override
  String toString() => message;
}
